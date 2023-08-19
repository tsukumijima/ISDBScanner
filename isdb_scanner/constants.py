
from __future__ import annotations

from pydantic import BaseModel
from pydantic import RootModel


# Pydantic モデルの定義

class ServiceInfo(BaseModel):
    service_id: int = -1
    service_name: str = ''
    service_type: int = -1
    is_free: bool = True
    is_oneseg: bool = False

class TransportStreamInfo(BaseModel):
    physical_channel: str = ''
    transport_stream_id: int = -1
    network_id: int = -1
    network_name: str = ''
    remote_control_key_id: int | None = None
    satellite_frequency: float | None = None
    satellite_transponder: int | None = None
    satellite_slot: int | None = None
    services: list[ServiceInfo] = []

class TransportStreamInfoList(RootModel[list[TransportStreamInfo]]):
    root: list[TransportStreamInfo]


# ref: https://github.com/tsukumijima/px4_drv

# ISDB-T 専用のチューナーデバイスのパス (px4_drv)
# PLEX PX-W3PE4/PX-W3PE5/PX-W3U4/PX-Q3PE4/PX-Q3PE5/PX-Q3U4 用 (全体で最大8チューナーまで想定)
ISDBT_TUNER_DEVICE_PATHS = [
    '/dev/px4video2',
    '/dev/px4video3',
    '/dev/px4video6',
    '/dev/px4video7',
    '/dev/px4video10',
    '/dev/px4video11',
    '/dev/px4video14',
    '/dev/px4video15',
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
