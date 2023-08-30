
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
from isdb_scanner.tuner import ISDBTuner
from isdb_scanner.tuner import TunerOpeningError
from isdb_scanner.tuner import TunerOutputError
from isdb_scanner.tuner import TunerTuningError


app = typer.Typer()

@app.command(help='ISDBScanner: Scans Japanese TV broadcast channels (ISDB-T/ISDB-S) and outputs results in various formats')
def main(
    exclude_pay_tv: bool = typer.Option(False, help='Exclude pay-TV channels from scan results and include only free-to-air terrestrial and BS channels.'),
    output_recisdb_log: bool = typer.Option(False, help='Output recisdb log to stdout.'),
):

    print(Rule(
        title = f'ISDBScanner version {__version__}',
        characters='=',
        style = Style(color='#E33157'),
        align = 'center',
    ))

    scan_start_time = time.time()

    # トータルでスキャンする必要がある物理チャンネル数
    ## 13ch - 62ch + BS01_0 (BS) + CS02 (CS1) + CS04 (CS2)
    ## 地上波はフルスキャン、衛星放送はそれぞれのネットワークごとの最初の物理チャンネルのみをスキャン
    ## 衛星放送では同一ネットワーク内の異なるチャンネルの情報を一括で取得できるため、スキャンは 3 回のみで済む
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
            print(f'Found Tuner: {isdbt_tuner.device_path}')

        # チューナーのブラックリスト
        ## TunerOpeningError が発生した場合に、そのチューナーをブラックリストに追加する
        black_list_tuners: list[ISDBTuner] = []

        # 地上波のチャンネルスキャンを実行 (13ch - 62ch)
        ## 地上波のうち 53ch - 62ch はすでに廃止されているが、依然一部ケーブルテレビのコミュニティチャンネル (自主放送) で利用されている
        terrestrial_ts_infos: list[TransportStreamInfo] = []
        for channel in scan_terrestrial_physical_channels:
            scanned_channel_count += 1
            progress.update(task, completed=scanned_channel_count)
            try:
                for tuner in isdbt_tuners:
                    # ブラックリストに登録されているチューナーはスキップ
                    if tuner in black_list_tuners:
                        continue
                    # チューナーの起動と TS 解析を実行
                    print(Rule(characters='-', style=Style(color='#E33157')))
                    print(f'Channel: [bright_blue]Terrestrial - {channel.replace("T", "")}ch[/bright_blue]')
                    print(f'Tuner: {tuner.device_path}')
                    try:
                        # 録画時間: 2.25 秒 (地上波の SI 送出間隔は最大 2 秒周期)
                        start_time = time.time()
                        try:
                            tuner.output_recisdb_log = output_recisdb_log
                            ts_stream_data = tuner.tune(channel, recording_time=2.25)
                        finally:
                            print(f'Tuning time: {time.time() - start_time:.2f} seconds')
                        # トランスポートストリームとサービスの情報を解析
                        ts_infos = TransportStreamAnalyzer(ts_stream_data, channel).analyze()
                        terrestrial_ts_infos.extend(ts_infos)
                        for ts_info in ts_infos:
                            print(f'[green]Transport Stream[/green]: {ts_info}')
                            for service_info in ts_info.services:
                                print(f'[green]         Service[/green]: {service_info}')
                        break
                    except TunerOpeningError as ex:
                        black_list_tuners.append(tuner)
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

        # 物理チャンネル順にソート
        terrestrial_ts_infos = sorted(terrestrial_ts_infos, key=lambda x: x.physical_channel)

        # TODO: 重複するチャンネルが検出された場合の処理

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
            print(f'Found Tuner: {isdbs_tuner.device_path}')

        # BS・CS1・CS2 のチャンネルスキャンを実行
        bs_ts_infos: list[TransportStreamInfo] = []
        cs_ts_infos: list[TransportStreamInfo] = []
        for channel in scan_satellite_physical_channels:
            scanned_channel_count += 1
            progress.update(task, completed=scanned_channel_count)
            for tuner in isdbs_tuners:
                # ブラックリストに登録されているチューナーはスキップ
                if tuner in black_list_tuners:
                    continue
                # チューナーの起動と TS 解析を実行
                channel_type = 'BS' if channel.startswith('BS') else ('CS1' if channel.startswith('CS02') else 'CS2')
                print(Rule(characters='-', style=Style(color='#E33157')))
                print(f'Channel: [bright_blue]{channel_type} (All channels)[/bright_blue]')
                print(f'Tuner: {tuner.device_path}')
                try:
                    # 録画時間: 10.25 秒 (BS・CS110 の SI 送出間隔は最大 10 秒周期)
                    start_time = time.time()
                    try:
                        tuner.output_recisdb_log = output_recisdb_log
                        ts_stream_data = tuner.tune(channel, recording_time=10.25)
                    finally:
                        print(f'Tuning time: {time.time() - start_time:.2f} seconds')
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
                    black_list_tuners.append(tuner)
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

    # チャンネルスキャン結果を様々なフォーマットで保存
    JSONFormatter(Path('Channels.json'), terrestrial_ts_infos, bs_ts_infos, cs_ts_infos, exclude_pay_tv).save()
    EDCBChSet4TxtFormatter(Path('BonDriver_mirakc.ChSet4.txt'), terrestrial_ts_infos, bs_ts_infos, cs_ts_infos, exclude_pay_tv).save()
    EDCBChSet4TxtFormatter(Path('BonDriver_mirakc_T.ChSet4.txt'), terrestrial_ts_infos, [], [], exclude_pay_tv).save()
    EDCBChSet4TxtFormatter(Path('BonDriver_mirakc_S.ChSet4.txt'), [], bs_ts_infos, cs_ts_infos, exclude_pay_tv).save()
    EDCBChSet5TxtFormatter(Path('ChSet5.txt'), terrestrial_ts_infos, bs_ts_infos, cs_ts_infos, exclude_pay_tv).save()

    print(Rule(characters='=', style=Style(color='#E33157')))
    print(f'Finished in {time.time() - scan_start_time:.2f} seconds.')
    print(Rule(characters='=', style=Style(color='#E33157')))


if __name__ == "__main__":
    app()
