
import subprocess
import sys
import time
import typer
from pathlib import Path
from rich import print
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import TaskProgressColumn
from rich.progress import TextColumn
from rich.progress import TimeRemainingColumn
from rich.rule import Rule
from rich.style import Style

from isdb_scanner import __version__
from isdb_scanner.analyzer import TransportStreamAnalyzeError
from isdb_scanner.analyzer import TransportStreamAnalyzer
from isdb_scanner.constants import TransportStreamInfo
from isdb_scanner.formatter import EDCBChSet4TxtFormatter
from isdb_scanner.formatter import EDCBChSet5TxtFormatter
from isdb_scanner.formatter import JSONFormatter
from isdb_scanner.formatter import MirakcConfigYmlFormatter
from isdb_scanner.formatter import MirakurunChannelsYmlFormatter
from isdb_scanner.formatter import MirakurunTunersYmlFormatter
from isdb_scanner.tuner import ISDBTuner
from isdb_scanner.tuner import TunerOpeningError
from isdb_scanner.tuner import TunerOutputError
from isdb_scanner.tuner import TunerTuningError


app = typer.Typer()

@app.command(help='ISDBScanner: Scans Japanese TV broadcast channels (ISDB-T/ISDB-S) and outputs results in various formats (depends on recisdb)')
def main(
    output: Path = typer.Argument(Path('scanned/'), help='Output scan results to the specified directory.'),
    exclude_pay_tv: bool = typer.Option(False, help='Exclude pay-TV channels from scan results and include only free-to-air terrestrial and BS channels.'),
    output_recisdb_log: bool = typer.Option(False, help='Output recisdb log to stderr.'),
):

    print(Rule(
        title = f'ISDBScanner version {__version__}',
        characters='=',
        style = Style(color='#E33157'),
        align = 'center',
    ))

    # recisdb の実行ファイルがインストールされているか確認
    if subprocess.run(['/bin/bash', '-c', 'type recisdb'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print('[red]recisdb not found.[/red]')
        print('[red]Please install recisdb and try again.[/red]')
        print(Rule(characters='=', style=Style(color='#E33157')))
        return

    # 実行環境が Linux か確認
    if sys.platform != 'linux':
        print('[red]ISDBScanner only supports Linux.[/red]')
        print('[red]Please run this tool on Linux.[/red]')
        print(Rule(characters='=', style=Style(color='#E33157')))
        return

    scan_start_time = time.time()

    # トータルでスキャンする必要がある物理チャンネル数
    ## 13ch - 62ch + BS01_0 (BS) + CS02 (CS1) + CS04 (CS2)
    ## 地上波はフルスキャン、衛星放送はそれぞれのネットワークごとの最初の物理チャンネルのみをスキャン
    ## 衛星放送では同一ネットワーク内の異なるチャンネルの情報を一括で取得できるため、スキャンは 3 回のみで済む
    ## BS のデフォルト TS は運用規定で 0x40F1 (NHKBS1: BS15/TS0) だが、手元環境ではなぜか他 TS と比べ NIT の送出間隔が不安定 (?) で
    ## 20 秒程度録画しないと NIT を確実に取得できないため、ここでは BS01/TS0 (BS朝日) をスキャンする
    scan_terrestrial_physical_channels = [f'T{i}' for i in range(13, 63)]
    if exclude_pay_tv is True:
        scan_satellite_physical_channels = ['BS01_0']
    else:
        scan_satellite_physical_channels = ['BS01_0', 'CS02', 'CS04']
    total_channel_count = len(scan_terrestrial_physical_channels) + len(scan_satellite_physical_channels)

    # スキャンし終えたチャンネル数 (受信できたかは問わない)
    scanned_channel_count = -1  # 初期値は -1 で、地上波のチャンネルスキャンが始まる前に 0 になる

    # プログレスバーを開始
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=9999),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        transient=True,
    )
    task = progress.add_task("[bright_red]Scanning...", total=total_channel_count)
    with progress:

        # ***** 地上波のチャンネルスキャン *****

        print('Scanning ISDB-T (Terrestrial) channels...')

        # チューナーを取得
        print(Rule(characters='-', style=Style(color='#E33157')))
        isdbt_tuners = ISDBTuner.getAvailableISDBTTuners()
        if len(isdbt_tuners) == 0:
            print('[red]No ISDB-T tuner found.[/red]')
            print('[red]Please connect an ISDB-T tuner and try again.[/red]')
            # チューナーがないため ISDB-T のスキャン処理は実行されない (for ループがスキップされる)
            # プログレスバーはスキャンする予定だった地上波チャンネル分だけ進める
            progress.update(task, completed=len(scan_terrestrial_physical_channels))
        for isdbt_tuner in isdbt_tuners:
            print(f'Found Tuner: [green]{isdbt_tuner.name}[/green] ({isdbt_tuner.device_path})')

        # 地上波のチャンネルスキャンを実行 (13ch - 62ch)
        ## 地上波のうち 53ch - 62ch はすでに廃止されているが、依然一部ケーブルテレビのコミュニティチャンネル (自主放送) で利用されている
        tr_ts_infos: list[TransportStreamInfo] = []
        for channel in scan_terrestrial_physical_channels:
            scanned_channel_count += 1
            progress.update(task, completed=scanned_channel_count)
            try:
                for tuner in isdbt_tuners:
                    # 前回チューナーオープンに失敗したチューナーはスキップ
                    if tuner.last_tuner_opening_failed is True:
                        continue
                    # チューナーの起動と TS 解析を実行
                    print(Rule(characters='-', style=Style(color='#E33157')))
                    print(f'  Channel: [bright_blue]Terrestrial - {channel.replace("T", "")}ch[/bright_blue]')
                    print(f'    Tuner: [green]{tuner.name}[/green] ({tuner.device_path})')
                    try:
                        # 録画時間: 2.25 秒 (地上波の SI 送出間隔は最大 2 秒周期)
                        start_time = time.time()
                        try:
                            tuner.output_recisdb_log = output_recisdb_log
                            ts_stream_data = tuner.tune(channel, recording_time=2.25)
                        finally:
                            print(f'Tune Time: {time.time() - start_time:.2f} seconds')
                        # トランスポートストリームとサービスの情報を解析
                        ts_infos = TransportStreamAnalyzer(ts_stream_data, channel).analyze()
                        tr_ts_infos.extend(ts_infos)
                        for ts_info in ts_infos:
                            print(f'[green]Transport Stream[/green]: {ts_info}')
                            for service_info in ts_info.services:
                                print(f'[green]         Service[/green]: {service_info}')
                        break
                    except TunerOpeningError as ex:
                        print(f'[red]Failed to open tuner. {ex}[/red]')
                        print('[red]Trying again with the next tuner...[/red]')
                        continue
                    except TransportStreamAnalyzeError as ex:
                        print(f'[red]Failed to analyze transport stream. {ex}[/red]')
                        print('[red]Trying again with the next tuner...[/red]')
                        continue
            except TunerTuningError as ex:
                print(f'[yellow]{ex}[/yellow]')
                print('[yellow]Channel may not be received in your area. Skipping...[/yellow]')
                continue
            except TunerOutputError:
                print('[yellow]Failed to receive data.[/yellow]')
                print('[yellow]Channel may not be received in your area. Skipping...[/yellow]')
                continue

        # 地上波で同一チャンネルが重複して検出された場合の処理
        ## 居住地域によっては、複数の中継所の電波が受信できるなどの理由で、同一チャンネルが複数の物理チャンネルで受信できる場合がある
        ## 同一チャンネルが複数の物理チャンネルから受信できると誤動作の要因になるため、TSID が一致する物理チャンネルを集計し、
        ## 次にどの物理チャンネルが一番信号レベルが高いかを判定して、その物理チャンネルのみを残す
        ## (地上波の TSID は放送局ごとに全国で一意であるため、TSID が一致する物理チャンネルは同一チャンネルであることが保証される)

        # 同一 TSID を持つ物理チャンネルをグループ化
        tsid_grouped_physical_channels: dict[int, list[TransportStreamInfo]] = {}
        for ts_info in tr_ts_infos:
            if ts_info.transport_stream_id not in tsid_grouped_physical_channels:
                tsid_grouped_physical_channels[ts_info.transport_stream_id] = []
            tsid_grouped_physical_channels[ts_info.transport_stream_id].append(ts_info)

        # 同一 TSID を持つ物理チャンネルのうち、信号レベルが最も高い物理チャンネルのみを残す
        for ts_infos in tsid_grouped_physical_channels.values():

            # 同一 TSID を持つ物理チャンネルが1つだけ (正常) の場合は何もしない
            if len(ts_infos) == 1:
                continue

            print(Rule(characters='-', style=Style(color='#E33157')))
            print(f'[yellow]{ts_infos[0].network_name} (TSID: {ts_infos[0].transport_stream_id}) '
                   'was detected redundantly across multiple physical channels.[/yellow]')
            print('[yellow]Outputs only the physical channel with the highest signal level...[/yellow]')

            # それぞれの物理チャンネルの信号レベルを計測
            signal_levels: dict[str, float] = {}
            for ts_info in ts_infos:
                signal_levels[ts_info.physical_channel] = -99.99  # デフォルト値 (信号レベルを計測できなかった場合用)
                for tuner in isdbt_tuners:
                    # 前回チューナーオープンに失敗したチューナーはスキップ
                    if tuner.last_tuner_opening_failed is True:
                        continue
                    # チューナーの起動と平均信号レベル取得を実行
                    ## チューナーの起動失敗などで平均信号レベルが取得できなかった場合は None が返されるので、次のチューナーで試す
                    result = tuner.getSignalLevelMean(ts_info.physical_channel)
                    if result is None:
                        continue
                    signal_levels[ts_info.physical_channel] = result
                    print(f'Physical Channel: {ts_info.physical_channel} | Signal Level: {result:.2f} dB')
                    break  # 信号レベルが取得できたら次の物理チャンネルへ
                if signal_levels[ts_info.physical_channel] == -99.99:
                    print(f'Physical Channel: {ts_info.physical_channel} | Signal Level: Failed to get signal level')

            # 信号レベルが最も高い物理チャンネル以外の物理チャンネルを terrestrial_ts_infos から削除
            max_signal_level = max(signal_levels.values())
            for physical_channel, signal_level in signal_levels.items():
                ts_info = next(ts_info for ts_info in ts_infos if ts_info.physical_channel == physical_channel)
                if signal_level != max_signal_level:
                    tr_ts_infos.remove(ts_info)
                else:
                    print(f'[green]Selected Physical Channel: {ts_info.physical_channel} | Signal Level: {signal_level:.2f} dB[/green]')

        # 物理チャンネル順にソート
        tr_ts_infos = sorted(tr_ts_infos, key=lambda x: x.physical_channel)

        # ***** BS・CS110 のチャンネルスキャン *****

        print(Rule(characters='=', style=Style(color='#E33157')))
        print('Scanning ISDB-S (Satellite) channels...')

        # チューナーを取得
        print(Rule(characters='-', style=Style(color='#E33157')))
        isdbs_tuners = ISDBTuner.getAvailableISDBSTuners()
        if len(isdbt_tuners) == 0:
            print('[red]No ISDB-S tuner found.[/red]')
            print('[red]Please connect an ISDB-S tuner and try again.[/red]')
            # チューナーがないため ISDB-S のスキャン処理は実行されない (for ループがスキップされる)
            # プログレスバーはスキャンする予定だった BS・CS110 チャンネル分だけ進める
            progress.update(task, completed=len(scan_terrestrial_physical_channels) + len(scan_satellite_physical_channels))
        for isdbs_tuner in isdbs_tuners:
            print(f'Found Tuner: [green]{isdbs_tuner.name}[/green] ({isdbs_tuner.device_path})')

        # BS・CS1・CS2 のチャンネルスキャンを実行
        bs_ts_infos: list[TransportStreamInfo] = []
        cs_ts_infos: list[TransportStreamInfo] = []
        for channel in scan_satellite_physical_channels:
            scanned_channel_count += 1
            progress.update(task, completed=scanned_channel_count)
            for tuner in isdbs_tuners:
                # 前回チューナーオープンに失敗したチューナーはスキップ
                if tuner.last_tuner_opening_failed is True:
                    continue
                # チューナーの起動と TS 解析を実行
                channel_type = 'BS' if channel.startswith('BS') else ('CS1' if channel.startswith('CS02') else 'CS2')
                print(Rule(characters='-', style=Style(color='#E33157')))
                print(f' Channel: [bright_blue]{channel_type} (All channels)[/bright_blue]')
                print(f'   Tuner: [green]{tuner.name}[/green] ({tuner.device_path})')
                try:
                    # 録画時間: 11 秒 (BS・CS110 の SI 送出間隔は最大 10 秒周期)
                    start_time = time.time()
                    try:
                        tuner.output_recisdb_log = output_recisdb_log
                        ts_stream_data = tuner.tune(channel, recording_time=11)
                    finally:
                        print(f'Tune Time: {time.time() - start_time:.2f} seconds')
                    # トランスポートストリームとサービスの情報を解析
                    ts_infos = TransportStreamAnalyzer(ts_stream_data, channel).analyze()
                    if channel.startswith('BS'):
                        bs_ts_infos.extend(ts_infos)
                    elif channel.startswith('CS'):
                        cs_ts_infos.extend(ts_infos)
                    for ts_info in ts_infos:
                        print(f'[green]Transport Stream[/green]: {ts_info}')
                        for service_info in ts_info.services:
                            print(f'[green]         Service[/green]: {service_info}')
                    break
                except TunerOpeningError as ex:
                    print(f'[red]Failed to open tuner. {ex}[/red]')
                    print('[red]Trying again with the next tuner...[/red]')
                    continue
                except TunerTuningError as ex:
                    print(f'[red]{ex}[/red]')
                    print('[red]Trying again with the next tuner...[/red]')
                    continue
                except TunerOutputError:
                    print('[red]Failed to receive data.[/red]')
                    print('[red]Trying again with the next tuner...[/red]')
                    continue
                except TransportStreamAnalyzeError as ex:
                    print(f'[red]Failed to analyze transport stream. {ex}[/red]')
                    print('[red]Trying again with the next tuner...[/red]')
                    continue

        # 物理チャンネル順にソート
        bs_ts_infos = sorted(bs_ts_infos, key=lambda x: x.physical_channel)
        cs_ts_infos = sorted(cs_ts_infos, key=lambda x: x.physical_channel)

        progress.update(task, completed=total_channel_count)

    # 出力先ディレクトリがなければ作成
    # 事前に絶対パスに変換しておく
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'EDCB-Wine').mkdir(parents=True, exist_ok=True)
    (output / 'Mirakurun').mkdir(parents=True, exist_ok=True)
    (output / 'mirakc').mkdir(parents=True, exist_ok=True)

    # ISDB-T 専用チューナー・ISDB-S 専用チューナー・ISDB-T/S 共用チューナーを取得
    available_isdbt_tuners = ISDBTuner.getAvailableISDBTOnlyTuners()
    available_isdbs_tuners = ISDBTuner.getAvailableISDBSOnlyTuners()
    available_multi_tuners = ISDBTuner.getAvailableMultiTuners()

    # チャンネルスキャン結果 (&一部のフォーマットでは利用可能なチューナー情報も) を様々なフォーマットで保存
    ## JSON のみ常に取得した全チャンネルを出力
    JSONFormatter(
        output / 'Channels.json',
        tr_ts_infos, bs_ts_infos, cs_ts_infos,
        exclude_pay_tv = False).save()
    EDCBChSet4TxtFormatter(
        output / 'EDCB-Wine/BonDriver_mirakc(BonDriver_mirakc).ChSet4.txt',
        tr_ts_infos, bs_ts_infos, cs_ts_infos,
        exclude_pay_tv).save()
    EDCBChSet4TxtFormatter(
        output / 'EDCB-Wine/BonDriver_mirakc_T(BonDriver_mirakc).ChSet4.txt',
        tr_ts_infos, [], [],
        exclude_pay_tv).save()
    EDCBChSet4TxtFormatter(
        output / 'EDCB-Wine/BonDriver_mirakc_S(BonDriver_mirakc).ChSet4.txt',
        [], bs_ts_infos, cs_ts_infos,
        exclude_pay_tv).save()
    EDCBChSet5TxtFormatter(
        output / 'EDCB-Wine/ChSet5.txt',
        tr_ts_infos, bs_ts_infos, cs_ts_infos,
        exclude_pay_tv).save()
    MirakurunChannelsYmlFormatter(
        output / 'Mirakurun/channels.yml',
        tr_ts_infos, bs_ts_infos, cs_ts_infos,
        exclude_pay_tv).save()
    MirakurunChannelsYmlFormatter(
        output / 'Mirakurun/channels_recpt1.yml',
        tr_ts_infos, bs_ts_infos, cs_ts_infos,
        exclude_pay_tv, recpt1_compatible = True).save()
    MirakurunTunersYmlFormatter(
        output / 'Mirakurun/tuners.yml',
        available_isdbt_tuners, available_isdbs_tuners, available_multi_tuners).save()
    MirakurunTunersYmlFormatter(
        output / 'Mirakurun/tuners_recpt1.yml',
        available_isdbt_tuners, available_isdbs_tuners, available_multi_tuners,
        recpt1_compatible = True).save()
    MirakcConfigYmlFormatter(
        output / 'mirakc/config.yml',
        available_isdbt_tuners, available_isdbs_tuners, available_multi_tuners,
        tr_ts_infos, bs_ts_infos, cs_ts_infos,
        exclude_pay_tv).save()
    MirakcConfigYmlFormatter(
        output / 'mirakc/config_recpt1.yml',
        available_isdbt_tuners, available_isdbs_tuners, available_multi_tuners,
        tr_ts_infos, bs_ts_infos, cs_ts_infos,
        exclude_pay_tv, recpt1_compatible = True).save()

    print(Rule(characters='=', style=Style(color='#E33157')))
    print(f'Finished in {time.time() - scan_start_time:.2f} seconds.')
    print(Rule(characters='=', style=Style(color='#E33157')))


if __name__ == "__main__":
    app()
