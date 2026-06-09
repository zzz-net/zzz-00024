from dataclasses import dataclass, field
from enum import Enum
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import uuid


class CalibrationConflictType(str, Enum):
    MISSING_DATE = "日期缺失"
    DUPLICATE_CERTIFICATE = "证书号重复"
    INSTRUMENT_NOT_FOUND = "仪器不存在"
    BORROWED_CONFLICT = "已借出状态冲突"
    FROZEN_CONFLICT = "已冻结状态冲突"
    INVALID_DATE = "日期无效"
    DUPLICATE_SERIAL = "序列号重复"


class CalibrationConflictResolution(str, Enum):
    PENDING = "待处理"
    CONFIRM = "确认导入"
    IGNORE = "忽略跳过"
    UPDATE = "强制更新"


class CalibrationScheduleStatus(str, Enum):
    IMPORTING = "导入中"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    CANCELLED = "已取消"


class CalibrationScheduleItemStatus(str, Enum):
    SCHEDULED = "待校准"
    IN_PROGRESS = "校准中"
    COMPLETED = "已完成"
    OVERDUE = "已逾期"
    CANCELLED = "已取消"


@dataclass
class CalibrationScheduleConflict:
    id: str
    schedule_id: str
    conflict_type: CalibrationConflictType
    serial_number: str
    expected_value: str
    actual_value: str
    instrument_id: Optional[str] = None
    instrument_name: str = ""
    resolution: CalibrationConflictResolution = CalibrationConflictResolution.PENDING
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    row_data: Optional[Dict[str, Any]] = None

    @classmethod
    def create(cls, schedule_id: str, conflict_type: CalibrationConflictType,
               serial_number: str, expected_value: str, actual_value: str,
               instrument_id: Optional[str] = None, instrument_name: str = "",
               notes: str = "", row_data: Optional[Dict[str, Any]] = None) -> 'CalibrationScheduleConflict':
        return cls(
            id=str(uuid.uuid4()),
            schedule_id=schedule_id,
            conflict_type=conflict_type,
            serial_number=serial_number,
            expected_value=expected_value,
            actual_value=actual_value,
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            resolution=CalibrationConflictResolution.PENDING,
            resolved_by=None,
            resolved_at=None,
            notes=notes,
            created_at=datetime.now(),
            row_data=row_data,
        )

    def resolve(self, resolution: CalibrationConflictResolution, resolved_by: str, notes: str = "") -> None:
        self.resolution = resolution
        self.resolved_by = resolved_by
        self.resolved_at = datetime.now()
        if notes:
            self.notes = (self.notes + "\n" if self.notes else "") + notes

    def to_dict(self) -> dict:
        row_data = None
        if self.row_data:
            row_data = {}
            for k, v in self.row_data.items():
                if isinstance(v, (date, datetime)):
                    row_data[k] = v.isoformat()
                else:
                    row_data[k] = v
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
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
            'row_data': row_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CalibrationScheduleConflict':
        return cls(
            id=data['id'],
            schedule_id=data['schedule_id'],
            conflict_type=CalibrationConflictType(data['conflict_type']),
            serial_number=data['serial_number'],
            expected_value=data['expected_value'],
            actual_value=data['actual_value'],
            instrument_id=data.get('instrument_id'),
            instrument_name=data.get('instrument_name', ''),
            resolution=CalibrationConflictResolution(data.get('resolution', '待处理')),
            resolved_by=data.get('resolved_by'),
            resolved_at=datetime.fromisoformat(data['resolved_at']) if data.get('resolved_at') else None,
            notes=data.get('notes', ''),
            created_at=datetime.fromisoformat(data['created_at']),
            row_data=data.get('row_data'),
        )


@dataclass
class CalibrationScheduleItem:
    id: str
    schedule_id: str
    instrument_id: str
    serial_number: str
    instrument_name: str
    planned_date: date
    calibration_agency: str = ""
    certificate_number: str = ""
    actual_calibration_date: Optional[date] = None
    next_calibration_date: Optional[date] = None
    result: str = ""
    notes: str = ""
    status: CalibrationScheduleItemStatus = CalibrationScheduleItemStatus.SCHEDULED
    processed_by: Optional[str] = None
    processed_at: Optional[datetime] = None
    undo_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, schedule_id: str, instrument_id: str, serial_number: str,
               instrument_name: str, planned_date: date,
               calibration_agency: str = "", certificate_number: str = "",
               notes: str = "") -> 'CalibrationScheduleItem':
        return cls(
            id=str(uuid.uuid4()),
            schedule_id=schedule_id,
            instrument_id=instrument_id,
            serial_number=serial_number,
            instrument_name=instrument_name,
            planned_date=planned_date,
            calibration_agency=calibration_agency,
            certificate_number=certificate_number,
            actual_calibration_date=None,
            next_calibration_date=None,
            result="",
            notes=notes,
            status=CalibrationScheduleItemStatus.SCHEDULED,
            processed_by=None,
            processed_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def mark_completed(self, calibration_date: date, next_calibration_date: date,
                       certificate_number: str, result: str, processed_by: str,
                       notes: str = "") -> None:
        self.actual_calibration_date = calibration_date
        self.next_calibration_date = next_calibration_date
        self.certificate_number = certificate_number
        self.result = result
        self.status = CalibrationScheduleItemStatus.COMPLETED
        self.processed_by = processed_by
        self.processed_at = datetime.now()
        self.updated_at = datetime.now()
        if notes:
            self.notes = (self.notes + "\n" if self.notes else "") + notes

    def mark_overdue(self) -> None:
        if self.status == CalibrationScheduleItemStatus.SCHEDULED:
            self.status = CalibrationScheduleItemStatus.OVERDUE
            self.updated_at = datetime.now()

    def is_overdue(self) -> bool:
        if self.status in [CalibrationScheduleItemStatus.COMPLETED, CalibrationScheduleItemStatus.CANCELLED]:
            return False
        return date.today() > self.planned_date

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'instrument_id': self.instrument_id,
            'serial_number': self.serial_number,
            'instrument_name': self.instrument_name,
            'planned_date': self.planned_date.isoformat(),
            'calibration_agency': self.calibration_agency,
            'certificate_number': self.certificate_number,
            'actual_calibration_date': self.actual_calibration_date.isoformat() if self.actual_calibration_date else None,
            'next_calibration_date': self.next_calibration_date.isoformat() if self.next_calibration_date else None,
            'result': self.result,
            'notes': self.notes,
            'status': self.status.value,
            'processed_by': self.processed_by,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'undo_snapshot': self.undo_snapshot,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CalibrationScheduleItem':
        return cls(
            id=data['id'],
            schedule_id=data['schedule_id'],
            instrument_id=data['instrument_id'],
            serial_number=data['serial_number'],
            instrument_name=data['instrument_name'],
            planned_date=date.fromisoformat(data['planned_date']),
            calibration_agency=data.get('calibration_agency', ''),
            certificate_number=data.get('certificate_number', ''),
            actual_calibration_date=date.fromisoformat(data['actual_calibration_date']) if data.get('actual_calibration_date') else None,
            next_calibration_date=date.fromisoformat(data['next_calibration_date']) if data.get('next_calibration_date') else None,
            result=data.get('result', ''),
            notes=data.get('notes', ''),
            status=CalibrationScheduleItemStatus(data.get('status', '待校准')),
            processed_by=data.get('processed_by'),
            processed_at=datetime.fromisoformat(data['processed_at']) if data.get('processed_at') else None,
            undo_snapshot=data.get('undo_snapshot'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
        )


@dataclass
class CalibrationSchedule:
    id: str
    name: str
    creator: str
    plan_date: date
    total_items: int = 0
    completed_count: int = 0
    conflict_count: int = 0
    status: CalibrationScheduleStatus = CalibrationScheduleStatus.IMPORTING
    notes: str = ""
    can_undo: bool = False
    undo_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @classmethod
    def create(cls, name: str, creator: str, plan_date: date,
               notes: str = "") -> 'CalibrationSchedule':
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            creator=creator,
            plan_date=plan_date,
            total_items=0,
            completed_count=0,
            conflict_count=0,
            status=CalibrationScheduleStatus.IMPORTING,
            notes=notes,
            can_undo=False,
            undo_snapshot=None,
            created_at=datetime.now(),
            completed_at=None,
        )

    def mark_processing(self) -> None:
        self.status = CalibrationScheduleStatus.PROCESSING

    def mark_completed(self) -> None:
        self.status = CalibrationScheduleStatus.COMPLETED
        self.completed_at = datetime.now()

    def mark_cancelled(self) -> None:
        self.status = CalibrationScheduleStatus.CANCELLED
        self.completed_at = datetime.now()

    def refresh_status(self, items: List[CalibrationScheduleItem]) -> None:
        for item in items:
            if item.is_overdue() and item.status == CalibrationScheduleItemStatus.SCHEDULED:
                item.mark_overdue()
        self.completed_count = sum(1 for i in items if i.status == CalibrationScheduleItemStatus.COMPLETED)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'creator': self.creator,
            'plan_date': self.plan_date.isoformat(),
            'total_items': self.total_items,
            'completed_count': self.completed_count,
            'conflict_count': self.conflict_count,
            'status': self.status.value,
            'notes': self.notes,
            'can_undo': self.can_undo,
            'undo_snapshot': self.undo_snapshot,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CalibrationSchedule':
        return cls(
            id=data['id'],
            name=data['name'],
            creator=data['creator'],
            plan_date=date.fromisoformat(data['plan_date']),
            total_items=data.get('total_items', 0),
            completed_count=data.get('completed_count', 0),
            conflict_count=data.get('conflict_count', 0),
            status=CalibrationScheduleStatus(data.get('status', '导入中')),
            notes=data.get('notes', ''),
            can_undo=data.get('can_undo', False),
            undo_snapshot=data.get('undo_snapshot'),
            created_at=datetime.fromisoformat(data['created_at']),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
        )
