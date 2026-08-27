from enum import StrEnum


class PaperSessionStatus(StrEnum):
    ACTIVE = "active"
    STOPPED = "stopped"
    ERROR = "error"


class ConnectionState(StrEnum):
    STARTING = "starting"
    CONNECTED = "connected"
    STALE = "stale"
    DISCONNECTED = "disconnected"
