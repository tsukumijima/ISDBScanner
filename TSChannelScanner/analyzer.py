
from __future__ import annotations

from ariblib import TransportStreamFile
from ariblib.descriptors import *
from ariblib.sections import *
from io import BytesIO
from pydantic import BaseModel
from typing import Any


class TransportStreamInfo(BaseModel):
    physical_channel: str = ''
    physical_channel_number: int = -1
    physical_channel_slot: int = -1
    frequency: int = -1
    transport_stream_id: int = -1
    network_id: int = -1
    network_name: str = ''
    remote_control_key_id: int = -1
    services: list[ServiceInfo] = []

class ServiceInfo(BaseModel):
    service_id: int = -1
    service_name: str = ''
    service_type: int = -1
    is_free: bool = True


class TransportStreamAnalyzer(TransportStreamFile):
    """
    ISDB-T / ISDB-S (地上波・BS・CS110) の TS ストリームに含まれる PSI/SI を解析するクラス
    ariblib の TransportStreamFile を継承しているが、メモリ上に格納された TS ストリームを直接解析できる
    """


    def __init__(self, ts_stream_data: bytearray, chunk_size: int = 10000):
        """
        TransportStreamAnalyzer を初期化する
        BS / CS110 では、NIT や SDT などの SI (Service Information) の送出周期 (2023/08 時点で最大 10 秒周期) の関係で、
        10 秒以上の長さを持つ TS ストリームを指定する必要がある

        Args:
            ts_stream_data (bytearray): チューナーから受信した TS ストリーム
            chunk_size (int, optional): チャンクサイズ. Defaults to 10000.
        """

        self.bytes_io = BytesIO(ts_stream_data)
        self.chunk_size = chunk_size
        self._callbacks: Any = dict()


    # TransportStreamFile は BufferedReader を継承しているが、BufferedReader ではメモリ上のバッファを直接操作できないため、
    # BufferedReader から継承しているメソッドのうち、TransportStreamFile の動作に必要なメソッドだけをオーバーライドしている
    def read(self, size: int | None = -1) -> bytes:
        return self.bytes_io.read(size)
    def seek(self, offset: int, whence: int = 0) -> int:
        return self.bytes_io.seek(offset, whence)
    def tell(self) -> int:
        return self.bytes_io.tell()


    def analyze(self) -> list[TransportStreamInfo]:
        """
        トランスポートストリームとサービスの情報を解析する

        Returns:
            list[TransportStreamInfo]: トランスポートストリームとサービスの情報
        """

        # transport_stream_id をキーにして TS の情報を格納する
        # transport_stream_id は事実上日本国内すべての放送波で一意 (のはず)
        ts_info_list: dict[int, TransportStreamInfo] = {}

        # NIT (自ネットワーク) からトランスポートストリームの情報を取得
        # 自ネットワーク: 選局中の TS が所属するものと同一のネットワーク
        self.seek(0)
        for nit in self.sections(ActualNetworkNetworkInformationSection):
            for transport_stream in nit.transport_streams:
                # すでに同じ transport_stream_id の TS が登録されている場合はスキップ
                if len([ts for ts in ts_info_list.values() if ts.transport_stream_id == transport_stream.transport_stream_id]) > 0:
                    continue
                # トランスポートストリームの情報を格納
                ts_info = TransportStreamInfo()
                ts_info.transport_stream_id = transport_stream.transport_stream_id
                ts_info.network_id = nit.network_id
                ts_info_list[ts_info.transport_stream_id] = ts_info
                # TSInformationDescriptor は地上波でのみ送出される
                if ts_info.network_id >= 0x7880 and ts_info.network_id <= 0x7FE8:
                    for ts_information in transport_stream.descriptors.get(TSInformationDescriptor, []):
                        ts_info.network_name = ts_information.ts_name_char
                        ts_info.remote_control_key_id = ts_information.remote_control_key_id
                        break
                # 地上波以外では NetworkNameDescriptor の値を使用する
                else:
                    for network_name in nit.network_descriptors.get(NetworkNameDescriptor, []):
                        ts_info.network_name = network_name.char
                        break

        # SDT からサービスの情報を取得
        self.seek(0)
        for sdt in self.sections(ServiceDescriptionSection):
            for service in sdt.services:
                # すでに取得されているはずのトランスポートストリームの情報を取得
                ts_info = ts_info_list.get(sdt.transport_stream_id)
                if ts_info is None:
                    continue
                # すでに同じ service_id のサービスが登録されている場合はスキップ
                if len([sv for sv in ts_info.services if sv.service_id == service.service_id]) > 0:
                    continue
                # サービスの情報を格納
                service_info = ServiceInfo()
                service_info.service_id = service.service_id
                service_info.is_free = not bool(service.free_CA_mode)
                ts_info.services.append(service_info)
                for service in service.descriptors.get(ServiceDescriptor, []):
                    service_info.service_type = service.service_type
                    service_info.service_name = service.service_name
                    break

        from devtools import debug
        debug(ts_info_list)

        # list に変換して返す
        return list(ts_info_list.values())
