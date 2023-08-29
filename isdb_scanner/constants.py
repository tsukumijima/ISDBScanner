
from __future__ import annotations

from pydantic import BaseModel
from pydantic import RootModel


# Pydantic モデルの定義

class ServiceInfo(BaseModel):
    channel_number: str = 'Unknown'  # 3桁チャンネル番号 (BS/CS ではサービス ID と同一)
    service_id: int = -1             # サービス ID
    service_type: int = -1           # サービス種別 (1: 映像サービス, 161: 臨時映像サービス, 192: データサービス/ワンセグ放送)
    service_name: str = 'Unknown'    # サービス名
    is_free: bool = True             # 無料放送かどうか
    is_oneseg: bool = False          # ワンセグ放送かどうか

    def __str__(self) -> str:
        message = f'Ch: {self.channel_number} | {self.service_name} '
        if self.service_type == 0x02:
            message += '[Radio]'
        elif 0xA1 <= self.service_type <= 0xA3:
            message += '[Temporary]'
        elif self.service_type == 0xA4:
            message += '[Engineering Service]'
        elif 0xA5 <= self.service_type <= 0xA7:
            message += '[Promotion]'
        elif self.service_type == 0xC0 and not self.is_oneseg:
            message += '[Data]'
        if not self.is_free:
            message += '[Pay TV]'
        if self.is_oneseg:
            message += '[OneSeg]'
        return message.rstrip()

class TransportStreamInfo(BaseModel):
    physical_channel: str = 'Unknown'         # 物理チャンネル (ex: "T13", "BS23_3", "CS04")
    transport_stream_id: int = -1             # トランスポートストリーム ID
    network_id: int = -1                      # ネットワーク ID
    network_name: str = 'Unknown'             # 地上波: トランスポートストリーム名 / BS/CS: ネットワーク名
    remote_control_key_id: int | None = None  # 地上波: リモコンキー ID
    satellite_frequency: float | None = None  # BS/CS: 周波数 (単位: GHz)
    satellite_transponder: int | None = None  # BS/CS: トランスポンダ番号
    satellite_slot_number: int | None = None  # BS: いわゆるスロット番号 (厳密には相対 TS 番号)
    services: list[ServiceInfo] = []

    def __str__(self) -> str:
        ts_type = 'Terrestrial'
        physical_channel = self.physical_channel
        if 0x7880 <= self.network_id <= 0x7FE8:
            physical_channel = self.physical_channel.replace('T', '') + 'ch'
        elif self.network_id == 4:
            ts_type = 'BS'
        elif self.network_id == 6:
            ts_type = 'CS1'
        elif self.network_id == 7:
            ts_type = 'CS2'
        message = f'{ts_type} - {physical_channel} / TSID: {self.transport_stream_id} '
        if 0x7880 <= self.network_id <= 0x7FE8:
            message += f'| {self.remote_control_key_id:02d}: {self.network_name}'
        else:
            message += f'/ Frequency: {self.satellite_frequency:.5f} GHz | {self.network_name}'
        return message.rstrip()

class TransportStreamInfoList(RootModel[list[TransportStreamInfo]]):
    root: list[TransportStreamInfo]


# ref: https://github.com/tsukumijima/px4_drv

# ISDB-T 専用のチューナーデバイスのパス (px4_drv)
# PLEX PX-W3PE4/PX-W3PE5/PX-W3U4/PX-Q3PE4/PX-Q3PE5/PX-Q3U4 用 (全体で最大8チューナーまで想定)
# PLEX PX-S1UR は最大8台接続まで想定
ISDBT_TUNER_DEVICE_PATHS = [
    '/dev/px4video2',
    '/dev/px4video3',
    '/dev/px4video6',
    '/dev/px4video7',
    '/dev/px4video10',
    '/dev/px4video11',
    '/dev/px4video14',
    '/dev/px4video15',
    # PX-S1UR (1台目)
    '/dev/pxs1urvideo0',
    # PX-S1UR (2台目)
    '/dev/pxs1urvideo1',
    # PX-S1UR (3台目)
    '/dev/pxs1urvideo2',
    # PX-S1UR (4台目)
    '/dev/pxs1urvideo3',
    # PX-S1UR (5台目)
    '/dev/pxs1urvideo4',
    # PX-S1UR (6台目)
    '/dev/pxs1urvideo5',
    # PX-S1UR (7台目)
    '/dev/pxs1urvideo6',
    # PX-S1UR (8台目)
    '/dev/pxs1urvideo7',
]

# ISDB-S 専用のチューナーデバイスのパス (px4_drv)
# PLEX PX-W3PE4/PX-W3PE5/PX-W3U4/PX-Q3PE4/PX-Q3PE5/PX-Q3U4 用 (全体で最大8チューナーまで想定)
ISDBS_TUNER_DEVICE_PATHS = [
    '/dev/px4video0',
    '/dev/px4video1',
    '/dev/px4video4',
    '/dev/px4video5',
    '/dev/px4video8',
    '/dev/px4video9',
    '/dev/px4video12',
    '/dev/px4video13',
]

# ISDB-T/ISDB-S 共用のマルチチューナーデバイスのパス (px4_drv)
# PLEX PX-MLT5PE/PX-MLT8PE/PX-M1UR, e-better DTV02A-4TS-P/DTV02A-1T1S-U 用
# PLEX PX-MLT5PE/PX-MLT8PE, e-better DTV02A-4TS-P は最大2台接続まで想定
# PLEX PX-M1UR, e-better DTV02A-1T1S-U は最大8台接続まで想定
ISDB_MULTI_TUNER_DEVICE_PATHS = [
    # DTV02A-4TS-P (1台目)
    '/dev/isdb6014video0',
    '/dev/isdb6014video1',
    '/dev/isdb6014video2',
    '/dev/isdb6014video3',
    # DTV02A-4TS-P (2台目)
    '/dev/isdb6014video4',
    '/dev/isdb6014video5',
    '/dev/isdb6014video6',
    '/dev/isdb6014video7',
    # PX-MLT5PE (1台目)
    '/dev/pxmlt5video0',
    '/dev/pxmlt5video1',
    '/dev/pxmlt5video2',
    '/dev/pxmlt5video3',
    '/dev/pxmlt5video4',
    # PX-MLT5PE (2台目)
    '/dev/pxmlt5video5',
    '/dev/pxmlt5video6',
    '/dev/pxmlt5video7',
    '/dev/pxmlt5video8',
    '/dev/pxmlt5video9',
    # PX-MLT8PE (1台目)
    '/dev/pxmlt8video0',
    '/dev/pxmlt8video1',
    '/dev/pxmlt8video2',
    '/dev/pxmlt8video3',
    '/dev/pxmlt8video4',
    '/dev/pxmlt8video5',
    '/dev/pxmlt8video6',
    '/dev/pxmlt8video7',
    # PX-MLT8PE (2台目)
    '/dev/pxmlt8video8',
    '/dev/pxmlt8video9',
    '/dev/pxmlt8video10',
    '/dev/pxmlt8video11',
    '/dev/pxmlt8video12',
    '/dev/pxmlt8video13',
    '/dev/pxmlt8video14',
    '/dev/pxmlt8video15',
    # DTV02A-1T1S-U (1台目)
    '/dev/isdb2056video0',
    # DTV02A-1T1S-U (2台目)
    '/dev/isdb2056video1',
    # DTV02A-1T1S-U (3台目)
    '/dev/isdb2056video2',
    # DTV02A-1T1S-U (4台目)
    '/dev/isdb2056video3',
    # DTV02A-1T1S-U (5台目)
    '/dev/isdb2056video4',
    # DTV02A-1T1S-U (6台目)
    '/dev/isdb2056video5',
    # DTV02A-1T1S-U (7台目)
    '/dev/isdb2056video6',
    # DTV02A-1T1S-U (8台目)
    '/dev/isdb2056video7',
    # PX-M1UR (1台目)
    '/dev/pxm1urvideo0',
    # PX-M1UR (2台目)
    '/dev/pxm1urvideo1',
    # PX-M1UR (3台目)
    '/dev/pxm1urvideo2',
    # PX-M1UR (4台目)
    '/dev/pxm1urvideo3',
    # PX-M1UR (5台目)
    '/dev/pxm1urvideo4',
    # PX-M1UR (6台目)
    '/dev/pxm1urvideo5',
    # PX-M1UR (7台目)
    '/dev/pxm1urvideo6',
    # PX-M1UR (8台目)
    '/dev/pxm1urvideo7',
]
