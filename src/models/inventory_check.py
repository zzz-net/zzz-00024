from dataclasses import dataclass, field
from enum import Enum
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import uuid


class ConflictType(str, Enum):
    UNKNOWN_INSTRUMENT = "未知仪器"
    LOCATION_MISMATCH = "位置不一致"
    BORROWED_BUT_PRESENT = "已借出却在库"
    DUPLICATE_SERIAL = "重复序列号"


class ConflictResolution(str, Enum):
    PENDING = "待处理"
    CONFIRM = "确认更新"
    IGNORE = "忽略"
    UPDATE = "强制更新"


class InventoryCheckStatus(str, Enum):
    IMPORTING = "导入中"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    CANCELLED = "已取消"


@dataclass
class InventoryCheckConflict:
    id: str
    inventory_check_id: str
    conflict_type: ConflictType
    serial_number: str
    expected_value: str
    actual_value: str
    instrument_id: Optional[str] = None
    instrument_name: str = ""
    resolution: ConflictResolution = ConflictResolution.PENDING
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, inventory_check_id: str, conflict_type: ConflictType,
               serial_number: str, expected_value: str, actual_value: str,
               instrument_id: Optional[str] = None, instrument_name: str = "",
               notes: str = "") -> 'InventoryCheckConflict':
        return cls(
            id=str(uuid.uuid4()),
            inventory_check_id=inventory_check_id,
            conflict_type=conflict_type,
            serial_number=serial_number,
            expected_value=expected_value,
            actual_value=actual_value,
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            resolution=ConflictResolution.PENDING,
            resolved_by=None,
            resolved_at=None,
            notes=notes,
            created_at=datetime.now()
        )

    def resolve(self, resolution: ConflictResolution, resolved_by: str, notes: str = "") -> None:
        self.resolution = resolution
        self.resolved_by = resolved_by
        self.resolved_at = datetime.now()
        if notes:
            self.notes = (self.notes + "\n" if self.notes else "") + notes

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'inventory_check_id': self.inventory_check_id,
            'conflict_type': self.conflict_type.value,
            'serial_number': self.serial_number,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'instrument_id': self.instrument_id,
            'instrument_name': self.instrument_name,
            'resolution': self.resolution.value,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'InventoryCheckConflict':
        return cls(
            id=data['id'],
            inventory_check_id=data['inventory_check_id'],
            conflict_type=ConflictType(data['conflict_type']),
            serial_number=data['serial_number'],
            expected_value=data['expected_value'],
            actual_value=data['actual_value'],
            instrument_id=data.get('instrument_id'),
            instrument_name=data.get('instrument_name', ''),
            resolution=ConflictResolution(data.get('resolution', '待处理')),
            resolved_by=data.get('resolved_by'),
            resolved_at=datetime.fromisoformat(data['resolved_at']) if data.get('resolved_at') else None,
            notes=data.get('notes', ''),
            created_at=datetime.fromisoformat(data['created_at']),
        )


@dataclass
class InventoryCheck:
    id: str
    name: str
    checker: str
    check_date: date
    total_items: int = 0
    matched_count: int = 0
    conflict_count: int = 0
    status: InventoryCheckStatus = InventoryCheckStatus.IMPORTING
    notes: str = ""
    can_undo: bool = False
    undo_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @classmethod
    def create(cls, name: str, checker: str, check_date: date,
               notes: str = "") -> 'InventoryCheck':
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            checker=checker,
            check_date=check_date,
            total_items=0,
            matched_count=0,
            conflict_count=0,
            status=InventoryCheckStatus.IMPORTING,
            notes=notes,
            can_undo=False,
            undo_snapshot=None,
            created_at=datetime.now(),
            completed_at=None
        )

    def mark_completed(self) -> None:
        self.status = InventoryCheckStatus.COMPLETED
        self.completed_at = datetime.now()

    def mark_cancelled(self) -> None:
        self.status = InventoryCheckStatus.CANCELLED
        self.completed_at = datetime.now()

    def set_processing(self) -> None:
        self.status = InventoryCheckStatus.PROCESSING

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'checker': self.checker,
            'check_date': self.check_date.isoformat(),
            'total_items': self.total_items,
            'matched_count': self.matched_count,
            'conflict_count': self.conflict_count,
            'status': self.status.value,
            'notes': self.notes,
            'can_undo': self.can_undo,
            'undo_snapshot': self.undo_snapshot,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'InventoryCheck':
        return cls(
            id=data['id'],
            name=data['name'],
            checker=data['checker'],
            check_date=date.fromisoformat(data['check_date']),
            total_items=data.get('total_items', 0),
            matched_count=data.get('matched_count', 0),
            conflict_count=data.get('conflict_count', 0),
            status=InventoryCheckStatus(data.get('status', '导入中')),
            notes=data.get('notes', ''),
            can_undo=data.get('can_undo', False),
            undo_snapshot=data.get('undo_snapshot'),
            created_at=datetime.fromisoformat(data['created_at']),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
        )
