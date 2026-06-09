from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import uuid


@dataclass
class InventoryItem:
    id: str
    name: str
    category: str
    model: str
    total_quantity: int
    locked_quantity: int = 0
    unit: str = "台"
    location: str = ""
    manager: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, name: str, category: str, model: str, total_quantity: int,
               unit: str = "台", location: str = "", manager: str = "",
               description: str = "") -> 'InventoryItem':
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            category=category,
            model=model,
            total_quantity=total_quantity,
            locked_quantity=0,
            unit=unit,
            location=location,
            manager=manager,
            description=description,
            created_at=now,
            updated_at=now
        )

    @property
    def available_quantity(self) -> int:
        return self.total_quantity - self.locked_quantity

    def can_lock(self, quantity: int) -> tuple[bool, str]:
        if quantity <= 0:
            return False, "锁定数量必须大于0"
        if quantity > self.available_quantity:
            return False, f"可用数量不足，当前可用: {self.available_quantity}{self.unit}，需要: {quantity}{self.unit}"
        return True, ""

    def lock(self, quantity: int) -> None:
        self.locked_quantity += quantity
        self.updated_at = datetime.now()

    def unlock(self, quantity: int) -> None:
        self.locked_quantity = max(0, self.locked_quantity - quantity)
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'model': self.model,
            'total_quantity': self.total_quantity,
            'locked_quantity': self.locked_quantity,
            'unit': self.unit,
            'location': self.location,
            'manager': self.manager,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'InventoryItem':
        return cls(
            id=data['id'],
            name=data['name'],
            category=data['category'],
            model=data['model'],
            total_quantity=data['total_quantity'],
            locked_quantity=data.get('locked_quantity', 0),
            unit=data.get('unit', '台'),
            location=data.get('location', ''),
            manager=data.get('manager', ''),
            description=data.get('description', ''),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
        )
