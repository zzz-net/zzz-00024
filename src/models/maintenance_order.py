from dataclasses import dataclass, field
from enum import Enum
from datetime import date, datetime
from typing import Optional, List
import uuid


class MaintenanceOrderStatus(str, Enum):
    PENDING = "待分配"
    IN_PROGRESS = "处理中"
    COMPLETED = "已完成"
    REJECTED = "已驳回"


class MaintenancePriority(str, Enum):
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"
    URGENT = "紧急"


class MaintenanceCompletionOption(str, Enum):
    RESTORE_AVAILABLE = "恢复可用"
    KEEP_FROZEN = "保持冻结"
    NEEDS_CALIBRATION = "转入待校准"


@dataclass
class MaintenanceLogEntry:
    id: str
    timestamp: datetime
    operator: str
    action: str
    details: str = ""

    @classmethod
    def create(cls, operator: str, action: str, details: str = "") -> 'MaintenanceLogEntry':
        return cls(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            operator=operator,
            action=action,
            details=details,
        )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'operator': self.operator,
            'action': self.action,
            'details': self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MaintenanceLogEntry':
        return cls(
            id=data['id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            operator=data['operator'],
            action=data['action'],
            details=data.get('details', ''),
        )


@dataclass
class MaintenanceOrder:
    id: str
    instrument_id: str
    instrument_name: str
    serial_number: str
    requester: str
    fault_description: str
    priority: MaintenancePriority
    expected_completion_date: Optional[date]
    assignee: Optional[str]
    status: MaintenanceOrderStatus
    completion_option: Optional[MaintenanceCompletionOption] = None
    rejection_reason: str = ""
    logs: List[MaintenanceLogEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, instrument_id: str, instrument_name: str, serial_number: str,
               requester: str, fault_description: str, priority: MaintenancePriority,
               expected_completion_date: Optional[date] = None,
               assignee: Optional[str] = None) -> 'MaintenanceOrder':
        order = cls(
            id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            serial_number=serial_number,
            requester=requester,
            fault_description=fault_description,
            priority=priority,
            expected_completion_date=expected_completion_date,
            assignee=assignee,
            status=MaintenanceOrderStatus.PENDING,
        )
        order.add_log(requester, "创建工单", f"故障描述: {fault_description}")
        return order

    def add_log(self, operator: str, action: str, details: str = "") -> None:
        self.logs.append(MaintenanceLogEntry.create(operator, action, details))
        self.updated_at = datetime.now()

    def can_accept(self, user_role: str) -> bool:
        if self.status != MaintenanceOrderStatus.PENDING:
            return False
        return user_role in ["维修人员", "管理员"]

    def can_process(self, username: str, user_role: str) -> bool:
        if self.status != MaintenanceOrderStatus.IN_PROGRESS:
            return False
        if user_role in ["管理员"]:
            return True
        return self.assignee == username

    def can_complete(self, username: str, user_role: str) -> bool:
        return self.can_process(username, user_role)

    def can_reject(self, username: str, user_role: str) -> bool:
        if self.status not in [MaintenanceOrderStatus.PENDING, MaintenanceOrderStatus.IN_PROGRESS]:
            return False
        return user_role in ["维修人员", "管理员"]

    def can_view(self, username: str, user_role: str) -> bool:
        if user_role in ["维修人员", "管理员"]:
            return True
        return self.requester == username

    def accept(self, assignee: str) -> None:
        self.status = MaintenanceOrderStatus.IN_PROGRESS
        self.assignee = assignee
        self.accepted_at = datetime.now()
        self.add_log(assignee, "接单", "开始处理维修工单")

    def add_processing_note(self, operator: str, note: str) -> None:
        self.add_log(operator, "补充处理记录", note)

    def complete(self, operator: str, completion_option: MaintenanceCompletionOption,
                 notes: str = "") -> None:
        self.status = MaintenanceOrderStatus.COMPLETED
        self.completion_option = completion_option
        self.completed_at = datetime.now()
        details = f"完成方式: {completion_option.value}"
        if notes:
            details += f", 备注: {notes}"
        self.add_log(operator, "完成维修", details)

    def reject(self, operator: str, reason: str) -> None:
        self.status = MaintenanceOrderStatus.REJECTED
        self.rejection_reason = reason
        self.completed_at = datetime.now()
        self.add_log(operator, "驳回工单", f"驳回原因: {reason}")

    def is_active(self) -> bool:
        return self.status in [MaintenanceOrderStatus.PENDING, MaintenanceOrderStatus.IN_PROGRESS]

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'instrument_id': self.instrument_id,
            'instrument_name': self.instrument_name,
            'serial_number': self.serial_number,
            'requester': self.requester,
            'fault_description': self.fault_description,
            'priority': self.priority.value,
            'expected_completion_date': self.expected_completion_date.isoformat() if self.expected_completion_date else None,
            'assignee': self.assignee,
            'status': self.status.value,
            'completion_option': self.completion_option.value if self.completion_option else None,
            'rejection_reason': self.rejection_reason,
            'logs': [log.to_dict() for log in self.logs],
            'created_at': self.created_at.isoformat(),
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MaintenanceOrder':
        expected_date = None
        if data.get('expected_completion_date'):
            expected_date = date.fromisoformat(data['expected_completion_date'])

        completion_option = None
        if data.get('completion_option'):
            completion_option = MaintenanceCompletionOption(data['completion_option'])

        accepted_at = None
        if data.get('accepted_at'):
            accepted_at = datetime.fromisoformat(data['accepted_at'])

        completed_at = None
        if data.get('completed_at'):
            completed_at = datetime.fromisoformat(data['completed_at'])

        logs = []
        if 'logs' in data:
            logs = [MaintenanceLogEntry.from_dict(log_data) for log_data in data['logs']]

        return cls(
            id=data['id'],
            instrument_id=data['instrument_id'],
            instrument_name=data['instrument_name'],
            serial_number=data['serial_number'],
            requester=data['requester'],
            fault_description=data['fault_description'],
            priority=MaintenancePriority(data['priority']),
            expected_completion_date=expected_date,
            assignee=data.get('assignee'),
            status=MaintenanceOrderStatus(data['status']),
            completion_option=completion_option,
            rejection_reason=data.get('rejection_reason', ''),
            logs=logs,
            created_at=datetime.fromisoformat(data['created_at']),
            accepted_at=accepted_at,
            completed_at=completed_at,
            updated_at=datetime.fromisoformat(data['updated_at']),
        )
