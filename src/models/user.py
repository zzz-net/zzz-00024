from dataclasses import dataclass
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    NORMAL = "普通用户"
    MAINTENANCE = "维修人员"
    ADMIN = "管理员"


@dataclass
class User:
    username: str
    role: UserRole
    display_name: str = ""

    @classmethod
    def create_normal_user(cls, username: str, display_name: str = "") -> 'User':
        return cls(
            username=username,
            role=UserRole.NORMAL,
            display_name=display_name or username,
        )

    @classmethod
    def create_maintenance_user(cls, username: str, display_name: str = "") -> 'User':
        return cls(
            username=username,
            role=UserRole.MAINTENANCE,
            display_name=display_name or username,
        )

    @classmethod
    def create_admin_user(cls, username: str, display_name: str = "") -> 'User':
        return cls(
            username=username,
            role=UserRole.ADMIN,
            display_name=display_name or username,
        )

    def can_unfreeze_maintenance(self) -> bool:
        return self.role in [UserRole.MAINTENANCE, UserRole.ADMIN]

    def can_freeze(self) -> bool:
        return self.role in [UserRole.MAINTENANCE, UserRole.ADMIN]

    def can_calibrate(self) -> bool:
        return self.role in [UserRole.MAINTENANCE, UserRole.ADMIN]

    def can_borrow(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            'username': self.username,
            'role': self.role.value,
            'display_name': self.display_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(
            username=data['username'],
            role=UserRole(data['role']),
            display_name=data.get('display_name', data['username']),
        )
