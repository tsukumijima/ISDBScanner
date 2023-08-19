
import typer
from rich import print
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

    # ***** 地上波のチャンネルスキャン *****

    print('Scanning ISDB-T (Terrestrial) channels...')

    # チューナーを取得
    print(Rule(characters='-', style=Style(color='#E33157')))
    isdbt_tuners = ISDBTuner.getAvailableISDBTTuners()
    for isdbt_tuner in isdbt_tuners:
        print(f'Found Tuner: {isdbt_tuner.device_path}')

    # 地上波のチャンネルスキャンを実行 (T13 - T62)
    terrestrial_ts_infos: list[TransportStreamInfo] = []
    for channel in [f"T{i}" for i in range(13, 63)]:  # T13 - T62
        try:
            for tuner in isdbt_tuners:
                print(Rule(characters='-', style=Style(color='#E33157')))
                print(f'Channel: [bright_green]Terrestrial - {channel}[/bright_green]')
                print(f'Tuner: {tuner.device_path}')
                try:
                    tuner.output_recisdb_log = output_recisdb_log
                    ts_stream_data = tuner.tune(channel, tune_time=10)
                    ts_infos = TransportStreamAnalyzer(ts_stream_data, channel).analyze()
                    terrestrial_ts_infos.extend(ts_infos)
                    for ts_info in ts_infos:
                        for service in ts_info.services:
                            print(f'[green]Found Channel: {service.service_name}[/green]')
                    print(ts_infos)
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
            print(f'[yellow]Failed to tune channel. {ex}[/yellow]')
            print('[yellow]Channel may not be received in your area. Skipping...[/yellow]')
            continue
        except TunerOutputError:
            print('[yellow]Failed to receive data.[/yellow]')
            print('[yellow]Channel may not be received in your area. Skipping...[/yellow]')
            continue

    # 物理チャンネル順にソート
    terrestrial_ts_infos = sorted(terrestrial_ts_infos, key=lambda x: x.physical_channel)

    print(Rule(characters='-', style=Style(color='#E33157')))
    print(terrestrial_ts_infos)
    print(Rule(characters='=', style=Style(color='#E33157')))

    # ***** BS・CS110 のチャンネルスキャン *****

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
        for tuner in isdbs_tuners:
            print(Rule(characters='-', style=Style(color='#E33157')))
            channel_type = 'BS' if channel.startswith('BS') else ('CS1' if channel.startswith('CS02') else 'CS2')
            print(f'Channel: [bright_green]{channel_type} - {channel.replace("_", "/TS")}[/bright_green]')
            print(f'Tuner: {tuner.device_path}')
            try:
                tuner.output_recisdb_log = output_recisdb_log
                ts_stream_data = tuner.tune(channel, tune_time=20)
                ts_infos = TransportStreamAnalyzer(ts_stream_data, channel).analyze()
                if channel.startswith('BS'):
                    bs_ts_infos.extend(ts_infos)
                elif channel.startswith('CS'):
                    cs_ts_infos.extend(ts_infos)
                for ts_info in ts_infos:
                    for service in ts_info.services:
                        print(f'[green]Found Channel: {service.service_name}[/green]')
                print(ts_infos)
                break
            except TunerOpeningError as ex:
                print(f'[red]Failed to open tuner. {ex}[/red]')
                print('[red]Trying again with the next tuner...[/red]')
                continue
            except TunerTuningError as ex:
                print(f'[red]Failed to tune channel. {ex}[/red]')
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

    print(Rule(characters='=', style=Style(color='#E33157')))

    with open('terrestrial.json', 'w') as f:
        f.write(TransportStreamInfoList(root=terrestrial_ts_infos).model_dump_json(indent=4))
    with open('bs.json', 'w') as f:
        f.write(TransportStreamInfoList(root=bs_ts_infos).model_dump_json(indent=4))
    with open('cs.json', 'w') as f:
        f.write(TransportStreamInfoList(root=cs_ts_infos).model_dump_json(indent=4))


if __name__ == "__main__":
    app()
