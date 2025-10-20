"""
HazeSDK Constants
=================

All game-related constants and offsets.
"""

# Process information
PROCESS_NAME = "RocketLeague.exe"

# Memory offsets (will be auto-detected)
GNAMES_OFFSET = None
GOBJECTS_OFFSET = None
EXPECTED_OFFSET_DIFF = 0x48

# Function names for hooking
FUNCTION_NAMES = {
    "PLAYER_TICK": "Function TAGame.PlayerController_TA.PlayerTick",
    "BOOST_PICKED_UP": "Function TAGame.VehiclePickup_Boost_TA.Idle.EndState",
    "BOOST_RESPAWN": "Function TAGame.VehiclePickup_Boost_TA.Idle.BeginState",
    "ROUND_ACTIVE_BEGIN": "Function TAGame.GameEvent_Soccar_TA.Active.BeginState",
    "ROUND_ACTIVE_END": "Function TAGame.GameEvent_Soccar_TA.Active.EndState",
    "RESET_PICKUPS": "Function TAGame.GameEvent_TA.ResetPickups",
    "GAMEEVENT_BEGIN": "Function TAGame.GameEvent_Soccar_TA.PostBeginPlay",
    "KEY_PRESS": "Function TAGame.GameViewportClient_TA.HandleKeyPress",
    "VIEWPORT_TICK": "Function Engine.GameViewportClient.Tick",
    "GAMEEVENT_DESTROYED": "Function TAGame.GameEvent_Soccar_TA.Destroyed",
}

# Memory patterns for offset scanning
MEMORY_PATTERNS = {
    'GObjects_Current': b"\x48\x8B\xC8\x48\x8B\x05\x00\x00\x00\x00\x48\x8B\x0C\xC8",
    'GNames_Current1': b"\x48\x8B\x0D\x00\x00\x00\x00\x48\x8B\x0C\xC1",
    'GNames_Current2': b"\x49\x63\x06\x48\x8D\x55\xE8\x48\x8B\x0D\x00\x00\x00\x00\x48\x8B\x0C\xC1",
    # Legacy patterns as fallback
    'GNames_Legacy1': b"\x75\x05\xE8\x00\x00\x00\x00\x85\xDB\x75\x31",
    'GObjects_Legacy1': b"\xE8\x00\x00\x00\x00\x8B\x5D\xBF\x48",
}

# UObject offsets
UOBJECT_INDEX = 0x0038
UOBJECT_OUTER = 0x0040
UOBJECT_NAME = 0x0048
UOBJECT_CLASS = 0x0050
UOBJECT_SIZE = 0x0060

# Actor offsets
ACTOR_LOCATION = 0x0090
ACTOR_ROTATION = 0x009C
ACTOR_VELOCITY = 0x01A8
ACTOR_ANGULAR_VELOCITY = 0x01C0

# Car offsets
CAR_PRI = 0x0808
CAR_INPUTS = 0x07D4
CAR_BOOST_COMPONENT = 0x0848
CAR_FLAGS = 0x07D0

# Ball offsets
BALL_SIZE = 0x0A48

# GameEvent offsets
GAMEEVENT_BALLS = 0x08E0
GAMEEVENT_CARS = 0x0350
GAMEEVENT_PRIS = 0x0340
GAMEEVENT_TEAMS = 0x0750
GAMEEVENT_TIME_REMAINING = 0x086C
GAMEEVENT_FLAGS = 0x0800

# Boost pad locations (standard Soccar field)
BOOST_PAD_LOCATIONS = [
    (0.0, -4240.0, 70.0, False),
    (-1792.0, -4184.0, 70.0, False),
    (1792.0, -4184.0, 70.0, False),
    (-3072.0, -4096.0, 73.0, True),
    (3072.0, -4096.0, 73.0, True),
    (-940.0, -3308.0, 70.0, False),
    (940.0, -3308.0, 70.0, False),
    (0.0, -2816.0, 70.0, False),
    (-3584.0, -2484.0, 70.0, False),
    (3584.0, -2484.0, 70.0, False),
    (-1788.0, -2300.0, 70.0, False),
    (1788.0, -2300.0, 70.0, False),
    (-2048.0, -1036.0, 70.0, False),
    (0.0, -1024.0, 70.0, False),
    (2048.0, -1036.0, 70.0, False),
    (-3584.0, 0.0, 73.0, True),
    (-1024.0, 0.0, 70.0, False),
    (1024.0, 0.0, 70.0, False),
    (3584.0, 0.0, 73.0, True),
    (-2048.0, 1036.0, 70.0, False),
    (0.0, 1024.0, 70.0, False),
    (2048.0, 1036.0, 70.0, False),
    (-1788.0, 2300.0, 70.0, False),
    (1788.0, 2300.0, 70.0, False),
    (-3584.0, 2484.0, 70.0, False),
    (3584.0, 2484.0, 70.0, False),
    (0.0, 2816.0, 70.0, False),
    (-940.0, 3310.0, 70.0, False),
    (940.0, 3308.0, 70.0, False),
    (-3072.0, 4096.0, 73.0, True),
    (3072.0, 4096.0, 73.0, True),
    (-1792.0, 4184.0, 70.0, False),
    (1792.0, 4184.0, 70.0, False),
    (0.0, 4240.0, 70.0, False),
]

# Performance settings
DEFAULT_TICK_RATE = 120
CACHE_EXPIRY_SECONDS = 0.1  # 100ms cache validity
MAX_READ_RETRIES = 3

