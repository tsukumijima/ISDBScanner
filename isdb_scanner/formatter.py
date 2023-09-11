
import copy
import csv
import json
from io import StringIO
from pathlib import Path
from ruamel.yaml import YAML
from typing import Any, cast, TypedDict

from isdb_scanner.constants import TransportStreamInfo
from isdb_scanner.constants import TransportStreamInfoList
from isdb_scanner.tuner import ISDBTuner


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
            exclude_pay_tv (bool): 有料放送 (+ショップチャンネル&QVC) を除外し、地上波と BS 無料放送のみを保存するか
        """

        self._save_file_path = save_file_path
        self._terrestrial_ts_infos = terrestrial_ts_infos
        self._bs_ts_infos = bs_ts_infos
        self._cs_ts_infos = cs_ts_infos
        self._exclude_pay_tv = exclude_pay_tv

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


    def format(self) -> str:
        """
        フォーマットを実行する (実装はサブクラスで行う)

        Returns:
            str: フォーマットされた文字列
        """

        raise NotImplementedError


    def save(self) -> str:
        """
        フォーマットを実行し、結果をファイルに保存する

        Returns:
            str: フォーマットされた文字列
        """

        formatted_str = self.format()
        with open(self._save_file_path, mode='w', encoding='utf-8') as f:
            f.write(formatted_str)

        return formatted_str


class JSONFormatter(BaseFormatter):
    """
    スキャン解析結果である TS 情報を JSON データとして保存するフォーマッター
    """


    def format(self) -> str:
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


    def format(self) -> str:
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
          use_view_flag は service_type が映像サービスの場合は 1 、それ以外は 0
          remocon_id は remote_control_key_id に対応する (リモコンキー ID が存在しないチャンネルでは 0)
        """

        # ヘッダーなし TSV (CRLF) に変換
        ## 実際のファイル書き込みは save() メソッドで行うため、ここでは StringIO に書き込む
        string_io = StringIO()
        writer = csv.writer(string_io, delimiter='\t', lineterminator='\r\n')
        for ts_infos in [terrestrial_ts_infos, bs_ts_infos, cs_ts_infos]:
            ch = 0  # 地上波・BS・CS ごとにチューナー空間が異なるので、通し番号をリセットする
            for ts_info in ts_infos:
                # 有料放送を除外する場合で、TS 内のサービスが空 (=TS内に無料放送サービスが存在しない) ならチャンネル自体を登録しない
                # (有料放送を除外する場合は、この時点ですでに各 TS 情報のサービス情報から有料放送が除外されている)
                ## 正確には有料放送の TS に無料独立データ放送が含まれる場合もあるので (WOWOW など) 、それらも除外してから判定する
                ## 独立データ放送の service_type は 0xC0 なので、それ以外のサービスが空かどうかで判定する
                if self._exclude_pay_tv is True and len([service for service in ts_info.services if service.service_type != 0xC0]) == 0:
                    continue
                for service in ts_info.services:
                    ch_name_prefix = ''
                    space = 0
                    if ts_info.broadcast_type == 'Terrestrial':
                        # 地上波
                        ch_name_prefix = 'Terrestrial'
                        space = 0
                    elif ts_info.broadcast_type == 'BS':
                        # BS
                        ch_name_prefix = 'BS'
                        space = 1
                    elif ts_info.broadcast_type == 'CS1' or ts_info.broadcast_type == 'CS2':
                        # CS
                        ch_name_prefix = 'CS'
                        space = 2
                    ch_name = f'{ch_name_prefix}:{ts_info.physical_channel}'
                    partial_flag = 1 if service.is_oneseg else 0
                    use_view_flag = 1 if service.isVideoServiceType() else 0
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

        # StringIO の先頭にシークする
        string_io.seek(0)

        # メモリ上に保存した TSV を文字列として取得して返す
        ## EDCB は UTF-8 with BOM でないと受け付けないため、先頭に BOM を付与する
        return '\ufeff' + string_io.getvalue()


class EDCBChSet5TxtFormatter(BaseFormatter):
    """
    スキャン解析結果である TS 情報を EDCB の ChSet5.txt (EDCB 全体で受信可能なチャンネル設定データ) として保存するフォーマッター
    各チューナー (BonDriver) に依存する情報は ChSet4.txt の方に書き込まれる
    """


    def format(self) -> str:
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
          epg_cap_flag と search_flag (定義のみで未使用) は service_type が映像サービスの場合は 1 、それ以外は 0
        """

        # ヘッダーなし TSV (CRLF) に変換
        ## 実際のファイル書き込みは save() メソッドで行うため、ここでは StringIO に書き込む
        string_io = StringIO()
        writer = csv.writer(string_io, delimiter='\t', lineterminator='\r\n')
        for ts_info in ts_infos:
            # 有料放送を除外する場合で、TS 内のサービスが空 (=TS内に無料放送サービスが存在しない) ならチャンネル自体を登録しない
            # (有料放送を除外する場合は、この時点ですでに各 TS 情報のサービス情報から有料放送が除外されている)
            ## 正確には有料放送の TS に無料独立データ放送が含まれる場合もあるので (WOWOW など) 、それらも除外してから判定する
            ## 独立データ放送の service_type は 0xC0 なので、それ以外のサービスが空かどうかで判定する
            if self._exclude_pay_tv is True and len([service for service in ts_info.services if service.service_type != 0xC0]) == 0:
                continue
            for service in ts_info.services:
                partial_flag = 1 if service.is_oneseg else 0
                epg_cap_flag = 1 if service.isVideoServiceType() else 0
                search_flag = 1 if service.isVideoServiceType() else 0
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

        # StringIO の先頭にシークする
        string_io.seek(0)

        # メモリ上に保存した TSV を文字列として取得して返す
        ## EDCB は UTF-8 with BOM でないと受け付けないため、先頭に BOM を付与する
        return '\ufeff' + string_io.getvalue()


class MirakurunChannel(TypedDict):
    name: str
    type: str
    channel: str
    isDisabled: bool


class MirakurunChannelsYmlFormatter(BaseFormatter):
    """
    スキャン解析結果である TS 情報を Mirakurun のチャンネル設定ファイルとして保存するフォーマッター
    """


    def __init__(self,
        save_file_path: Path,
        terrestrial_ts_infos: list[TransportStreamInfo],
        bs_ts_infos: list[TransportStreamInfo],
        cs_ts_infos: list[TransportStreamInfo],
        exclude_pay_tv: bool = False,
        recpt1_compatible: bool = False,
    ) -> None:
        """
        Args:
            save_file_path (Path): 保存先のファイルパス
            terrestrial_ts_infos (list[TransportStreamInfo]): スキャン結果の地上波の TS 情報
            bs_ts_infos (list[TransportStreamInfo]): スキャン結果の BS の TS 情報
            cs_ts_infos (list[TransportStreamInfo]): スキャン結果の CS の TS 情報
            exclude_pay_tv (bool): 有料放送 (+ショップチャンネル&QVC) を除外し、地上波と BS 無料放送のみを保存するか
            recpt1_compatible (bool): recpt1 と互換性のある物理チャンネル指定フォーマットで保存するか
        """

        self._recpt1_compatible = recpt1_compatible
        super().__init__(save_file_path, terrestrial_ts_infos, bs_ts_infos, cs_ts_infos, exclude_pay_tv)


    def format(self) -> str:
        """
        Mirakurun のチャンネル設定ファイルとしてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        # 各 TS 情報を物理チャンネル昇順でソートして結合
        ## この時点で処理対象が地上波チューナーなら BS/CS の TS 情報、衛星チューナーなら地上波の TS 情報として空のリストが渡されているはず
        terrestrial_ts_infos = sorted(self._terrestrial_ts_infos, key=lambda x: x.physical_channel)
        bs_ts_infos = sorted(self._bs_ts_infos, key=lambda x: x.physical_channel)
        cs_ts_infos = sorted(self._cs_ts_infos, key=lambda x: x.physical_channel)
        ts_infos = terrestrial_ts_infos + bs_ts_infos + cs_ts_infos

        # Mirakurun のチャンネル設定ファイル用のデータ構造に変換
        mirakurun_channels: list[MirakurunChannel] = []
        for ts_info in ts_infos:
            if ts_info.broadcast_type == 'Terrestrial':
                mirakurun_name = ts_info.network_name
                mirakurun_type = 'GR'
            else:
                mirakurun_name = ts_info.physical_channel
                mirakurun_type = 'BS' if ts_info.broadcast_type == 'BS' else 'CS'
                # 有料放送を除外する場合で、TS 内のサービスが空 (=TS内に無料放送サービスが存在しない) ならチャンネル自体を登録しない
                # (有料放送を除外する場合は、この時点ですでに各 TS 情報のサービス情報から有料放送が除外されている)
                ## 正確には有料放送の TS に無料独立データ放送が含まれる場合もあるので (WOWOW など) 、それらも除外してから判定する
                ## 独立データ放送の service_type は 0xC0 なので、それ以外のサービスが空かどうかで判定する
                if self._exclude_pay_tv is True and len([service for service in ts_info.services if service.service_type != 0xC0]) == 0:
                    continue
            if self._recpt1_compatible is True:
                # recpt1 互換の物理チャンネル指定フォーマット
                mirakurun_channel = ts_info.physical_channel_recpt1
            else:
                # recisdb 互換の物理チャンネル指定フォーマット
                mirakurun_channel = ts_info.physical_channel_recisdb
            channel: MirakurunChannel = {
                'name': mirakurun_name,
                'type': mirakurun_type,
                'channel': mirakurun_channel,
                'isDisabled': False,
            }
            mirakurun_channels.append(channel)

        # YAML に変換
        string_io = StringIO()
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.dump(mirakurun_channels, string_io)

        # StringIO の先頭にシークする
        string_io.seek(0)

        # メモリ上に保存した YAML を文字列として取得して返す
        return string_io.getvalue()


class MirakurunTuner(TypedDict):
    name: str
    types: list[str]
    command: str
    isDisabled: bool


class MirakurunTunersYmlFormatter(BaseFormatter):
    """
    取得したチューナー情報を Mirakurun のチューナー設定ファイルとして保存するフォーマッター
    """


    def __init__(self,
        save_file_path: Path,
        isdbt_tuners: list[ISDBTuner],
        isdbs_tuners: list[ISDBTuner],
        multi_tuners: list[ISDBTuner],
        recpt1_compatible: bool = False,
    ) -> None:
        """
        Args:
            save_file_path (Path): 保存先のファイルパス
            isdbt_tuners (list[ISDBTuner]): ISDB-T 専用チューナーのリスト
            isdbs_tuners (list[ISDBTuner]): ISDB-S 専用チューナーのリスト
            multi_tuners (list[ISDBTuner]): ISDB-T/S 共用チューナーのリスト
            recpt1_compatible (bool): recpt1 と互換性のある物理チャンネル指定フォーマットで保存するか
        """

        self._save_file_path = save_file_path
        self._isdbt_tuners = isdbt_tuners
        self._isdbs_tuners = isdbs_tuners
        self._multi_tuners = multi_tuners
        self._recpt1_compatible = recpt1_compatible


    def format(self) -> str:
        """
        Mirakurun のチューナー設定ファイルとしてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        def get_tuner_command(device_path: Path) -> str:
            if self._recpt1_compatible is True:
                return f'recpt1 --device {device_path} <channel> - -'
            else:
                return f'recisdb tune --device {device_path} --channel <channel> -'

        # Mirakurun のチューナー設定ファイル用のデータ構造に変換
        mirakurun_tuners: list[MirakurunTuner] = []
        for isdbt_tuner in self._isdbt_tuners:
            tuner: MirakurunTuner = {
                'name': isdbt_tuner.name,
                'types': ['GR'],
                'command': get_tuner_command(isdbt_tuner.device_path),
                'isDisabled': False,
            }
            mirakurun_tuners.append(tuner)
        for isdbs_tuner in self._isdbs_tuners:
            tuner: MirakurunTuner = {
                'name': isdbs_tuner.name,
                'types': ['BS', 'CS'],
                'command': get_tuner_command(isdbs_tuner.device_path),
                'isDisabled': False,
            }
            mirakurun_tuners.append(tuner)
        for multi_tuner in self._multi_tuners:
            tuner: MirakurunTuner = {
                'name': multi_tuner.name,
                'types': ['GR', 'BS', 'CS'],
                'command': get_tuner_command(multi_tuner.device_path),
                'isDisabled': False,
            }
            mirakurun_tuners.append(tuner)

        # YAML に変換
        string_io = StringIO()
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.dump(mirakurun_tuners, string_io)

        # StringIO の先頭にシークする
        string_io.seek(0)

        # メモリ上に保存した YAML を文字列として取得して返す
        return string_io.getvalue()


class MirakcChannel(TypedDict):
    name: str
    type: str
    channel: str
    disabled: bool

class MirakcTuner(TypedDict):
    name: str
    types: list[str]
    command: str
    disabled: bool


class MirakcConfigYmlFormatter(BaseFormatter):
    """
    取得したチューナー情報とスキャン解析結果である TS 情報を mirakc の設定ファイルとして保存するフォーマッター
    """


    def __init__(self,
        save_file_path: Path,
        isdbt_tuners: list[ISDBTuner],
        isdbs_tuners: list[ISDBTuner],
        multi_tuners: list[ISDBTuner],
        terrestrial_ts_infos: list[TransportStreamInfo],
        bs_ts_infos: list[TransportStreamInfo],
        cs_ts_infos: list[TransportStreamInfo],
        exclude_pay_tv: bool = False,
        recpt1_compatible: bool = False,
        mirakc_config_template: dict[str, Any] = {
            'server': {
                'addrs': [
                    {'http': '0.0.0.0:40772'},
                ],
            },
            'epg': {
                'cache-dir': '/var/lib/mirakc/epg',
            },
            'channels': [],
            'tuners': [],
        },
    ) -> None:
        """
        Args:
            save_file_path (Path): 保存先のファイルパス
            isdbt_tuners (list[ISDBTuner]): ISDB-T 専用チューナーのリスト
            isdbs_tuners (list[ISDBTuner]): ISDB-S 専用チューナーのリスト
            multi_tuners (list[ISDBTuner]): ISDB-T/S 共用チューナーのリスト
            terrestrial_ts_infos (list[TransportStreamInfo]): スキャン結果の地上波の TS 情報
            bs_ts_infos (list[TransportStreamInfo]): スキャン結果の BS の TS 情報
            cs_ts_infos (list[TransportStreamInfo]): スキャン結果の CS の TS 情報
            exclude_pay_tv (bool): 有料放送 (+ショップチャンネル&QVC) を除外し、地上波と BS 無料放送のみを保存するか
            recpt1_compatible (bool): recpt1 と互換性のある物理チャンネル指定フォーマットで保存するか
            mirakc_config_template (dict[str, Any]): mirakc の設定ファイルのひな形 (channels と tuners は空のリストで初期化されている必要がある)
        """

        self._isdbt_tuners = isdbt_tuners
        self._isdbs_tuners = isdbs_tuners
        self._multi_tuners = multi_tuners
        self._recpt1_compatible = recpt1_compatible
        super().__init__(save_file_path, terrestrial_ts_infos, bs_ts_infos, cs_ts_infos, exclude_pay_tv)

        assert 'channels' in mirakc_config_template and type(mirakc_config_template['channels']) is list
        assert 'tuners' in mirakc_config_template and type(mirakc_config_template['tuners']) is list
        self._mirakc_config_template = mirakc_config_template


    def format(self) -> str:
        """
        mirakc の設定ファイルとしてフォーマットする

        Returns:
            str: フォーマットされた文字列
        """

        # ひな形の設定データ
        mirakc_config = copy.deepcopy(self._mirakc_config_template)  # ひな型が変更されないようにコピーする

        # 各 TS 情報を物理チャンネル昇順でソートして結合
        ## この時点で処理対象が地上波チューナーなら BS/CS の TS 情報、衛星チューナーなら地上波の TS 情報として空のリストが渡されているはず
        terrestrial_ts_infos = sorted(self._terrestrial_ts_infos, key=lambda x: x.physical_channel)
        bs_ts_infos = sorted(self._bs_ts_infos, key=lambda x: x.physical_channel)
        cs_ts_infos = sorted(self._cs_ts_infos, key=lambda x: x.physical_channel)
        ts_infos = terrestrial_ts_infos + bs_ts_infos + cs_ts_infos

        # mirakc のチャンネル設定ファイル用のデータ構造に変換
        for ts_info in ts_infos:
            if ts_info.broadcast_type == 'Terrestrial':
                mirakc_name = ts_info.network_name
                mirakc_type = 'GR'
            else:
                mirakc_name = ts_info.physical_channel
                mirakc_type = 'BS' if ts_info.broadcast_type == 'BS' else 'CS'
                # 有料放送を除外する場合で、TS 内のサービスが空 (=TS内に無料放送サービスが存在しない) ならチャンネル自体を登録しない
                # (有料放送を除外する場合は、この時点ですでに各 TS 情報のサービス情報から有料放送が除外されている)
                ## 正確には有料放送の TS に無料独立データ放送が含まれる場合もあるので (WOWOW など) 、それらも除外してから判定する
                ## 独立データ放送の service_type は 0xC0 なので、それ以外のサービスが空かどうかで判定する
                if self._exclude_pay_tv is True and len([service for service in ts_info.services if service.service_type != 0xC0]) == 0:
                    continue
            if self._recpt1_compatible is True:
                # recpt1 互換の物理チャンネル指定フォーマット
                mirakc_channel = ts_info.physical_channel_recpt1
            else:
                # recisdb 互換の物理チャンネル指定フォーマット
                mirakc_channel = ts_info.physical_channel_recisdb
            channel: MirakcChannel = {
                'name': mirakc_name,
                'type': mirakc_type,
                'channel': mirakc_channel,
                'disabled': False,
            }
            cast(list[MirakcChannel], mirakc_config['channels']).append(channel)

        def get_tuner_command(device_path: Path) -> str:
            if self._recpt1_compatible is True:
                return f'recpt1 --device {device_path} ' + '{{{channel}}} - -'
            else:
                return f'recisdb tune --device {device_path} --channel ' + '{{{channel}}} -'

        # mirakc のチューナー設定ファイル用のデータ構造に変換
        for isdbt_tuner in self._isdbt_tuners:
            tuner: MirakcTuner = {
                'name': isdbt_tuner.name,
                'types': ['GR'],
                'command': get_tuner_command(isdbt_tuner.device_path),
                'disabled': False,
            }
            cast(list[MirakcTuner], mirakc_config['tuners']).append(tuner)
        for isdbs_tuner in self._isdbs_tuners:
            tuner: MirakcTuner = {
                'name': isdbs_tuner.name,
                'types': ['BS', 'CS'],
                'command': get_tuner_command(isdbs_tuner.device_path),
                'disabled': False,
            }
            cast(list[MirakcTuner], mirakc_config['tuners']).append(tuner)
        for multi_tuner in self._multi_tuners:
            tuner: MirakcTuner = {
                'name': multi_tuner.name,
                'types': ['GR', 'BS', 'CS'],
                'command': get_tuner_command(multi_tuner.device_path),
                'disabled': False,
            }
            cast(list[MirakcTuner], mirakc_config['tuners']).append(tuner)

        # YAML に変換
        string_io = StringIO()
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.dump(mirakc_config, string_io)

        # StringIO の先頭にシークする
        string_io.seek(0)

        # メモリ上に保存した YAML を文字列として取得して返す
        return string_io.getvalue()
