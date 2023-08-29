
import csv
import json
from io import StringIO
from pathlib import Path

from isdb_scanner.constants import TransportStreamInfo
from isdb_scanner.constants import TransportStreamInfoList


class BaseFormatter:
    """
    フォーマッターの基底クラス
    """


    def __init__(self,
        save_file_path: Path,
        terrestrial_ts_infos: list[TransportStreamInfo],
        bs_ts_infos: list[TransportStreamInfo],
        cs_ts_infos: list[TransportStreamInfo],
        exclude_pay_tv: bool = False,
    ) -> None:
        """
        Args:
            save_file_path (Path): 保存先のファイルパス
            terrestrial_ts_infos (list[TransportStreamInfo]): スキャン結果の地上波の TS 情報
            bs_ts_infos (list[TransportStreamInfo]): スキャン結果の BS の TS 情報
            cs_ts_infos (list[TransportStreamInfo]): スキャン結果の CS の TS 情報
            exclude_pay_tv (bool): 有料放送 (+ショップチャンネル&QVC) を除外するかどうか
        """

        self._save_file_path = save_file_path
        self._terrestrial_ts_infos = terrestrial_ts_infos
        self._bs_ts_infos = bs_ts_infos
        self._cs_ts_infos = cs_ts_infos

        # 与えられた TS 情報から有料放送サービスを除外
        ## 地上波は実運用上有料放送は存在しないが、念のため除外しておく
        if exclude_pay_tv is True:
            for terrestrial_ts_info in self._terrestrial_ts_infos:
                terrestrial_ts_info.services = [service for service in terrestrial_ts_info.services if service.is_free is True]
            for bs_ts_info in self._bs_ts_infos:
                bs_ts_info.services = [service for service in bs_ts_info.services if service.is_free is True]
            for cs_ts_info in self._cs_ts_infos:
                # CS はショップチャンネルと QVC 以外の全サービスが有料放送 (スカパー！) として運用されている上、
                # 無料とはいえわざわざ通販チャンネルを見る人がいるとも思えないので全てのサービスを除外する
                cs_ts_info.services = []


    def __format(self) -> str:
        """
        フォーマットを実行する (実装はサブクラスで行う)

        Returns:
            str: フォーマットされた文字列
        """

        raise NotImplementedError


    def save(self) -> str:
        """
        フォーマット結果をファイルに保存する

        Returns:
            str: フォーマットされた文字列
        """

        formatted_str = self.__format()
        with open(self._save_file_path, mode='w', encoding='utf-8') as f:
            f.write(formatted_str)

        return formatted_str


class JSONFormatter(BaseFormatter):
    """
    スキャン解析結果である TS 情報を JSON データとして保存するフォーマッター
    """


    def __format(self) -> str:
        """
        JSON データとしてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        channels_dict = {
            'Terrestrial': TransportStreamInfoList(root=self._terrestrial_ts_infos).model_dump(mode='json'),
            'BS': TransportStreamInfoList(root=self._bs_ts_infos).model_dump(mode='json'),
            'CS': TransportStreamInfoList(root=self._cs_ts_infos).model_dump(mode='json'),
        }
        formatted_str = json.dumps(channels_dict, indent=4, ensure_ascii=False)
        return formatted_str


class EDCBChSet4TxtFormatter(BaseFormatter):
    """
    スキャン解析結果である TS 情報を EDCB の ChSet4.txt (ファイル名に対応する BonDriver で受信可能なチャンネル設定データ) として保存するフォーマッター
    初期化時は保存対象の ChSet4.txt に対応する BonDriver の種別 (地上波 or 衛星 or マルチチューナー) に合わせた TS 情報のみを引数に渡すこと
    このフォーマッターで生成される ChSet4.txt は BonDriver_mirakc / BonDriver_Mirakurun 専用で、
    他 BonDriver では物理チャンネルやチューナー空間の対応を別途変更する必要がある
    """


    def __format(self) -> str:
        """
        EDCB の ChSet4.txt としてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        # 各 TS 情報を物理チャンネル昇順でソート
        ## この時点で処理対象が地上波チューナーなら BS/CS の TS 情報、衛星チューナーなら地上波の TS 情報として空のリストが渡されているはず
        terrestrial_ts_infos = sorted(self._terrestrial_ts_infos, key=lambda x: x.physical_channel)
        bs_ts_infos = sorted(self._bs_ts_infos, key=lambda x: x.physical_channel)
        cs_ts_infos = sorted(self._cs_ts_infos, key=lambda x: x.physical_channel)

        # 各トランスポートストリームのサービス情報を service_id 昇順でソート
        for ts_info in terrestrial_ts_infos:
            ts_info.services = sorted(ts_info.services, key=lambda x: x.service_id)
        for ts_info in bs_ts_infos:
            ts_info.services = sorted(ts_info.services, key=lambda x: x.service_id)
        for ts_info in cs_ts_infos:
            ts_info.services = sorted(ts_info.services, key=lambda x: x.service_id)

        """
        ChSet4.txt のフォーマット:
          ch_name, service_name, network_name, space, ch, network_id, transport_stream_id, service_id, service_type, partial_flag, use_view_flag, remocon_id
          ch_name は物理チャンネル名で任意の値でよく、ISDBScanner では物理チャンネル名をそのまま使用する
          space (チューナー空間) は BonDriver_mirakc の場合、地上波: 0, BS: 1, CS: 2
          ch (物理チャンネルに対応する BonDriver の通し番号) BonDriver_mirakc の場合、地上波・BS・CS それぞれで 0 から通し番号を振る
          partial_flag は is_oneseg に対応する (ワンセグ放送の場合は 1 、それ以外は 0)
          use_view_flag は service_type が 0x01 (映像サービス) の場合は 1 、それ以外は 0
          remocon_id は remote_control_key_id に対応する (リモコンキー ID が存在しないチャンネルでは 0)
        """

        # ヘッダーなし TSV に変換
        ## 実際のファイル書き込みは save() メソッドで行うため、ここでは StringIO に書き込む
        with StringIO() as f:
            writer = csv.writer(f, delimiter='\t', lineterminator='\n')
            for ts_infos in [terrestrial_ts_infos, bs_ts_infos, cs_ts_infos]:
                ch = 0  # 地上波・BS・CS ごとにチューナー空間が異なるので、通し番号をリセットする
                for ts_info in ts_infos:
                    for service in ts_info.services:
                        ts_name_prefix = ''
                        space = 0
                        if 0x7880 <= ts_info.network_id <= 0x7FE8:
                            # 地上波
                            ts_name_prefix = 'Terrestrial'
                            space = 0
                        elif ts_info.network_id == 4:
                            # BS
                            ts_name_prefix = 'BS'
                            space = 1
                        elif ts_info.network_id == 6 or ts_info.network_id == 7:
                            # CS
                            ts_name_prefix = 'CS'
                            space = 2
                        ch_name = f'{ts_name_prefix}:{ts_info.physical_channel}'
                        partial_flag = 1 if service.is_oneseg else 0
                        use_view_flag = 1 if service.service_type == 0x01 else 0
                        remocon_id = ts_info.remote_control_key_id if ts_info.remote_control_key_id is not None else 0
                        writer.writerow([
                            ch_name,
                            service.service_name,
                            ts_info.network_name,
                            space,
                            ch,
                            ts_info.network_id,
                            ts_info.transport_stream_id,
                            service.service_id,
                            service.service_type,
                            partial_flag,
                            use_view_flag,
                            remocon_id,
                        ])
                    ch += 1  # 0 スタートなので処理完了後にインクリメントする

            # メモリ上に保存した TSV を文字列として取得して返す
            ## EDCB は UTF-8 with BOM でないと受け付けないため、先頭に BOM を付与する
            return '\ufeff' + f.getvalue()


class EDCBChSet5TxtFormatter(BaseFormatter):
    """
    スキャン解析結果である TS 情報を EDCB の ChSet5.txt (EDCB 全体で受信可能なチャンネル設定データ) として保存するフォーマッター
    各チューナー (BonDriver) に依存する情報は ChSet4.txt の方に書き込まれる
    """


    def __format(self) -> str:
        """
        EDCB の ChSet5.txt としてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        # 地上波・BS・CS の TS 情報を結合し、network_id, transport_stream_id それぞれ昇順でソート
        ts_infos = self._terrestrial_ts_infos + self._bs_ts_infos + self._cs_ts_infos
        ts_infos = sorted(ts_infos, key=lambda x: (x.network_id, x.transport_stream_id))

        # 各トランスポートストリームのサービス情報を service_id 昇順でソート
        for ts_info in ts_infos:
            ts_info.services = sorted(ts_info.services, key=lambda x: x.service_id)

        """
        ChSet5.txt のフォーマット:
          service_name, network_name, network_id, transport_stream_id, service_id, service_type, partial_flag, epg_cap_flag, search_flag (未使用)
          partial_flag は is_oneseg に対応する (ワンセグ放送の場合は 1 、それ以外は 0)
          epg_cap_flag と search_flag (定義のみで未使用) は service_type が 0x01 (映像サービス) の場合は 1 、それ以外は 0
        """

        # ヘッダーなし TSV に変換
        ## 実際のファイル書き込みは save() メソッドで行うため、ここでは StringIO に書き込む
        with StringIO() as f:
            writer = csv.writer(f, delimiter='\t', lineterminator='\n')
            for ts_info in ts_infos:
                for service in ts_info.services:
                    partial_flag = 1 if service.is_oneseg else 0
                    epg_cap_flag = 1 if service.service_type == 0x01 else 0
                    search_flag = 1 if service.service_type == 0x01 else 0
                    writer.writerow([
                        service.service_name,
                        ts_info.network_name,
                        ts_info.network_id,
                        ts_info.transport_stream_id,
                        service.service_id,
                        service.service_type,
                        partial_flag,
                        epg_cap_flag,
                        search_flag,
                    ])

            # メモリ上に保存した TSV を文字列として取得して返す
            ## EDCB は UTF-8 with BOM でないと受け付けないため、先頭に BOM を付与する
            return '\ufeff' + f.getvalue()