
import typer

from isdb_scanner.analyzer import TransportStreamAnalyzer
from isdb_scanner.tuner import (
    ISDBTuner,
    TunerOpeningError,
    TunerOutputError,
    TunerTuningError,
)


def main():

    # 地上波のチャンネルスキャン
    isdbt_devices = ISDBTuner.getAvailableISDBSTunerDevices()
    isdbt_tuner = ISDBTuner(isdbt_devices[1], output_recisdb_log=True)

    try:
        result = isdbt_tuner.tune('CS02', tune_time=20)
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
    print(len(result))

    TransportStreamAnalyzer(result).analyze()


if __name__ == "__main__":
    typer.run(main)
