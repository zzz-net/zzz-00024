from dataclasses import dataclass, field
from enum import Enum
from datetime import date, datetime
from typing import Optional
import uuid


class BorrowStatus(str, Enum):
    BORROWED = "借出中"
    RETURNED = "已归还"


@dataclass
class BorrowRecord:
    id: str
    instrument_id: str
    borrower: str
    borrower_department: str
    borrow_date: date
    expected_return_date: date
    actual_return_date: Optional[date] = None
    purpose: str = ""
    notes: str = ""
    status: BorrowStatus = BorrowStatus.BORROWED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, instrument_id: str, borrower: str, borrower_department: str,
               borrow_date: date, expected_return_date: date,
               purpose: str = "", notes: str = "") -> 'BorrowRecord':
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            borrower=borrower,
            borrower_department=borrower_department,
            borrow_date=borrow_date,
            expected_return_date=expected_return_date,
            purpose=purpose,
            notes=notes,
            status=BorrowStatus.BORROWED,
            created_at=now,
            updated_at=now
        )

    def is_returned(self) -> bool:
        return self.status == BorrowStatus.RETURNED

    def can_return(self) -> tuple[bool, str]:
        if self.is_returned():
            return False, "该借用记录已归还，不能重复归还"
        return True, ""

    def mark_returned(self, return_date: Optional[date] = None, notes: str = "") -> None:
        self.actual_return_date = return_date or date.today()
        self.status = BorrowStatus.RETURNED
        if notes:
            self.notes = (self.notes + "\n" if self.notes else "") + f"归还备注: {notes}"
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'instrument_id': self.instrument_id,
            'borrower': self.borrower,
            'borrower_department': self.borrower_department,
            'borrow_date': self.borrow_date.isoformat(),
            'expected_return_date': self.expected_return_date.isoformat(),
            'actual_return_date': self.actual_return_date.isoformat() if self.actual_return_date else None,
            'purpose': self.purpose,
            'notes': self.notes,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BorrowRecord':
        actual_return_date = None
        if data.get('actual_return_date'):
            actual_return_date = date.fromisoformat(data['actual_return_date'])
        
        return cls(
            id=data['id'],
            instrument_id=data['instrument_id'],
            borrower=data['borrower'],
            borrower_department=data['borrower_department'],
            borrow_date=date.fromisoformat(data['borrow_date']),
            expected_return_date=date.fromisoformat(data['expected_return_date']),
            actual_return_date=actual_return_date,
            purpose=data.get('purpose', ''),
            notes=data.get('notes', ''),
            status=BorrowStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
        )
