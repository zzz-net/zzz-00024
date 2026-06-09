from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import uuid


@dataclass
class CalibrationRecord:
    id: str
    instrument_id: str
    calibration_date: date
    next_calibration_date: date
    certificate_number: str
    calibration_agency: str
    result: str = "合格"
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, instrument_id: str, calibration_date: date, 
               next_calibration_date: date, certificate_number: str,
               calibration_agency: str, result: str = "合格", 
               notes: str = "") -> 'CalibrationRecord':
        return cls(
            id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            calibration_date=calibration_date,
            next_calibration_date=next_calibration_date,
            certificate_number=certificate_number,
            calibration_agency=calibration_agency,
            result=result,
            notes=notes,
        )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'instrument_id': self.instrument_id,
            'calibration_date': self.calibration_date.isoformat(),
            'next_calibration_date': self.next_calibration_date.isoformat(),
            'certificate_number': self.certificate_number,
            'calibration_agency': self.calibration_agency,
            'result': self.result,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CalibrationRecord':
        return cls(
            id=data['id'],
            instrument_id=data['instrument_id'],
            calibration_date=date.fromisoformat(data['calibration_date']),
            next_calibration_date=date.fromisoformat(data['next_calibration_date']),
            certificate_number=data['certificate_number'],
            calibration_agency=data['calibration_agency'],
            result=data.get('result', '合格'),
            notes=data.get('notes', ''),
            created_at=datetime.fromisoformat(data['created_at']),
        )
