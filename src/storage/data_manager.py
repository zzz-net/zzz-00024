import json
import os
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from ..models import (
    Instrument, InstrumentStatus,
    BorrowRecord,
    OperationHistory,
    CalibrationRecord,
    User, UserRole,
)


class DataManager:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            app_data = os.environ.get('APPDATA') or os.environ.get('HOME') or '.'
            self.data_dir = os.path.join(app_data, 'lab_instrument_manager')
        else:
            self.data_dir = data_dir
        
        self.data_file = os.path.join(self.data_dir, 'data.json')
        self.settings_file = os.path.join(self.data_dir, 'settings.json')
        self._ensure_data_dir()
        self._data = self._load_data()

    def _ensure_data_dir(self) -> None:
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.data_file):
            return self._get_empty_data()
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return self._convert_from_json(data)
        except (json.JSONDecodeError, FileNotFoundError):
            return self._get_empty_data()

    def _get_empty_data(self) -> Dict[str, Any]:
        return {
            'instruments': [],
            'borrow_records': [],
            'operation_histories': [],
            'calibration_records': [],
            'current_user': User.create_normal_user('user', '普通用户').to_dict(),
            'settings': {
                'export_dir': os.path.join(os.path.expanduser('~'), 'Documents', 'LabExports'),
                'last_filters': {
                    'status': '',
                    'category': '',
                    'search': '',
                },
            },
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'version': '1.0',
            },
        }

    def _convert_from_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = self._get_empty_data()
        
        if 'instruments' in data:
            result['instruments'] = [
                Instrument.from_dict(item) for item in data['instruments']
            ]
        
        if 'borrow_records' in data:
            result['borrow_records'] = [
                BorrowRecord.from_dict(item) for item in data['borrow_records']
            ]
        
        if 'operation_histories' in data:
            result['operation_histories'] = [
                OperationHistory.from_dict(item) for item in data['operation_histories']
            ]
        
        if 'calibration_records' in data:
            result['calibration_records'] = [
                CalibrationRecord.from_dict(item) for item in data['calibration_records']
            ]
        
        if 'current_user' in data:
            result['current_user'] = data['current_user']
        
        if 'settings' in data:
            result['settings'].update(data['settings'])
        
        return result

    def _convert_to_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'instruments': [item.to_dict() for item in data['instruments']],
            'borrow_records': [item.to_dict() for item in data['borrow_records']],
            'operation_histories': [item.to_dict() for item in data['operation_histories']],
            'calibration_records': [item.to_dict() for item in data['calibration_records']],
            'current_user': data['current_user'],
            'settings': data['settings'],
            'metadata': {
                'created_at': data['metadata']['created_at'],
                'updated_at': datetime.now().isoformat(),
                'version': '1.0',
            },
        }

    def save(self) -> None:
        self._ensure_data_dir()
        data_to_save = self._convert_to_json(self._data)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)

    def has_data(self) -> bool:
        return len(self._data['instruments']) > 0

    def get_current_user(self) -> User:
        return User.from_dict(self._data['current_user'])

    def set_current_user(self, user: User) -> None:
        self._data['current_user'] = user.to_dict()
        self.save()

    def get_settings(self) -> Dict[str, Any]:
        return self._data['settings']

    def update_settings(self, settings: Dict[str, Any]) -> None:
        self._data['settings'].update(settings)
        self.save()

    def get_instruments(self) -> List[Instrument]:
        return self._data['instruments']

    def get_instrument_by_id(self, instrument_id: str) -> Optional[Instrument]:
        for instr in self._data['instruments']:
            if instr.id == instrument_id:
                return instr
        return None

    def add_instrument(self, instrument: Instrument) -> None:
        self._data['instruments'].append(instrument)
        self.save()

    def update_instrument(self, instrument: Instrument) -> None:
        for i, instr in enumerate(self._data['instruments']):
            if instr.id == instrument.id:
                instrument.updated_at = datetime.now()
                self._data['instruments'][i] = instrument
                self.save()
                return
        raise ValueError(f"Instrument with id {instrument.id} not found")

    def delete_instrument(self, instrument_id: str) -> None:
        self._data['instruments'] = [
            instr for instr in self._data['instruments'] if instr.id != instrument_id
        ]
        self.save()

    def get_borrow_records(self, instrument_id: Optional[str] = None) -> List[BorrowRecord]:
        records = self._data['borrow_records']
        if instrument_id:
            records = [r for r in records if r.instrument_id == instrument_id]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def get_active_borrow_record(self, instrument_id: str) -> Optional[BorrowRecord]:
        for record in self._data['borrow_records']:
            if record.instrument_id == instrument_id and not record.is_returned():
                return record
        return None

    def add_borrow_record(self, record: BorrowRecord) -> None:
        self._data['borrow_records'].append(record)
        self.save()

    def update_borrow_record(self, record: BorrowRecord) -> None:
        for i, r in enumerate(self._data['borrow_records']):
            if r.id == record.id:
                self._data['borrow_records'][i] = record
                self.save()
                return
        raise ValueError(f"BorrowRecord with id {record.id} not found")

    def get_operation_histories(self, instrument_id: Optional[str] = None) -> List[OperationHistory]:
        histories = self._data['operation_histories']
        if instrument_id:
            histories = [h for h in histories if h.instrument_id == instrument_id]
        return sorted(histories, key=lambda h: h.timestamp, reverse=True)

    def add_operation_history(self, history: OperationHistory) -> None:
        self._data['operation_histories'].append(history)
        self.save()

    def get_calibration_records(self, instrument_id: Optional[str] = None) -> List[CalibrationRecord]:
        records = self._data['calibration_records']
        if instrument_id:
            records = [r for r in records if r.instrument_id == instrument_id]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def add_calibration_record(self, record: CalibrationRecord) -> None:
        self._data['calibration_records'].append(record)
        self.save()

    def clear_all_data(self) -> None:
        self._data = self._get_empty_data()
        self.save()

    def refresh_instrument_statuses(self) -> None:
        for instr in self._data['instruments']:
            if instr.status == InstrumentStatus.BORROWED:
                continue
            if instr.status == InstrumentStatus.MAINTENANCE:
                continue
            if instr.status == InstrumentStatus.FROZEN:
                continue
            
            if instr.is_calibration_expired():
                instr.status = InstrumentStatus.CALIBRATION_EXPIRED
            elif instr.is_calibration_due_soon(30):
                instr.status = InstrumentStatus.CALIBRATION_DUE
            else:
                instr.status = InstrumentStatus.AVAILABLE
        self.save()
