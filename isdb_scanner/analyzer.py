
from __future__ import annotations

from ariblib import TransportStreamFile
from ariblib.descriptors import (
    NetworkNameDescriptor,
    PartialReceptionDescriptor,
    SatelliteDeliverySystemDescriptor,
    ServiceDescriptor,
    TSInformationDescriptor,
)
from ariblib.sections import (
    ActualNetworkNetworkInformationSection,
    ServiceDescriptionSection,
)
from collections import defaultdict
from io import BytesIO
from pydantic import BaseModel
from pydantic import RootModel
from typing import Any


class TransportStreamInfo(BaseModel):
    physical_channel: str = ''
    transport_stream_id: int = -1
    network_id: int = -1
    network_name: str = ''
    remote_control_key_id: int | None = None
    satellite_frequency: float | None = None
    satellite_transponder: int | None = None
    satellite_slot: int | None = None
    services: list[ServiceInfo] = []

class TransportStreamInfoList(RootModel[list[TransportStreamInfo]]):
    root: list[TransportStreamInfo]

class ServiceInfo(BaseModel):
    service_id: int = -1
    service_name: str = ''
    service_type: int = -1
    is_free: bool = True
    is_oneseg: bool = False


class TransportStreamAnalyzer(TransportStreamFile):
    """
    ISDB-T / ISDB-S (地上波・BS・CS110) の TS ストリームに含まれる PSI/SI を解析するクラス
    ariblib の TransportStreamFile を継承しているが、メモリ上に格納された TS ストリームを直接解析できる
    """


    def __init__(self, ts_stream_data: bytearray, tuned_physical_channel: str, chunk_size: int = 10000):
        """
        TransportStreamAnalyzer を初期化する
        BS / CS110 では、NIT や SDT などの SI (Service Information) の送出間隔 (2023/08 時点で最大 10 秒周期) の関係で、
        最低 15 秒以上の長さを持つ TS ストリームを指定する必要がある (なお地上波の SI 送出間隔は最大 2 秒周期)

        Args:
            ts_stream_data (bytearray): チューナーから受信した TS ストリーム
            tuned_physical_channel (str): TS ストリームの受信時に選局した物理チャンネル (ex: "T13" / "BS23_3", "CS04")
            chunk_size (int, optional): チャンクサイズ. Defaults to 10000.
        """

        self.tuned_physical_channel = tuned_physical_channel
        self.chunk_size = chunk_size
        self._bytes_io = BytesIO(ts_stream_data)
        self._callbacks: Any = dict()


    # TransportStreamFile は BufferedReader を継承しているが、BufferedReader ではメモリ上のバッファを直接操作できないため、
    # BufferedReader から継承しているメソッドのうち、TransportStreamFile の動作に必要なメソッドだけをオーバーライドしている
    def read(self, size: int | None = -1) -> bytes:
        return self._bytes_io.read(size)
    def seek(self, offset: int, whence: int = 0) -> int:
        return self._bytes_io.seek(offset, whence)
    def tell(self) -> int:
        return self._bytes_io.tell()


    def analyze(self) -> list[TransportStreamInfo]:
        """
        トランスポートストリームとサービスの情報を解析する
        ref: https://codepen.io/ppsrbn/pen/KKZPapG

        Returns:
            list[TransportStreamInfo]: トランスポートストリームとサービスの情報
        """

        # transport_stream_id をキーにして TS の情報を格納する
        # transport_stream_id は事実上日本国内すべての放送波で一意 (のはず)
        ts_infos: dict[int, TransportStreamInfo] = {}

        # NIT (自ネットワーク) からトランスポートストリームの情報を取得
        # 自ネットワーク: 選局中の TS が所属するものと同一のネットワーク
        self.seek(0)
        for nit in self.sections(ActualNetworkNetworkInformationSection):
            for transport_stream in nit.transport_streams:
                # トランスポートストリームの情報を格納
                # すでに同じ transport_stream_id の TS が登録されている場合は既存の情報を上書きする
                if transport_stream.transport_stream_id in ts_infos:
                    ts_info = ts_infos[transport_stream.transport_stream_id]
                else:
                    ts_info = TransportStreamInfo()
                    ts_info.transport_stream_id = int(transport_stream.transport_stream_id)
                    ts_infos[ts_info.transport_stream_id] = ts_info
                ts_info.network_id = int(nit.network_id)
                # BS の TSID は、ARIB TR-B15 第三分冊 第一部 第七編 8.1.1 によると
                # (network_idの下位4ビット:4bit)(放送開始時期を示すフラグ:3bit)(トランスポンダ番号:5bit)(予約:1bit)(スロット番号:3bit) の 16bit で構成されている
                # ここからビット演算でトランスポンダ番号とスロット番号を取得する
                if ts_info.network_id == 4:
                    ts_info.satellite_transponder = (ts_info.transport_stream_id >> 4) & 0b11111
                    ts_info.satellite_slot = ts_info.transport_stream_id & 0b111
                    ts_info.physical_channel = f'BS{ts_info.satellite_transponder:02d}/TS{ts_info.satellite_slot}'
                # CS110 の TSID は、ARIB TR-B15 第四分冊 第二部 第七編 8.1.1 によると
                # (network_idの下位4ビット:4bit)(予約:3bit)(トランスポンダ番号:5bit)(予約:1bit)(スロット番号:3bit) の 16bit で構成されている
                # ここからビット演算でトランスポンダ番号を取得する (スロット番号は常に 0 なので取得しない)
                elif ts_info.network_id == 6 or ts_info.network_id == 7:
                    ts_info.satellite_transponder = (ts_info.transport_stream_id >> 4) & 0b11111
                    ts_info.physical_channel = f'CS{ts_info.satellite_transponder:02d}'
                if ts_info.network_id >= 0x7880 and ts_info.network_id <= 0x7FE8:
                    # TS 情報記述子 (地上波のみ)
                    for ts_information in transport_stream.descriptors.get(TSInformationDescriptor, []):
                        ts_info.network_name = str(ts_information.ts_name_char)  # TS 名 (ネットワーク名として設定)
                        ts_info.remote_control_key_id = int(ts_information.remote_control_key_id)  # リモコンキー ID
                        break
                    # 部分受信記述子 (地上波のみ)
                    # ワンセグ放送のサービスを特定するために必要
                    for partial_reception in transport_stream.descriptors.get(PartialReceptionDescriptor, []):
                        for partial_service in partial_reception.services:
                            # すでに同じ service_id のサービスが登録されている場合は既存の情報を上書きする
                            if partial_service.service_id in [sv.service_id for sv in ts_info.services]:
                                service_info = [sv for sv in ts_info.services if sv.service_id == partial_service.service_id][0]
                            else:
                                service_info = ServiceInfo()
                                service_info.service_id = int(partial_service.service_id)
                                ts_info.services.append(service_info)
                            service_info.is_oneseg = True
                        break
                else:
                    # 衛星分配システム記述子 (衛星放送のみ)
                    for satellite_delivery_system in transport_stream.descriptors.get(SatelliteDeliverySystemDescriptor, []):
                        ts_info.satellite_frequency = float(satellite_delivery_system.frequency)  # GHz 単位
                    # ネットワーク名記述子
                    for network_name in nit.network_descriptors.get(NetworkNameDescriptor, []):
                        ts_info.network_name = str(network_name.char)  # ネットワーク名 (地上波では "関東広域0" のような値になるので利用しない)
                        break

        # BS のスロット番号を 0 からの連番に振り直す
        ## TSID は ARIB TR-B15 第三分冊 第一部 第七編 8.1.1 の規定により末尾 3bit がスロット番号となっていて、
        ## ISDB-S の TMCC 信号内の相対 TS 番号と同一になるとされている
        ## ところが、BS 帯域再編の影響でスロット番号 0 を持つ TS が存在しない場合がある
        ## (規定にも「ただし例外として、再編により相対 TS 番号の若い TS が他中継器へ移動あるいは消滅する場合は、
        ## 残る TS に対し相対 TS 番号を前詰めとし、bit (2-0) は従前の値を継承して割り付けることを可能とする」とある)
        ## 一方 px4_drv は選局時に 0 スタートかつ歯抜けがない連番の相対 TS 番号を求めるため、スロット番号に齟齬が生じる
        ## ここでは便宜上スロット番号を多くのチューナーが要求する 0 からの連番 (≒ TMCC 信号内の相対 TS 番号 (?)) に振り直すこととする
        # 同じトランスポンダ (中継器) を持つ TS ごとにグループ化
        groups: defaultdict[int, list[TransportStreamInfo]] = defaultdict(list)
        for ts_info in ts_infos.values():
            if ts_info.network_id == 4 and ts_info.satellite_transponder is not None:
                groups[ts_info.satellite_transponder].append(ts_info)
        # 各グループをスロット番号順にソートし、satellite_slot を連番で振り直して、合わせて physical_channel を更新する
        for group in groups.values():
            group.sort(key=lambda ts_info: ts_info.satellite_slot or -1)
            for count, ts_info in enumerate(group):
                ts_info.satellite_slot = count
                ts_info.physical_channel = f'BS{ts_info.satellite_transponder:02d}/TS{ts_info.satellite_slot}'

        # 解析中の TS ストリーム選局時の物理チャンネルが地上波 ("T13" など) なら、常に選局した 1TS のみが取得されるはず
        ## 地上波では当然ながら PSI/SI からは受信中の物理チャンネルを判定できないので、ここで別途セットする
        if self.tuned_physical_channel.startswith('T'):
            assert len(ts_infos) == 1
            ts_infos[list(ts_infos.keys())[0]].physical_channel = self.tuned_physical_channel
        # 地上波以外では、TS 情報を物理チャンネル順に並び替える
        else:
            ts_infos = dict(sorted(ts_infos.items(), key=lambda x: x[1].physical_channel))

        # SDT からサービスの情報を取得
        self.seek(0)
        for sdt in self.sections(ServiceDescriptionSection):
            for service in sdt.services:
                # すでに取得されているはずのトランスポートストリームの情報を取得
                ts_info = ts_infos.get(sdt.transport_stream_id)
                if ts_info is None:
                    continue
                # サービスの情報を格納
                # すでに同じ service_id のサービスが登録されている場合は既存の情報を上書きする
                if service.service_id in [sv.service_id for sv in ts_info.services]:
                    service_info = [sv for sv in ts_info.services if sv.service_id == service.service_id][0]
                else:
                    service_info = ServiceInfo()
                    service_info.service_id = int(service.service_id)
                    ts_info.services.append(service_info)
                service_info.is_free = not bool(service.free_CA_mode)
                for service in service.descriptors.get(ServiceDescriptor, []):
                    service_info.service_type = int(service.service_type)
                    service_info.service_name = str(service.service_name)
                    break
            # service_id 順にソート
            ts_info = ts_infos.get(sdt.transport_stream_id)
            if ts_info is not None:
                ts_info.services.sort(key=lambda x: x.service_id)

        # list に変換して返す
        return list(ts_infos.values())
