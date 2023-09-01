
from __future__ import annotations

import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from isdb_scanner.constants import (
    ISDBT_TUNER_DEVICE_PATHS,
    ISDBS_TUNER_DEVICE_PATHS,
    ISDB_MULTI_TUNER_DEVICE_PATHS,
)


class ISDBTuner:
    """ ISDB-T/S チューナーデバイスを操作するクラス (recisdb のラッパー) """


    def __init__(self, device_path: Path, output_recisdb_log: bool = False) -> None:
        """
        ISDBTuner を初期化する

        Args:
            device_path (Path): デバイスファイルのパス
            output_recisdb_log (bool, optional): recisdb のログを出力するかどうか. Defaults to False.
        """

        self.device_path = device_path
        self.output_recisdb_log = output_recisdb_log
        self.type, self.name = self.__getTunerDeviceInfo()


    def __getPX4VideoDeviceTypeAndIndex(self) -> tuple[Literal['Terrestrial', 'Satellite'], int]:
        """
        /dev/px4videoX の X の部分を取得して、チューナーの種類と番号を返す

        Returns:
            tuple[Literal['Terrestrial', 'Satellite'], int]: チューナーの種類と番号
        """

        # デバイスパスから数字部分を抽出
        device_number = int(str(self.device_path).split('px4video')[-1])

        # デバイスタイプとインデックスを自動判定
        # ISDB-T: 2,3,6,7,10,11,14,15 ... (2個おき)
        # ISDB-S: 0,1,4,5,8,9,12,13 ... (2個おき)
        remainder = device_number % 4
        if remainder in [0, 1]:
            tuner_type = 'Satellite'
            tuner_number = device_number // 4 * 2 + 1
        elif remainder in [2, 3]:
            tuner_type = 'Terrestrial'
            tuner_number = (device_number - 2) // 4 * 2 + 1
        else:
            assert False, f'Unknown tuner device: {self.device_path}'

        if remainder in [1, 3]:
            tuner_number += 1

        return tuner_type, tuner_number


    def __getTunerDeviceInfo(self) -> tuple[Literal['Terrestrial', 'Satellite', 'Multi'], str]:
        """
        チューナーデバイスの種類と名前を取得する

        Returns:
            tuple[Literal['Terrestrial', 'Satellite', 'Multi'], str]: チューナーデバイスの種類と名前
        """

        # PLEX PX-W3U4/PX-Q3U4/PX-W3PE4/PX-Q3PE4/PX-W3PE5/PX-Q3PE5
        if str(self.device_path).startswith('/dev/px4video'):
            tuner_type, tuner_number = self.__getPX4VideoDeviceTypeAndIndex()
            return (tuner_type, f'PLEX PX4/PX5 Series ({tuner_type}) #{tuner_number}')

        # PLEX PX-S1UR
        if str(self.device_path).startswith('/dev/pxs1urvideo'):
            return 'Terrestrial', f'PLEX PX-S1UR #{int(str(self.device_path).split("pxs1urvideo")[-1]) + 1}'

        # PLEX PX-M1UR
        if str(self.device_path).startswith('/dev/pxm1urvideo'):
            return 'Multi', f'PLEX PX-M1UR #{int(str(self.device_path).split("pxm1urvideo")[-1]) + 1}'

        # PLEX PX-MLT5PE
        if str(self.device_path).startswith('/dev/pxmlt5video'):
            return 'Multi', f'PLEX PX-MLT5PE #{int(str(self.device_path).split("pxmlt5video")[-1]) + 1}'

        # PLEX PX-MLT8PE
        if str(self.device_path).startswith('/dev/pxmlt8video'):
            return 'Multi', f'PLEX PX-MLT8PE #{int(str(self.device_path).split("pxmlt8video")[-1]) + 1}'

        # e-better DTV02A-4TS-P
        if str(self.device_path).startswith('/dev/isdb6014video'):
            return 'Multi', f'e-better DTV02A-4TS-P #{int(str(self.device_path).split("isdb6014video")[-1]) + 1}'

        # e-better DTV02A-1T1S-U
        if str(self.device_path).startswith('/dev/isdb2056video'):
            return 'Multi', f'e-better DTV02A-1T1S-U #{int(str(self.device_path).split("isdb2056video")[-1]) + 1}'

        # ここには到達しないはず
        assert False, f'Unknown tuner device: {self.device_path}'


    def tune(self, physical_channel: str, recording_time: float = 10.0, tune_timeout: float = 7.0) -> bytearray:
        """
        チューナーデバイスから指定された物理チャンネルを受信し、選局/受信できなかった場合は例外を送出する
        録画時間にはチューナーオープンに掛かった時間を含まない
        選局タイムアウト発生時、チューナーのクローズに時間がかかる関係で最小でも合計 7 秒程度の時間が掛かる

        Args:
            physical_channel (str): 物理チャンネル (ex: "T13", "BS23_3", "CS04")
            recording_time (float, optional): 録画時間 (秒). Defaults to 10.0.
            tune_timeout (float, optional): 選局 (チューナーオープン) のタイムアウト時間 (秒). Defaults to 7.0.

        Returns:
            bytearray: 受信したデータ

        Raises:
            TunerOpeningError: チューナーをオープンできなかった場合
            TunerTuningError: チャンネルを選局できなかった場合
            TunerOutputError: 受信したデータが小さすぎる場合
        """

        # recisdb (チューナープロセス) を起動
        process = subprocess.Popen(
            ['recisdb', 'tune', '--device', str(self.device_path), '--channel', physical_channel, '--time', str(recording_time), '-'],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
        )

        # それぞれ別スレッドで標準出力と標準エラー出力の読み込みを開始
        stdout: bytearray = bytearray()
        is_stdout_arrived = False
        def stdout_thread_func():
            nonlocal stdout, is_stdout_arrived
            assert process.stdout is not None
            while True:
                data = process.stdout.read(188)
                is_stdout_arrived = True
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
        stdout_thread.start()
        stderr_thread.start()

        # プロセスが終了するか、選局 (チューナーオープン) のタイムアウト秒数に達するまで待機
        # 標準出力から TS ストリームが出力されるようになったらタイムアウト秒数のカウントを停止
        tune_timeout_count = 0
        while process.poll() is None and tune_timeout_count < tune_timeout:
            time.sleep(0.01)
            if is_stdout_arrived is False:
                tune_timeout_count += 0.01

        # この時点でプロセスが終了しておらず、標準出力からまだ TS ストリームを受け取っていない場合
        # プロセスを終了 (Ctrl+C を送信) し、タイムアウトエラーを送出する
        if process.poll() is None and is_stdout_arrived is False:
            process.send_signal(signal.SIGINT)
            # ここでプロセスが完全に終了するまで待機しないと、続けて別のチャンネルを選局する際にデバイス使用中エラーが発生してしまう
            process.wait()
            raise TunerTuningError('Channel selection timed out.')

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
                error_message = 'Channel selection failed due to an unknown error.'

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


    def getSignalLevel(self, physical_channel: str) -> tuple[subprocess.Popen[bytes], Iterator[float]]:
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
            while True:

                # \r が出力されるまで 1 バイトずつ読み込む
                line = b''
                while True:
                    char = process.stdout.read(1)
                    if char == b'\r' or char == b'':
                        break
                    line += char

                # プロセスが終了していたら終了
                if process.poll() is not None:
                    process.send_signal(signal.SIGINT)
                    process.wait()
                    raise StopIteration

                # 信号レベルをパースして随時返す
                result = re.search(r'(\d+\.\d+)dB', line.decode('utf-8').strip())
                if result is None:
                    continue
                yield float(result.group(1))

        return process, iterator()


    def getSignalLevelMean(self, physical_channel: str) -> float | None:
        """
        チューナーデバイスから指定された物理チャンネルを受信し、5回の平均信号レベルを返す

        Args:
            physical_channel (str): 物理チャンネル (ex: "T13", "BS23_3", "CS04")

        Returns:
            float | None: 平均信号レベル (選局失敗時は None)
        """

        # 信号レベルを取得するイテレータを取得
        process, iterator = self.getSignalLevel(physical_channel)

        # 5回分の信号レベルを取得
        # もし信号レベルの取得中にプロセスが終了した場合は選局に失敗しているので None を返す
        signal_levels: list[float] = []
        for _ in range(5):
            try:
                signal_levels.append(next(iterator))
            except RuntimeError:
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
