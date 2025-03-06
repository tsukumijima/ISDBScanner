from collections import defaultdict
from io import BytesIO
from typing import Any

from ariblib import TransportStreamFile
from ariblib.aribstr import AribString
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

from isdb_scanner.constants import ServiceInfo, TransportStreamInfo


class TransportStreamAnalyzer(TransportStreamFile):
    """
    ISDB-T/ISDB-S (地上波・BS・CS110) の TS ストリームに含まれる PSI/SI を解析するクラス
    ariblib の TransportStreamFile を継承しているが、メモリ上に格納された TS ストリームを直接解析できる
    """

    def __init__(self, ts_stream_data: bytearray, tuned_physical_channel: str, chunk_size: int = 10000):
        """
        TransportStreamAnalyzer を初期化する
        BS / CS110 では、NIT や SDT などの SI (Service Information) の送出間隔 (2023/08 時点で最大 10 秒周期) の関係で、
        最低 15 秒以上の長さを持つ TS ストリームを指定する必要がある (なお地上波の SI 送出間隔は最大 2 秒周期)

        Args:
            ts_stream_data (bytearray): チューナーから受信した TS ストリーム
            tuned_physical_channel (str): TS ストリームの受信時に選局した物理チャンネル (ex: "T13", "BS23/TS3", "ND04")
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

        try:
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
                    # (network_idの下位4ビット:4bit)(放送開始時期を示すフラグ:3bit)(トランスポンダ番号:5bit)(予約:1bit)(スロット番号:3bit)
                    # の 16bit で構成されている
                    # ここからビット演算でトランスポンダ番号とスロット番号を取得する
                    if ts_info.network_id == 4:
                        ts_info.satellite_transponder = (ts_info.transport_stream_id >> 4) & 0b11111
                        ts_info.satellite_slot_number = ts_info.transport_stream_id & 0b111
                        ts_info.physical_channel = f'BS{ts_info.satellite_transponder:02d}/TS{ts_info.satellite_slot_number}'
                    # CS110 の TSID は、ARIB TR-B15 第四分冊 第二部 第七編 8.1.1 によると
                    # (network_idの下位4ビット:4bit)(予約:3bit)(トランスポンダ番号:5bit)(予約:1bit)(スロット番号:3bit) の 16bit で構成されている
                    # ここからビット演算でトランスポンダ番号を取得する (CS110 ではスロット番号は常に 0 なので取得しない)
                    elif ts_info.network_id == 6 or ts_info.network_id == 7:
                        ts_info.satellite_transponder = (ts_info.transport_stream_id >> 4) & 0b11111
                        ts_info.physical_channel = f'ND{ts_info.satellite_transponder:02d}'
                    if 0x7880 <= ts_info.network_id <= 0x7FE8:
                        # TS 情報記述子 (地上波のみ)
                        for ts_information in transport_stream.descriptors.get(TSInformationDescriptor, []):
                            # TS 名 (ネットワーク名として設定)
                            ts_info.network_name = self.__fullWidthToHalfWith(ts_information.ts_name_char)
                            # リモコンキー ID
                            ts_info.remote_control_key_id = int(ts_information.remote_control_key_id)
                            break
                        # 部分受信記述子 (地上波のみ)
                        # ワンセグ放送のサービスを特定するために必要
                        for partial_reception in transport_stream.descriptors.get(PartialReceptionDescriptor, []):
                            for partial_service in partial_reception.services:
                                # すでに同じ service_id のサービスが登録されている場合は既存の情報を上書きする
                                if partial_service.service_id in [sv.service_id for sv in ts_info.services]:
                                    service_info = next(sv for sv in ts_info.services if sv.service_id == partial_service.service_id)
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
                            # ネットワーク名 (地上波では "関東広域0" のような値になるので利用しない)
                            ts_info.network_name = self.__fullWidthToHalfWith(network_name.char)
                            break

            # BS のスロット番号を適切に振り直す
            ## TSID は ARIB TR-B15 第三分冊 第一部 第七編 8.1.1 の規定により末尾 3bit がスロット番号となっていて、
            ## ISDB-S の TMCC 信号内の相対 TS 番号と同一になるとされている
            ## ところが、BS 帯域再編や閉局の影響でスロット番号に歯抜けが生じる場合がある
            ## (規定にも「ただし例外として、再編により相対 TS 番号の若い TS が他中継器へ移動あるいは消滅する場合は、
            ## 残る TS に対し相対 TS 番号を前詰めとし、bit (2-0) は従前の値を継承して割り付けることを可能とする」とある)
            ## 一方 px4_drv は選局時に 0 スタートの相対 TS 番号を求めるため、スロット番号に齟齬が生じる
            ## ここでは、相対 TS 番号が 0 スタートになるよう、適切に相対 TS 番号を振り直すこととする
            ## 同じトランスポンダ (中継器) の中にかつて TS0, TS1, TS2, TS3 が放送されていたと仮定した際、下記の通り振る舞う
            ## 1. 再編や閉局で TS0, TS1 が消滅した場合、消滅した分の相対 TS 番号分、旧 TS2, TS3 をそれぞれ TS0, TS1 に相対 TS 番号をずらす
            ## 2. 再編や閉局で TS0, TS2 が消滅した場合、旧 TS1 を TS0 に、旧 TS3 を TS1 に相対 TS 番号をずらす
            ## 以前は『再編や閉局で TS2 が消滅した場合、物理的には TS2 は残存している (ヌルパケットが送られている) ため、相対 TS 番号の振り直しは行わない』挙動だったが、
            ## 2025年2月末の帯域再編で閉局した空き帯域の相対 TS 番号が一斉に詰められた関係で齟齬が出たため、現在は上記挙動に変更している
            ## （本来はこのように厳密に一意に定まらない相対 TS 番号ではなく、TSID を指定して選局すべき）
            # 同じトランスポンダ (中継器) を持つ TS ごとにグループ化
            bs_groups: defaultdict[int, list[TransportStreamInfo]] = defaultdict(list)
            for ts_info in ts_infos.values():
                if ts_info.network_id == 4 and ts_info.satellite_transponder is not None:
                    bs_groups[ts_info.satellite_transponder].append(ts_info)
            # 各グループをスロット番号順にソートし、satellite_slot を適切に振り直して、合わせて physical_channel を更新する
            for bs_group in bs_groups.values():
                bs_group.sort(key=lambda ts_info: ts_info.satellite_slot_number or -1)
                slot_numbers = [ts_info.satellite_slot_number for ts_info in bs_group if ts_info.satellite_slot_number is not None]
                new_slot_numbers: list[int] = []
                """
                # 相対 TS 番号を適切に詰める
                if 0 not in slot_numbers:
                    # 0 が存在しない場合のみ、他の相対 TS 番号を前にずらす
                    shift = min(slot_numbers)
                    new_slot_numbers = [slot - shift for slot in slot_numbers]
                else:
                    # 0 が存在する場合は変更しない
                    new_slot_numbers = slot_numbers
                """
                # 相対 TS 番号を0スタートの連番になるように振り直す
                # 例: [0,1,3,5] → [0,1,2,3], [1,3,5] → [0,1,2]
                new_slot_numbers = []
                sorted_slots = sorted(slot_numbers)
                for i, _ in enumerate(sorted_slots):
                    new_slot_numbers.append(i)
                # 新しいスロット番号を割り当てる
                for ts_info, new_slot in zip(bs_group, new_slot_numbers):
                    ts_info.satellite_slot_number = new_slot
                    ts_info.physical_channel = f'BS{ts_info.satellite_transponder:02d}/TS{new_slot}'

            # 解析中の TS ストリーム選局時の物理チャンネルが地上波 ("T13" など) なら、常に選局した 1TS のみが取得されるはず
            ## 地上波では当然ながら PSI/SI からは受信中の物理チャンネルを判定できないので、ここで別途セットする
            if self.tuned_physical_channel.startswith('T'):
                assert len(ts_infos) == 1
                ts_infos[next(iter(ts_infos.keys()))].physical_channel = self.tuned_physical_channel
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
                        service_info = next(sv for sv in ts_info.services if sv.service_id == service.service_id)
                    else:
                        service_info = ServiceInfo()
                        service_info.service_id = int(service.service_id)
                        ts_info.services.append(service_info)
                    service_info.is_free = not bool(service.free_CA_mode)
                    for service in service.descriptors.get(ServiceDescriptor, []):
                        service_info.service_type = int(service.service_type)
                        service_info.service_name = self.__fullWidthToHalfWith(service.service_name)
                        break
                # service_id 順にソート
                ts_info = ts_infos.get(sdt.transport_stream_id)
                if ts_info is not None:
                    ts_info.services.sort(key=lambda x: x.service_id)

            # 3桁チャンネル番号を算出
            for ts_info in ts_infos.values():
                for service_info in ts_info.services:
                    # 地上波: ((サービス種別 × 200) + remote_control_key_id × 10) + (サービス番号 + 1)
                    if 0x7880 <= ts_info.network_id <= 0x7FE8:
                        assert ts_info.remote_control_key_id is not None
                        # 地上波のサービス ID は、ARIB TR-B14 第五分冊 第七編 9.1 によると
                        # (地域種別:6bit)(県複フラグ:1bit)(サービス種別:2bit)(地域事業者識別:4bit)(サービス番号:3bit)
                        # の 16bit で構成されている
                        # ビット演算でサービス識別 (0~3) を取得する
                        service_type = (service_info.service_id & 0b0000000110000000) >> 7
                        # ビット演算でサービス番号 (0~7) を取得する (1~8 に直すために +1 する)
                        service_number = (service_info.service_id & 0b0000000000000111) + 1
                        # ARIB TR-B14 第五分冊 第七編 9.1.3 (d) の「3桁番号」の通りに算出する
                        service_info.channel_number = f'{(service_type * 200) + (ts_info.remote_control_key_id * 10) + service_number:03d}'
                    # BS/CS: サービス ID と同一
                    else:
                        service_info.channel_number = f'{service_info.service_id:03d}'

        # TS データが破損しているなどエラーの原因は色々考えられるが想定のしようがないので、とりあえず例外を送出しておく
        except Exception as ex:
            raise TransportStreamAnalyzeError(ex)

        # list に変換して返す
        return list(ts_infos.values())

    @staticmethod
    def __fullWidthToHalfWith(string: str | AribString) -> str:
        """
        全角英数字を半角英数字に変換する
        囲み文字の置換処理が入っていない以外は KonomiTV での実装とほぼ同じ
        ref: https://github.com/tsukumijima/KonomiTV/blob/master/server/app/utils/TSInformation.py#L79-L104

        SI に含まれている ARIB 独自の文字コードである8単位符号では半角と全角のコードポイント上の厳密な区別がなく、
        本来は MSZ (半角) と NSZ (全角) という制御コードが指定されているかで半角/全角どちらのコードポイントにマップすべきか決めるべき
        しかしデコードに利用している ariblib は MSZ / NSZ の制御コードの解釈をサポートしていないため、
        8単位符号中で2バイト文字で指定された英数字は全角、ASCII で指定された英数字は半角としてデコードされてしまう
        ただ元より EDCB は EPG のチャンネル名文字列と ChSet4/5.txt のチャンネル名文字列を一致させる必要はない設計になっているため、
        ariblib での MSZ / NSZ 制御コード対応の手間を鑑み、すべて半角に変換することとする

        Args:
            string (str | AribString): 変換前の文字列

        Returns:
            str: 変換後の文字列
        """

        # AribString になっているので明示的に str 型にキャストする
        string = str(string)

        # 全角英数を半角英数に置換
        # ref: https://github.com/ikegami-yukino/jaconv/blob/master/jaconv/conv_table.py
        zenkaku_table = (
            '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
        )
        hankaku_table = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        merged_table = dict(zip(list(zenkaku_table), list(hankaku_table)))

        # 全角記号を半角記号に置換
        symbol_zenkaku_table = '＂＃＄％＆＇（）＋，－．／：；＜＝＞［＼］＾＿｀｛｜｝　'
        symbol_hankaku_table = '"#$%&\'()+,-./:;<=>[\\]^_`{|} '
        merged_table.update(zip(list(symbol_zenkaku_table), list(symbol_hankaku_table)))
        merged_table.update(
            {
                # 一部の半角記号を全角に置換
                # 主に見栄え的な問題（全角の方が字面が良い）
                '!': '！',
                '?': '？',
                '*': '＊',
                '~': '～',
                '@': '＠',
                # シャープ → ハッシュ
                '♯': '#',
                # 波ダッシュ → 全角チルダ
                ## EDCB は ～ を全角チルダとして扱っているため、ISDBScanner でもそのように統一する
                '〜': '～',
            }
        )

        return string.translate(str.maketrans(merged_table))  # type: ignore


class TransportStreamAnalyzeError(Exception):
    """何らかの問題でトランスポートストリームの解析に失敗したときに送出される例外"""

    pass
