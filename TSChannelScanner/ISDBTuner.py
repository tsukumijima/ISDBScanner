
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path


class ISDBTuner:
    """ ISDB-T/S チューナーを操作するクラス (recisdb のラッパー) """

    # チューナーの受信タイムアウト (秒)
    TUNE_TIMEOUT = 5

    # 検出可能とする信号レベル (dB)
    ## TVTest のデフォルト値と同一
    SIGNAL_LEVEL_THRESHOLD = 7.0


    def __init__(self, output_recisdb_log: bool = False) -> None:
        """
        ISDB-T/S チューナーを操作するクラスを初期化する

        Args:
            output_recisdb_log (bool, optional): recisdb のログを出力するかどうか. Defaults to False.
        """

        self.output_recisdb_log = output_recisdb_log


    def tune(self, device_path: Path, physical_channel: str) -> bytes | None:
        """
        チューナーデバイスから指定された物理チャンネルを受信する
        選局/受信できなかった場合は None を返す

        Args:
            device_path (Path): デバイスファイルのパス
            physical_channel (str): 物理チャンネル (ex: "T13" / "BS23_3", "CS04")

        Returns:
            bytes | None: 受信したデータ (失敗時は None)
        """

        # recisdb (チューナープロセス) を起動
        process = subprocess.Popen(
            ['recisdb', 'tune', '--device', str(device_path), '--channel', physical_channel, '-'],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE if self.output_recisdb_log else None,
        )

        # タイムアウト秒数に達するまで受信し続ける
        try:
            stdout, _ = process.communicate(timeout=self.TUNE_TIMEOUT)
        except subprocess.TimeoutExpired:
            # タイムアウトに達したらプロセスを終了し、stdout と stderr を取得
            process.terminate()
            stdout, _ = process.communicate()

        # この時点でリターンコードが 0 でなければ選局または受信に失敗している
        if process.returncode != 0:
            return None

        # 5秒も受信していれば（チューナーオープン時間を含めても）100KB 以上のデータが得られるはず
        # それ未満の場合は選局に失敗している
        if len(stdout) < 100 * 1024:
            return None

        # 受信したデータを返す
        return stdout


    def checkSignal(self, device_path: Path, physical_channel: str) -> tuple[subprocess.Popen[bytes], Iterator[float]]:
        """
        チューナーデバイスから指定された物理チャンネルを受信し、イテレータで信号レベルを返す
        この関数はイテレータを呼び終わってもプロセスを終了しないので、呼び出し側で明示的にプロセスを終了する必要がある

        Args:
            device_path (Path): デバイスファイルのパス
            physical_channel (str): 物理チャンネル (ex: "T13" / "BS23_3", "CS04")

        Returns:
            tuple[subprocess.Popen, Iterator[float]]: チューナープロセスと信号レベルを返すイテレータ
        """

        # recisdb (チューナープロセス) を起動
        process = subprocess.Popen(
            ['recisdb', 'checksignal', '--device', str(device_path), '--channel', physical_channel],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE if self.output_recisdb_log else None,
        )

        # 標準出力に一行ずつ受信感度が "30.00dB" のように出力されるので、随時パースしてイテレータで返す
        ## 選局/受信に失敗したか、あるいはユーザーが手動でプロセスを終了させた場合は StopIteration が発生する
        def iterator() -> Iterator[float]:
            assert process.stdout is not None
            for line in process.stdout:

                # プロセスが終了していたら終了
                if line == b'' or process.poll() is not None:
                    process.terminate()
                    break

                # 信号レベルをパースして随時返す
                result = re.search(r'(\d+\.\d+)dB', line.decode('utf-8'))
                if result is None:
                    continue
                yield float(result.group(1))

        return process, iterator()


    def checkSignalMean(self, device_path: Path, physical_channel: str) -> float | None:
        """
        チューナーデバイスから指定された物理チャンネルを受信し、5回の平均信号レベルを返す

        Args:
            device_path (Path): デバイスファイルのパス
            physical_channel (str): 物理チャンネル (ex: "T13" / "BS23_3", "CS04")

        Returns:
            float | None: 平均信号レベル (選局失敗時は None)
        """

        # 信号レベルを取得するイテレータを取得
        process, iterator = self.checkSignal(device_path, physical_channel)

        # 5回分の信号レベルを取得
        # もし信号レベルの取得中にプロセスが終了した場合は選局に失敗しているので None を返す
        try:
            signal_levels = [next(iterator) for _ in range(5)]
        except StopIteration:
            return None

        # プロセスを終了
        process.terminate()

        # 平均信号レベルを返す
        return sum(signal_levels) / len(signal_levels)
