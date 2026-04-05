import enum


class UserRole(str, enum.Enum):
    COMMUTER = "COMMUTER"
    DRIVER = "DRIVER"
    ADMIN = "ADMIN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
