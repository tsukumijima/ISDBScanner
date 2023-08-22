
import json
import time
import typer
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
from isdb_scanner.constants import TransportStreamInfoList
from isdb_scanner.tuner import ISDBTuner
from isdb_scanner.tuner import TunerOpeningError
from isdb_scanner.tuner import TunerOutputError
from isdb_scanner.tuner import TunerTuningError


app = typer.Typer()

@app.command(help='ISDBScanner')
def main(
    output_recisdb_log: bool = typer.Option(False, help='Output recisdb log to stdout. (default: False)'),
):

    print(Rule(
        title = f'ISDBScanner version {__version__}',
        characters='=',
        style = Style(color='#E33157'),
        align = 'center',
    ))

    start_time = time.time()

    # トータルでスキャンする必要があるチャンネル数
    total_channel_count = len([f'T{i}' for i in range(13, 63)]) + 3  # 13ch - 62ch + BS01_0 (BS) + CS02 (CS1) + CS04 (CS2)

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
        for isdbt_tuner in isdbt_tuners:
            print(f'Found Tuner: {isdbt_tuner.device_path}')

        # チューナーのブラックリスト
        ## TunerOpeningError が発生した場合に、そのチューナーをブラックリストに追加する
        black_list_tuners: list[ISDBTuner] = []

        # 地上波のチャンネルスキャンを実行 (13ch - 62ch)
        ## 地上波のうち 53ch - 62ch はすでに廃止されているが、依然一部ケーブルテレビのコミュニティチャンネル (自主放送) で利用されている
        terrestrial_ts_infos: list[TransportStreamInfo] = []
        for channel in [f'T{i}' for i in range(13, 63)]:  # 13ch - 62ch
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
                        tuner.output_recisdb_log = output_recisdb_log
                        ts_stream_data = tuner.tune(channel, recording_time=4)  # 地上波の SI 送出間隔は最大 2 秒周期なので 4 秒で十分
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
        for isdbs_tuner in isdbs_tuners:
            print(f'Found Tuner: {isdbs_tuner.device_path}')

        # BS・CS1・CS2 のチャンネルスキャンを実行
        bs_ts_infos: list[TransportStreamInfo] = []
        cs_ts_infos: list[TransportStreamInfo] = []
        for channel in ['BS01_0', 'CS02', 'CS04']:  # それぞれのネットワークごとの最初の物理チャンネル
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
                    tuner.output_recisdb_log = output_recisdb_log
                    ts_stream_data = tuner.tune(channel, recording_time=20)  # BS・CS110 の SI 送出間隔は最大 10 秒周期 (余裕を持って 20 秒)
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

    # チャンネルスキャン結果を Channels.json に保存
    channels_dict = {
        'Terrestrial': TransportStreamInfoList(root=terrestrial_ts_infos).model_dump(mode='json'),
        'BS': TransportStreamInfoList(root=bs_ts_infos).model_dump(mode='json'),
        'CS': TransportStreamInfoList(root=cs_ts_infos).model_dump(mode='json'),
    }
    with open('Channels.json', 'w') as fp:
        json.dump(channels_dict, fp, indent=4, ensure_ascii=False)

    print(Rule(characters='=', style=Style(color='#E33157')))
    print(f'Finished in {time.time() - start_time:.2f} seconds.')
    print(Rule(characters='=', style=Style(color='#E33157')))


if __name__ == "__main__":
    app()
