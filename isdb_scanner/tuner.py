
from __future__ import annotations

import re
import signal
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

from isdb_scanner.constants import (
    ISDBT_TUNER_DEVICE_PATHS,
    ISDBS_TUNER_DEVICE_PATHS,
    ISDB_MULTI_TUNER_DEVICE_PATHS,
)


class ISDBTuner:
    """ ISDB-T/S チューナーデバイスを操作するクラス (recisdb のラッパー) """

    # 検出可能とする信号レベル (dB)
    ## TVTest のデフォルト値と同一
    SIGNAL_LEVEL_THRESHOLD = 7.0


    def __init__(self, device_path: Path, output_recisdb_log: bool = False) -> None:
        """
        ISDBTuner を初期化する

        Args:
            device_path (Path): デバイスファイルのパス
            output_recisdb_log (bool, optional): recisdb のログを出力するかどうか. Defaults to False.
        """

        self.device_path = device_path
        self.output_recisdb_log = output_recisdb_log


    def tune(self, physical_channel: str, tune_time: float = 10.0) -> bytearray:
        """
        チューナーデバイスから指定された物理チャンネルを受信する
        選局/受信できなかった場合は例外を送出する

        Args:
            physical_channel (str): 物理チャンネル (ex: "T13", "BS23_3", "CS04")
            tune_time (float, optional): 受信時間 (秒). Defaults to 10.0.

        Returns:
            bytearray: 受信したデータ

        Raises:
            TunerOpeningError: チューナーをオープンできなかった場合
            TunerTuningError: チャンネルを選局できなかった場合
            TunerOutputError: 受信したデータが小さすぎる場合
        """

        # recisdb (チューナープロセス) を起動
        process = subprocess.Popen(
            ['recisdb', 'tune', '--device', str(self.device_path), '--channel', physical_channel, '-'],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
        )

        # 標準出力と標準エラー出力を別スレッドで読み込む
        stdout: bytearray = bytearray()
        def stdout_thread_func():
            nonlocal stdout
            assert process.stdout is not None
            while True:
                data = process.stdout.read(188)
                if len(data) == 0:
                    break
                stdout.extend(data)
        stderr: bytes = b''
        def stderr_thread_func():
            nonlocal stderr
            assert process.stderr is not None
            while True:
                data = process.stderr.read(1)
                if len(data) == 0:
                    break
                stderr += data
                if self.output_recisdb_log is True:
                    sys.stderr.buffer.write(data)
                    sys.stderr.buffer.flush()
        stdout_thread = threading.Thread(target=stdout_thread_func)
        stderr_thread = threading.Thread(target=stderr_thread_func)

        # スレッドを開始し、タイムアウト秒数に達するまで待機
        # タイムアウト秒数経過後にプロセスに SIGINT を送る必要があるので、標準出力のみ join する
        stdout_thread.start()
        stderr_thread.start()
        stdout_thread.join(timeout=tune_time)

        # 最大でもタイムアウト秒数に達しているはずなので、プロセスを終了 (Ctrl+C を送信)
        process.send_signal(signal.SIGINT)

        # プロセスと標準エラー出力スレッドの終了を待機
        process.wait()
        stderr_thread.join()

        # この時点でリターンコードが 0 でなければ選局または受信に失敗している
        if process.returncode != 0:

            # エラメッセージを正規表現で取得
            result = re.search(r'ERROR:\s+(.+)', stderr.decode('utf-8'))
            if result is not None:
                error_message = result.group(1)
            else:
                error_message = 'Unknown error'

            # チューナーオープン時のエラー
            if error_message in [
                'The tuner device does not exist.',
                'The tuner device is already in use.',
                'he tuner device is busy.',
            ] or error_message.startswith('Cannot open the device.'):
                raise TunerOpeningError(error_message)

            # それ以外は選局/受信時のエラーと判断
            raise TunerTuningError(error_message)

        # 受信していれば（チューナーオープン時間を含めても）100KB 以上のデータが得られるはず
        # それ未満の場合は選局に失敗している
        if len(stdout) < 100 * 1024:
            raise TunerOutputError('The tuner output is too small.')

        # 受信したデータを返す
        return stdout


    def checkSignal(self, physical_channel: str) -> tuple[subprocess.Popen[bytes], Iterator[float]]:
        """
        チューナーデバイスから指定された物理チャンネルを受信し、イテレータで信号レベルを返す
        この関数はイテレータを呼び終わってもプロセスを終了しないので、呼び出し側で明示的にプロセスを終了する必要がある

        Args:
            physical_channel (str): 物理チャンネル (ex: "T13", "BS23_3", "CS04")

        Returns:
            tuple[subprocess.Popen, Iterator[float]]: チューナープロセスと信号レベルを返すイテレータ
        """

        # recisdb (チューナープロセス) を起動
        process = subprocess.Popen(
            ['recisdb', 'checksignal', '--device', str(self.device_path), '--channel', physical_channel],
            stdout = subprocess.PIPE,
            stderr = None if self.output_recisdb_log is True else subprocess.DEVNULL,
        )

        # 標準出力に一行ずつ受信感度が "30.00dB" のように出力されるので、随時パースしてイテレータで返す
        ## 選局/受信に失敗したか、あるいはユーザーが手動でプロセスを終了させた場合は StopIteration が発生する
        def iterator() -> Iterator[float]:
            assert process.stdout is not None
            for line in process.stdout:

                # プロセスが終了していたら終了
                if line == b'' or process.poll() is not None:
                    process.send_signal(signal.SIGINT)
                    process.wait()
                    break

                # 信号レベルをパースして随時返す
                result = re.search(r'(\d+\.\d+)dB', line.decode('utf-8'))
                if result is None:
                    continue
                yield float(result.group(1))

        return process, iterator()


    def checkSignalMean(self, physical_channel: str) -> float | None:
        """
        チューナーデバイスから指定された物理チャンネルを受信し、5回の平均信号レベルを返す

        Args:
            physical_channel (str): 物理チャンネル (ex: "T13", "BS23_3", "CS04")

        Returns:
            float | None: 平均信号レベル (選局失敗時は None)
        """

        # 信号レベルを取得するイテレータを取得
        process, iterator = self.checkSignal(physical_channel)

        # 5回分の信号レベルを取得
        # もし信号レベルの取得中にプロセスが終了した場合は選局に失敗しているので None を返す
        try:
            signal_levels = [next(iterator) for _ in range(5)]
        except StopIteration:
            return None

        # プロセスを終了
        process.send_signal(signal.SIGINT)
        process.wait()

        # 平均信号レベルを返す
        return sum(signal_levels) / len(signal_levels)


    @staticmethod
    def getAvailableISDBTTuners() -> list[ISDBTuner]:
        """
        利用可能な ISDB-T チューナーのリストを取得する
        ISDB-T 専用チューナーと ISDB-T/S 共用チューナーの両方が含まれる

        Returns:
            list[ISDBTuner]: 利用可能な ISDB-T チューナーのリスト
        """

        # 存在するデバイスのパスを取得し、ISDBTuner を初期化してリストに追加
        tuners: list[ISDBTuner] = []
        for device_path in [*ISDBT_TUNER_DEVICE_PATHS, *ISDB_MULTI_TUNER_DEVICE_PATHS]:
            device_path = Path(device_path)
            if not device_path.exists():
                continue
            tuners.append(ISDBTuner(device_path))

        return tuners


    @staticmethod
    def getAvailableISDBSTuners() -> list[ISDBTuner]:
        """
        利用可能な ISDB-S チューナーのリストを取得する
        ISDB-S 専用チューナーと ISDB-T/S 共用チューナーの両方が含まれる

        Returns:
            list[ISDBTuner]: 利用可能な ISDB-S チューナーのリスト
        """

        # 存在するデバイスのパスを取得し、ISDBTuner を初期化してリストに追加
        tuners: list[ISDBTuner] = []
        for device_path in [*ISDBS_TUNER_DEVICE_PATHS, *ISDB_MULTI_TUNER_DEVICE_PATHS]:
            device_path = Path(device_path)
            if not device_path.exists():
                continue
            tuners.append(ISDBTuner(device_path))

        return tuners


class TunerOpeningError(Exception):
    """ チューナーのオープンに失敗したことを表す例外 """
    pass


class TunerTuningError(Exception):
    """ チューナーの選局に失敗したことを表す例外 """
    pass


class TunerOutputError(Exception):
    """ チューナーから出力されたデータが不正なことを表す例外 """
    pass
