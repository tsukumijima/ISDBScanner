
import typer

from TSChannelScanner.tuner import ISDBTuner, TunerOpeningError, TunerTuningError, TunerOutputError


def main():

    # 地上波のチャンネルスキャン
    isdbt_devices = ISDBTuner.getAvailableISDBTTunerDevices()
    isdbt_tuner = ISDBTuner(isdbt_devices[0], output_recisdb_log=True)

    try:
        result = isdbt_tuner.tune('T30')
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


if __name__ == "__main__":
    typer.run(main)
