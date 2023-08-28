
import json
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
        """

        self.save_file_path = save_file_path
        self.terrestrial_ts_infos = terrestrial_ts_infos
        self.bs_ts_infos = bs_ts_infos
        self.cs_ts_infos = cs_ts_infos


    def __format(self) -> str:
        """
        フォーマットを実行する (実装はサブクラスで行う)

        Returns:
            str: フォーマットされた文字列
        """

        raise NotImplementedError


    def save(self) -> None:
        """
        フォーマット結果をファイルに保存する
        """

        formatted_str = self.__format()
        with open(self.save_file_path, mode='w', encoding='utf-8') as f:
            f.write(formatted_str)


class JSONFormatter(BaseFormatter):
    """ スキャン解析結果である TS 情報を JSON データとして保存するフォーマッター """

    def __format(self) -> str:
        """
        JSON データとしてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        channels_dict = {
            'Terrestrial': TransportStreamInfoList(root=self.terrestrial_ts_infos).model_dump(mode='json'),
            'BS': TransportStreamInfoList(root=self.bs_ts_infos).model_dump(mode='json'),
            'CS': TransportStreamInfoList(root=self.cs_ts_infos).model_dump(mode='json'),
        }
        formatted_str = json.dumps(channels_dict, indent=4, ensure_ascii=False)
        return formatted_str
