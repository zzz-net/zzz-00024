from dataclasses import dataclass, field
from enum import Enum
from datetime import date, datetime
from typing import Optional
import uuid


class ReservationStatus(str, Enum):
    PENDING = "待审批"
    APPROVED = "已审批"
    REJECTED = "已拒绝"
    CANCELLED = "已取消"
    FULFILLED = "已领用"
    RESCHEDULED = "已改期"


@dataclass
class Reservation:
    id: str
    inventory_item_id: str
    requester: str
    department: str
    quantity: int
    expected_use_date: date
    purpose: str = ""
    notes: str = ""
    status: ReservationStatus = ReservationStatus.PENDING
    approver: Optional[str] = None
    approved_at: Optional[datetime] = None
    original_reservation_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, inventory_item_id: str, requester: str, department: str,
               quantity: int, expected_use_date: date, purpose: str = "",
               notes: str = "", original_reservation_id: Optional[str] = None
               ) -> 'Reservation':
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            inventory_item_id=inventory_item_id,
            requester=requester,
            department=department,
            quantity=quantity,
            expected_use_date=expected_use_date,
            purpose=purpose,
            notes=notes,
            status=ReservationStatus.PENDING,
            approver=None,
            approved_at=None,
            original_reservation_id=original_reservation_id,
            created_at=now,
            updated_at=now
        )

    def can_approve(self) -> tuple[bool, str]:
        if self.status != ReservationStatus.PENDING:
            return False, f"当前状态为{self.status.value}，无法审批"
        return True, ""

    def can_reject(self) -> tuple[bool, str]:
        if self.status != ReservationStatus.PENDING:
            return False, f"当前状态为{self.status.value}，无法拒绝"
        return True, ""

    def can_cancel(self) -> tuple[bool, str]:
        if self.status in [ReservationStatus.FULFILLED, ReservationStatus.CANCELLED, ReservationStatus.REJECTED, ReservationStatus.RESCHEDULED]:
            return False, f"当前状态为{self.status.value}，无法取消"
        return True, ""

    def can_reschedule(self) -> tuple[bool, str]:
        if self.status not in [ReservationStatus.APPROVED, ReservationStatus.PENDING]:
            return False, f"当前状态为{self.status.value}，无法改期"
        return True, ""

    def can_fulfill(self) -> tuple[bool, str]:
        if self.status != ReservationStatus.APPROVED:
            return False, f"当前状态为{self.status.value}，无法领用"
        return True, ""

    def requires_locking(self) -> bool:
        return self.status == ReservationStatus.APPROVED

    def mark_approved(self, approver: str) -> None:
        self.status = ReservationStatus.APPROVED
        self.approver = approver
        self.approved_at = datetime.now()
        self.updated_at = datetime.now()

    def mark_rejected(self, approver: str, reason: str = "") -> None:
        self.status = ReservationStatus.REJECTED
        self.approver = approver
        self.approved_at = datetime.now()
        if reason:
            self.notes = (self.notes + "\n" if self.notes else "") + f"拒绝原因: {reason}"
        self.updated_at = datetime.now()

    def mark_cancelled(self, canceller: str, reason: str = "") -> None:
        self.status = ReservationStatus.CANCELLED
        if reason:
            self.notes = (self.notes + "\n" if self.notes else "") + f"取消原因: {reason}，操作人: {canceller}"
        self.updated_at = datetime.now()

    def mark_rescheduled(self, new_reservation_id: str) -> None:
        self.status = ReservationStatus.RESCHEDULED
        self.notes = (self.notes + "\n" if self.notes else "") + f"已改期，新预约ID: {new_reservation_id}"
        self.updated_at = datetime.now()

    def mark_fulfilled(self, operator: str) -> None:
        self.status = ReservationStatus.FULFILLED
        self.notes = (self.notes + "\n" if self.notes else "") + f"已领用，操作人: {operator}"
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'inventory_item_id': self.inventory_item_id,
            'requester': self.requester,
            'department': self.department,
            'quantity': self.quantity,
            'expected_use_date': self.expected_use_date.isoformat(),
            'purpose': self.purpose,
            'notes': self.notes,
            'status': self.status.value,
            'approver': self.approver,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'original_reservation_id': self.original_reservation_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Reservation':
        return cls(
            id=data['id'],
            inventory_item_id=data['inventory_item_id'],
            requester=data['requester'],
            department=data['department'],
            quantity=data['quantity'],
            expected_use_date=date.fromisoformat(data['expected_use_date']),
            purpose=data.get('purpose', ''),
            notes=data.get('notes', ''),
            status=ReservationStatus(data['status']),
            approver=data.get('approver'),
            approved_at=datetime.fromisoformat(data['approved_at']) if data.get('approved_at') else None,
            original_reservation_id=data.get('original_reservation_id'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
        )
