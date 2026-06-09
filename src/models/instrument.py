from dataclasses import dataclass, field
from enum import Enum
from datetime import date, datetime
from typing import Optional, List
import uuid


class InstrumentStatus(str, Enum):
    AVAILABLE = "可用"
    BORROWED = "借出中"
    MAINTENANCE = "维修中"
    CALIBRATION_DUE = "校准到期"
    CALIBRATION_EXPIRED = "校准过期"
    FROZEN = "冻结"


class InstrumentCategory(str, Enum):
    ANALYSIS = "分析仪器"
    MEASUREMENT = "测量仪器"
    OPTICAL = "光学仪器"
    ELECTRONIC = "电子仪器"
    MECHANICAL = "机械仪器"
    OTHER = "其他"


@dataclass
class Instrument:
    id: str
    name: str
    category: InstrumentCategory
    model: str
    serial_number: str
    location: str
    manager: str
    calibration_due_date: Optional[date] = None
    status: InstrumentStatus = InstrumentStatus.AVAILABLE
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, name: str, category: InstrumentCategory, model: str, 
               serial_number: str, location: str, manager: str,
               calibration_due_date: Optional[date] = None,
               description: str = "") -> 'Instrument':
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            category=category,
            model=model,
            serial_number=serial_number,
            location=location,
            manager=manager,
            calibration_due_date=calibration_due_date,
            status=InstrumentStatus.AVAILABLE,
            description=description,
            created_at=now,
            updated_at=now
        )

    def is_calibration_expired(self) -> bool:
        if self.calibration_due_date is None:
            return False
        return date.today() > self.calibration_due_date

    def is_calibration_due_soon(self, days: int = 30) -> bool:
        if self.calibration_due_date is None:
            return False
        delta = self.calibration_due_date - date.today()
        return 0 <= delta.days <= days

    def can_borrow(self) -> tuple[bool, str]:
        if self.status == InstrumentStatus.BORROWED:
            return False, "仪器已被借出"
        if self.status == InstrumentStatus.MAINTENANCE:
            return False, "仪器正在维修中"
        if self.status == InstrumentStatus.FROZEN:
            return False, "仪器已被冻结"
        if self.is_calibration_expired():
            return False, "仪器校准已过期，需先完成校准才能借出"
        if self.status == InstrumentStatus.CALIBRATION_EXPIRED:
            return False, "仪器校准已过期，需先完成校准才能借出"
        return True, ""

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category.value,
            'model': self.model,
            'serial_number': self.serial_number,
            'location': self.location,
            'manager': self.manager,
            'calibration_due_date': self.calibration_due_date.isoformat() if self.calibration_due_date else None,
            'status': self.status.value,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Instrument':
        calibration_due_date = None
        if data.get('calibration_due_date'):
            calibration_due_date = date.fromisoformat(data['calibration_due_date'])
        
        return cls(
            id=data['id'],
            name=data['name'],
            category=InstrumentCategory(data['category']),
            model=data['model'],
            serial_number=data['serial_number'],
            location=data['location'],
            manager=data['manager'],
            calibration_due_date=calibration_due_date,
            status=InstrumentStatus(data['status']),
            description=data.get('description', ''),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
        )
