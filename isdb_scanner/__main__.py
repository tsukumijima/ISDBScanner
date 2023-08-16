
import typer

from isdb_scanner.analyzer import TransportStreamAnalyzer
from isdb_scanner.tuner import (
    ISDBTuner,
    TunerOpeningError,
    TunerOutputError,
    TunerTuningError,
)


def main():

    tuners = ISDBTuner.getAvailableISDBTTuners()

    physical_channel = 'T27'

    try:
        ts_stream_data = tuners[0].tune(physical_channel, tune_time=10)
    except TunerOpeningError as ex:
        print(f'チューナーのオープンに失敗しました。({ex})')
        return
    except TunerTuningError as ex:
        print(f'チャンネルのチューニングに失敗しました。({ex})')
        return
    except TunerOutputError as ex:
        print(f'チャンネルの出力に失敗しました。({ex})')
        return
    print('チャンネルスキャン成功')
    print(len(ts_stream_data))

    TransportStreamAnalyzer(ts_stream_data, physical_channel).analyze()


if __name__ == "__main__":
    typer.run(main)
