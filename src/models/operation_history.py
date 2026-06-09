from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid


class OperationType(str, Enum):
    CREATE = "新增仪器"
    UPDATE = "更新信息"
    BORROW = "借出"
    RETURN = "归还"
    CALIBRATION = "校准"
    FREEZE = "冻结"
    UNFREEZE = "解冻"
    MAINTENANCE_START = "开始维修"
    MAINTENANCE_END = "维修完成"
    CALIBRATION_SCHEDULE_IMPORT = "校准排程导入"
    CALIBRATION_SCHEDULE_COMPLETE = "校准排程完成"
    CALIBRATION_SCHEDULE_UNDO = "校准排程撤销"


@dataclass
class OperationHistory:
    id: str
    instrument_id: str
    operation_type: OperationType
    operator: str
    timestamp: datetime
    details: str = ""
    related_record_id: Optional[str] = None

    @classmethod
    def create(cls, instrument_id: str, operation_type: OperationType, 
               operator: str, details: str = "", 
               related_record_id: Optional[str] = None) -> 'OperationHistory':
        return cls(
            id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            operation_type=operation_type,
            operator=operator,
            timestamp=datetime.now(),
            details=details,
            related_record_id=related_record_id,
        )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'instrument_id': self.instrument_id,
            'operation_type': self.operation_type.value,
            'operator': self.operator,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'related_record_id': self.related_record_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'OperationHistory':
        return cls(
            id=data['id'],
            instrument_id=data['instrument_id'],
            operation_type=OperationType(data['operation_type']),
            operator=data['operator'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            details=data.get('details', ''),
            related_record_id=data.get('related_record_id'),
        )
