import json
import os
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime

from ..models import (
    Instrument, InstrumentStatus,
    BorrowRecord,
    OperationHistory,
    CalibrationRecord,
    User, UserRole,
    InventoryItem,
    Reservation,
    InventoryCheck, InventoryCheckStatus,
    InventoryCheckConflict, ConflictType, ConflictResolution,
    CalibrationSchedule, CalibrationScheduleStatus,
    CalibrationScheduleItem, CalibrationScheduleItemStatus,
    CalibrationScheduleConflict, CalibrationConflictType, CalibrationConflictResolution,
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
            'inventory_items': [],
            'reservations': [],
            'inventory_checks': [],
            'inventory_check_conflicts': [],
            'calibration_schedules': [],
            'calibration_schedule_items': [],
            'calibration_schedule_conflicts': [],
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
        
        if 'inventory_items' in data:
            result['inventory_items'] = [
                InventoryItem.from_dict(item) for item in data['inventory_items']
            ]
        
        if 'reservations' in data:
            result['reservations'] = [
                Reservation.from_dict(item) for item in data['reservations']
            ]
        
        if 'inventory_checks' in data:
            result['inventory_checks'] = [
                InventoryCheck.from_dict(item) for item in data['inventory_checks']
            ]
        
        if 'inventory_check_conflicts' in data:
            result['inventory_check_conflicts'] = [
                InventoryCheckConflict.from_dict(item) for item in data['inventory_check_conflicts']
            ]
        
        if 'calibration_schedules' in data:
            result['calibration_schedules'] = [
                CalibrationSchedule.from_dict(item) for item in data['calibration_schedules']
            ]
        
        if 'calibration_schedule_items' in data:
            result['calibration_schedule_items'] = [
                CalibrationScheduleItem.from_dict(item) for item in data['calibration_schedule_items']
            ]
        
        if 'calibration_schedule_conflicts' in data:
            result['calibration_schedule_conflicts'] = [
                CalibrationScheduleConflict.from_dict(item) for item in data['calibration_schedule_conflicts']
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
            'inventory_items': [item.to_dict() for item in data['inventory_items']],
            'reservations': [item.to_dict() for item in data['reservations']],
            'inventory_checks': [item.to_dict() for item in data['inventory_checks']],
            'inventory_check_conflicts': [item.to_dict() for item in data['inventory_check_conflicts']],
            'calibration_schedules': [item.to_dict() for item in data['calibration_schedules']],
            'calibration_schedule_items': [item.to_dict() for item in data['calibration_schedule_items']],
            'calibration_schedule_conflicts': [item.to_dict() for item in data['calibration_schedule_conflicts']],
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

    def get_inventory_items(self) -> List[InventoryItem]:
        return self._data['inventory_items']

    def get_inventory_item_by_id(self, item_id: str) -> Optional[InventoryItem]:
        for item in self._data['inventory_items']:
            if item.id == item_id:
                return item
        return None

    def add_inventory_item(self, item: InventoryItem) -> None:
        self._data['inventory_items'].append(item)
        self.save()

    def update_inventory_item(self, item: InventoryItem) -> None:
        for i, existing in enumerate(self._data['inventory_items']):
            if existing.id == item.id:
                item.updated_at = datetime.now()
                self._data['inventory_items'][i] = item
                self.save()
                return
        raise ValueError(f"InventoryItem with id {item.id} not found")

    def delete_inventory_item(self, item_id: str) -> None:
        self._data['inventory_items'] = [
            item for item in self._data['inventory_items'] if item.id != item_id
        ]
        self.save()

    def get_reservations(self, inventory_item_id: Optional[str] = None) -> List[Reservation]:
        reservations = self._data['reservations']
        if inventory_item_id:
            reservations = [r for r in reservations if r.inventory_item_id == inventory_item_id]
        return sorted(reservations, key=lambda r: r.created_at, reverse=True)

    def get_reservation_by_id(self, reservation_id: str) -> Optional[Reservation]:
        for r in self._data['reservations']:
            if r.id == reservation_id:
                return r
        return None

    def add_reservation(self, reservation: Reservation) -> None:
        self._data['reservations'].append(reservation)
        self.save()

    def update_reservation(self, reservation: Reservation) -> None:
        for i, existing in enumerate(self._data['reservations']):
            if existing.id == reservation.id:
                reservation.updated_at = datetime.now()
                self._data['reservations'][i] = reservation
                self.save()
                return
        raise ValueError(f"Reservation with id {reservation.id} not found")

    def recalculate_locked_quantities(self) -> None:
        for item in self._data['inventory_items']:
            locked = 0
            for r in self._data['reservations']:
                if r.inventory_item_id == item.id and r.requires_locking():
                    locked += r.quantity
            item.locked_quantity = locked
        self.save()

    def get_inventory_checks(self) -> List[InventoryCheck]:
        return sorted(self._data['inventory_checks'], key=lambda c: c.created_at, reverse=True)

    def get_inventory_check_by_id(self, check_id: str) -> Optional[InventoryCheck]:
        for c in self._data['inventory_checks']:
            if c.id == check_id:
                return c
        return None

    def get_latest_inventory_check(self) -> Optional[InventoryCheck]:
        checks = self.get_inventory_checks()
        return checks[0] if checks else None

    def add_inventory_check(self, check: InventoryCheck) -> None:
        self._data['inventory_checks'].append(check)
        self.save()

    def update_inventory_check(self, check: InventoryCheck) -> None:
        for i, existing in enumerate(self._data['inventory_checks']):
            if existing.id == check.id:
                self._data['inventory_checks'][i] = check
                self.save()
                return
        raise ValueError(f"InventoryCheck with id {check.id} not found")

    def get_inventory_check_conflicts(self, check_id: Optional[str] = None) -> List[InventoryCheckConflict]:
        conflicts = self._data['inventory_check_conflicts']
        if check_id:
            conflicts = [c for c in conflicts if c.inventory_check_id == check_id]
        return sorted(conflicts, key=lambda c: c.created_at)

    def get_conflict_by_id(self, conflict_id: str) -> Optional[InventoryCheckConflict]:
        for c in self._data['inventory_check_conflicts']:
            if c.id == conflict_id:
                return c
        return None

    def add_inventory_check_conflict(self, conflict: InventoryCheckConflict) -> None:
        self._data['inventory_check_conflicts'].append(conflict)
        self.save()

    def update_inventory_check_conflict(self, conflict: InventoryCheckConflict) -> None:
        for i, existing in enumerate(self._data['inventory_check_conflicts']):
            if existing.id == conflict.id:
                self._data['inventory_check_conflicts'][i] = conflict
                self.save()
                return
        raise ValueError(f"InventoryCheckConflict with id {conflict.id} not found")

    def add_conflicts_batch(self, conflicts: List[InventoryCheckConflict]) -> None:
        self._data['inventory_check_conflicts'].extend(conflicts)
        self.save()

    def get_calibration_schedules(self) -> List[CalibrationSchedule]:
        return sorted(self._data['calibration_schedules'], key=lambda c: c.created_at, reverse=True)

    def get_calibration_schedule_by_id(self, schedule_id: str) -> Optional[CalibrationSchedule]:
        for c in self._data['calibration_schedules']:
            if c.id == schedule_id:
                return c
        return None

    def get_latest_calibration_schedule(self) -> Optional[CalibrationSchedule]:
        schedules = self.get_calibration_schedules()
        return schedules[0] if schedules else None

    def add_calibration_schedule(self, schedule: CalibrationSchedule) -> None:
        self._data['calibration_schedules'].append(schedule)
        self.save()

    def update_calibration_schedule(self, schedule: CalibrationSchedule) -> None:
        for i, existing in enumerate(self._data['calibration_schedules']):
            if existing.id == schedule.id:
                self._data['calibration_schedules'][i] = schedule
                self.save()
                return
        raise ValueError(f"CalibrationSchedule with id {schedule.id} not found")

    def get_calibration_schedule_items(self, schedule_id: Optional[str] = None,
                                        instrument_id: Optional[str] = None) -> List[CalibrationScheduleItem]:
        items = self._data['calibration_schedule_items']
        if schedule_id:
            items = [i for i in items if i.schedule_id == schedule_id]
        if instrument_id:
            items = [i for i in items if i.instrument_id == instrument_id]
        return sorted(items, key=lambda i: i.planned_date)

    def get_calibration_schedule_item_by_id(self, item_id: str) -> Optional[CalibrationScheduleItem]:
        for i in self._data['calibration_schedule_items']:
            if i.id == item_id:
                return i
        return None

    def add_calibration_schedule_item(self, item: CalibrationScheduleItem) -> None:
        self._data['calibration_schedule_items'].append(item)
        self.save()

    def update_calibration_schedule_item(self, item: CalibrationScheduleItem) -> None:
        for i, existing in enumerate(self._data['calibration_schedule_items']):
            if existing.id == item.id:
                item.updated_at = datetime.now()
                self._data['calibration_schedule_items'][i] = item
                self.save()
                return
        raise ValueError(f"CalibrationScheduleItem with id {item.id} not found")

    def add_calibration_schedule_items_batch(self, items: List[CalibrationScheduleItem]) -> None:
        self._data['calibration_schedule_items'].extend(items)
        self.save()

    def get_calibration_schedule_conflicts(self, schedule_id: Optional[str] = None) -> List[CalibrationScheduleConflict]:
        conflicts = self._data['calibration_schedule_conflicts']
        if schedule_id:
            conflicts = [c for c in conflicts if c.schedule_id == schedule_id]
        return sorted(conflicts, key=lambda c: c.created_at)

    def get_calibration_schedule_conflict_by_id(self, conflict_id: str) -> Optional[CalibrationScheduleConflict]:
        for c in self._data['calibration_schedule_conflicts']:
            if c.id == conflict_id:
                return c
        return None

    def add_calibration_schedule_conflict(self, conflict: CalibrationScheduleConflict) -> None:
        self._data['calibration_schedule_conflicts'].append(conflict)
        self.save()

    def update_calibration_schedule_conflict(self, conflict: CalibrationScheduleConflict) -> None:
        for i, existing in enumerate(self._data['calibration_schedule_conflicts']):
            if existing.id == conflict.id:
                self._data['calibration_schedule_conflicts'][i] = conflict
                self.save()
                return
        raise ValueError(f"CalibrationScheduleConflict with id {conflict.id} not found")

    def add_calibration_schedule_conflicts_batch(self, conflicts: List[CalibrationScheduleConflict]) -> None:
        self._data['calibration_schedule_conflicts'].extend(conflicts)
        self.save()

    def refresh_calibration_schedule_statuses(self) -> None:
        for schedule in self._data['calibration_schedules']:
            if schedule.status in [CalibrationScheduleStatus.COMPLETED, CalibrationScheduleStatus.CANCELLED]:
                continue
            items = self.get_calibration_schedule_items(schedule.id)
            schedule.refresh_status(items)
            self.save()

    def can_undo_last_calibration_schedule(self) -> Tuple[bool, Optional[CalibrationScheduleItem]]:
        items = self.get_calibration_schedule_items()
        undoable = [item for item in items if item.undo_snapshot is not None]
        undoable.sort(key=lambda x: x.processed_at or datetime.min, reverse=True)
        return (True, undoable[0]) if undoable else (False, None)
