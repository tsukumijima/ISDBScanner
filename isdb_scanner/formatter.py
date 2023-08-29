
import csv
import json
from io import StringIO
from pathlib import Path

from isdb_scanner.constants import TransportStreamInfo
from isdb_scanner.constants import TransportStreamInfoList


class BaseFormatter:
    """ フォーマッターの基底クラス """

    def __init__(self,
        save_file_path: Path,
        terrestrial_ts_infos: list[TransportStreamInfo],
        bs_ts_infos: list[TransportStreamInfo],
        cs_ts_infos: list[TransportStreamInfo],
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
        for terrestrial_ts_info in self._terrestrial_ts_infos:
            terrestrial_ts_info.services = [service for service in terrestrial_ts_info.services if service.is_free is True]
        for bs_ts_info in self._bs_ts_infos:
            bs_ts_info.services = [service for service in bs_ts_info.services if service.is_free is True]
        for cs_ts_info in self._cs_ts_infos:
            # CS はショップチャンネルと QVC 以外は全部有料放送 (スカパー) になっていて、
            # わざわざ通販チャンネルを見る人がいるとも思えないので全てのサービスを除外する
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
    """ スキャン解析結果である TS 情報を JSON データとして保存するフォーマッター """

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


class EDCBChSet5TxtFormatter(BaseFormatter):
    """ スキャン解析結果である TS 情報を EDCB の ChSet5.txt として保存するフォーマッター """

    def __format(self) -> str:
        """
        EDCB の ChSet5.txt としてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        # 地上波・BS・CS のチャンネル情報を結合し、network_id, transport_stream_id それぞれ昇順でソート
        ts_infos = self._terrestrial_ts_infos + self._bs_ts_infos + self._cs_ts_infos
        ts_infos = sorted(ts_infos, key=lambda x: (x.network_id, x.transport_stream_id))

        # 各トランスポートストリームのサービス情報を service_id 昇順でソート
        for ts_info in ts_infos:
            ts_info.services = sorted(ts_info.services, key=lambda x: x.service_id)

        # ヘッダーなし TSV に変換
        ## フォーマット: service_name, network_name, network_id, transport_stream_id, service_id, service_type, partial_flag, epg_cap_flag, search_flag (未使用)
        ## EDCB での partial_flag は is_oneseg に対応する (ワンセグ放送の場合は 1 、それ以外は 0)
        ## epg_cap_flag と search_flag (定義のみで未使用) は service_type が 0x01 (映像サービス) の場合は 1 、それ以外は 0
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
            return f.getvalue()

