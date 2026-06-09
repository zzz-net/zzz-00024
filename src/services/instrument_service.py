from typing import List, Optional, Tuple, Dict, Any
from datetime import date, datetime, timedelta
import csv
import json
import os

from ..models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    BorrowRecord, BorrowStatus,
    OperationHistory, OperationType,
    CalibrationRecord,
    User, UserRole,
    InventoryItem,
    Reservation, ReservationStatus,
    InventoryCheck, InventoryCheckStatus,
    InventoryCheckConflict, ConflictType, ConflictResolution,
)
from ..storage import DataManager


class InstrumentService:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self.refresh_statuses()
        self.recalculate_locked_quantities()

    def refresh_statuses(self) -> None:
        self.data_manager.refresh_instrument_statuses()

    def get_current_user(self) -> User:
        return self.data_manager.get_current_user()

    def set_current_user(self, user: User) -> None:
        self.data_manager.set_current_user(user)

    def get_instruments(self, status_filter: Optional[str] = None,
                        category_filter: Optional[str] = None,
                        search_text: Optional[str] = None) -> List[Instrument]:
        instruments = self.data_manager.get_instruments()
        
        if status_filter:
            instruments = [i for i in instruments if i.status.value == status_filter]
        
        if category_filter:
            instruments = [i for i in instruments if i.category.value == category_filter]
        
        if search_text:
            search_lower = search_text.lower()
            instruments = [
                i for i in instruments
                if search_lower in i.name.lower()
                or search_lower in i.serial_number.lower()
                or search_lower in i.model.lower()
                or search_lower in i.manager.lower()
            ]
        
        return sorted(instruments, key=lambda i: i.created_at, reverse=True)

    def get_instrument_by_id(self, instrument_id: str) -> Optional[Instrument]:
        return self.data_manager.get_instrument_by_id(instrument_id)

    def create_instrument(self, name: str, category: InstrumentCategory, model: str,
                          serial_number: str, location: str, manager: str,
                          calibration_due_date: Optional[date] = None,
                          description: str = "") -> Instrument:
        user = self.get_current_user()
        instrument = Instrument.create(
            name=name,
            category=category,
            model=model,
            serial_number=serial_number,
            location=location,
            manager=manager,
            calibration_due_date=calibration_due_date,
            description=description,
        )
        
        if instrument.is_calibration_expired():
            instrument.status = InstrumentStatus.CALIBRATION_EXPIRED
        elif instrument.is_calibration_due_soon(30):
            instrument.status = InstrumentStatus.CALIBRATION_DUE
        
        self.data_manager.add_instrument(instrument)
        
        history = OperationHistory.create(
            instrument_id=instrument.id,
            operation_type=OperationType.CREATE,
            operator=user.display_name,
            details=f"新增仪器: {name} ({model})",
        )
        self.data_manager.add_operation_history(history)
        
        return instrument

    def update_instrument(self, instrument: Instrument, **kwargs) -> Instrument:
        user = self.get_current_user()
        
        changes = []
        for key, value in kwargs.items():
            if hasattr(instrument, key) and getattr(instrument, key) != value:
                setattr(instrument, key, value)
                changes.append(f"{key}: {value}")
        
        if instrument.is_calibration_expired():
            instrument.status = InstrumentStatus.CALIBRATION_EXPIRED
        elif instrument.is_calibration_due_soon(30):
            instrument.status = InstrumentStatus.CALIBRATION_DUE
        elif instrument.status in [InstrumentStatus.CALIBRATION_DUE, InstrumentStatus.CALIBRATION_EXPIRED]:
            instrument.status = InstrumentStatus.AVAILABLE
        
        self.data_manager.update_instrument(instrument)
        
        if changes:
            history = OperationHistory.create(
                instrument_id=instrument.id,
                operation_type=OperationType.UPDATE,
                operator=user.display_name,
                details=f"更新信息: {'; '.join(changes)}",
            )
            self.data_manager.add_operation_history(history)
        
        return instrument

    def delete_instrument(self, instrument_id: str) -> None:
        self.data_manager.delete_instrument(instrument_id)

    def borrow_instrument(self, instrument_id: str, borrower: str,
                          borrower_department: str, borrow_date: date,
                          expected_return_date: date, purpose: str = "",
                          notes: str = "") -> Tuple[bool, str, Optional[BorrowRecord]]:
        user = self.get_current_user()
        instrument = self.get_instrument_by_id(instrument_id)
        
        if not instrument:
            return False, "仪器不存在", None
        
        can_borrow, reason = instrument.can_borrow()
        if not can_borrow:
            return False, reason, None
        
        if expected_return_date < borrow_date:
            return False, "预计归还日期不能早于借用日期", None
        
        existing_record = self.data_manager.get_active_borrow_record(instrument_id)
        if existing_record:
            return False, "该仪器已有未归还的借用记录", None
        
        borrow_record = BorrowRecord.create(
            instrument_id=instrument_id,
            borrower=borrower,
            borrower_department=borrower_department,
            borrow_date=borrow_date,
            expected_return_date=expected_return_date,
            purpose=purpose,
            notes=notes,
        )
        
        self.data_manager.add_borrow_record(borrow_record)
        
        instrument.status = InstrumentStatus.BORROWED
        self.data_manager.update_instrument(instrument)
        
        history = OperationHistory.create(
            instrument_id=instrument_id,
            operation_type=OperationType.BORROW,
            operator=user.display_name,
            details=f"借给 {borrower} ({borrower_department}), 用途: {purpose}",
            related_record_id=borrow_record.id,
        )
        self.data_manager.add_operation_history(history)
        
        return True, "借出成功", borrow_record

    def return_instrument(self, borrow_record_id: str, return_date: Optional[date] = None,
                          notes: str = "") -> Tuple[bool, str, Optional[BorrowRecord]]:
        user = self.get_current_user()
        
        all_records = self.data_manager.get_borrow_records()
        borrow_record = None
        for r in all_records:
            if r.id == borrow_record_id:
                borrow_record = r
                break
        
        if not borrow_record:
            return False, "借用记录不存在", None
        
        can_return, reason = borrow_record.can_return()
        if not can_return:
            return False, reason, None
        
        borrow_record.mark_returned(return_date, notes)
        self.data_manager.update_borrow_record(borrow_record)
        
        instrument = self.get_instrument_by_id(borrow_record.instrument_id)
        if instrument:
            if instrument.is_calibration_expired():
                instrument.status = InstrumentStatus.CALIBRATION_EXPIRED
            elif instrument.is_calibration_due_soon(30):
                instrument.status = InstrumentStatus.CALIBRATION_DUE
            else:
                instrument.status = InstrumentStatus.AVAILABLE
            self.data_manager.update_instrument(instrument)
        
        history = OperationHistory.create(
            instrument_id=borrow_record.instrument_id,
            operation_type=OperationType.RETURN,
            operator=user.display_name,
            details=f"归还确认, 借用人: {borrow_record.borrower}",
            related_record_id=borrow_record.id,
        )
        self.data_manager.add_operation_history(history)
        
        return True, "归还成功", borrow_record

    def calibrate_instrument(self, instrument_id: str, calibration_date: date,
                             next_calibration_date: date, certificate_number: str,
                             calibration_agency: str, result: str = "合格",
                             notes: str = "") -> Tuple[bool, str, Optional[CalibrationRecord]]:
        user = self.get_current_user()
        
        if not user.can_calibrate():
            return False, "您没有校准仪器的权限", None
        
        instrument = self.get_instrument_by_id(instrument_id)
        if not instrument:
            return False, "仪器不存在", None
        
        if next_calibration_date <= calibration_date:
            return False, "下次校准日期必须晚于本次校准日期", None
        
        calibration_record = CalibrationRecord.create(
            instrument_id=instrument_id,
            calibration_date=calibration_date,
            next_calibration_date=next_calibration_date,
            certificate_number=certificate_number,
            calibration_agency=calibration_agency,
            result=result,
            notes=notes,
        )
        
        self.data_manager.add_calibration_record(calibration_record)
        
        instrument.calibration_due_date = next_calibration_date
        
        was_frozen = instrument.status == InstrumentStatus.FROZEN
        
        if instrument.is_calibration_expired():
            instrument.status = InstrumentStatus.CALIBRATION_EXPIRED
        elif instrument.is_calibration_due_soon(30):
            instrument.status = InstrumentStatus.CALIBRATION_DUE
        else:
            instrument.status = InstrumentStatus.AVAILABLE
        
        self.data_manager.update_instrument(instrument)
        
        details = f"校准完成, 证书编号: {certificate_number}, 机构: {calibration_agency}, 结果: {result}"
        if was_frozen:
            details += " (已自动解冻)"
        
        history = OperationHistory.create(
            instrument_id=instrument_id,
            operation_type=OperationType.CALIBRATION,
            operator=user.display_name,
            details=details,
            related_record_id=calibration_record.id,
        )
        self.data_manager.add_operation_history(history)
        
        return True, "校准录入成功", calibration_record

    def freeze_instrument(self, instrument_id: str, reason: str = "") -> Tuple[bool, str]:
        user = self.get_current_user()
        
        if not user.can_freeze():
            return False, "您没有冻结仪器的权限"
        
        instrument = self.get_instrument_by_id(instrument_id)
        if not instrument:
            return False, "仪器不存在"
        
        if instrument.status == InstrumentStatus.FROZEN:
            return False, "仪器已处于冻结状态"
        
        if instrument.status == InstrumentStatus.BORROWED:
            return False, "借出中的仪器不能冻结"
        
        instrument.status = InstrumentStatus.FROZEN
        self.data_manager.update_instrument(instrument)
        
        history = OperationHistory.create(
            instrument_id=instrument_id,
            operation_type=OperationType.FREEZE,
            operator=user.display_name,
            details=f"冻结原因: {reason}" if reason else "冻结",
        )
        self.data_manager.add_operation_history(history)
        
        return True, "冻结成功"

    def unfreeze_instrument(self, instrument_id: str, reason: str = "") -> Tuple[bool, str]:
        user = self.get_current_user()
        
        if not user.can_unfreeze_maintenance():
            return False, "您没有解冻维修冻结的权限，需维修人员或管理员操作"
        
        instrument = self.get_instrument_by_id(instrument_id)
        if not instrument:
            return False, "仪器不存在"
        
        if instrument.status != InstrumentStatus.FROZEN:
            return False, "仪器不处于冻结状态"
        
        if instrument.is_calibration_expired():
            instrument.status = InstrumentStatus.CALIBRATION_EXPIRED
        elif instrument.is_calibration_due_soon(30):
            instrument.status = InstrumentStatus.CALIBRATION_DUE
        else:
            instrument.status = InstrumentStatus.AVAILABLE
        
        self.data_manager.update_instrument(instrument)
        
        history = OperationHistory.create(
            instrument_id=instrument_id,
            operation_type=OperationType.UNFREEZE,
            operator=user.display_name,
            details=f"解冻原因: {reason}" if reason else "解冻",
        )
        self.data_manager.add_operation_history(history)
        
        return True, "解冻成功"

    def start_maintenance(self, instrument_id: str, reason: str = "") -> Tuple[bool, str]:
        user = self.get_current_user()
        
        if not user.can_unfreeze_maintenance():
            return False, "您没有维修权限"
        
        instrument = self.get_instrument_by_id(instrument_id)
        if not instrument:
            return False, "仪器不存在"
        
        if instrument.status == InstrumentStatus.BORROWED:
            return False, "借出中的仪器不能开始维修"
        
        instrument.status = InstrumentStatus.MAINTENANCE
        self.data_manager.update_instrument(instrument)
        
        history = OperationHistory.create(
            instrument_id=instrument_id,
            operation_type=OperationType.MAINTENANCE_START,
            operator=user.display_name,
            details=f"开始维修: {reason}" if reason else "开始维修",
        )
        self.data_manager.add_operation_history(history)
        
        return True, "维修开始"

    def end_maintenance(self, instrument_id: str, notes: str = "") -> Tuple[bool, str]:
        user = self.get_current_user()
        
        if not user.can_unfreeze_maintenance():
            return False, "您没有维修权限"
        
        instrument = self.get_instrument_by_id(instrument_id)
        if not instrument:
            return False, "仪器不存在"
        
        if instrument.status != InstrumentStatus.MAINTENANCE:
            return False, "仪器不处于维修状态"
        
        if instrument.is_calibration_expired():
            instrument.status = InstrumentStatus.CALIBRATION_EXPIRED
        elif instrument.is_calibration_due_soon(30):
            instrument.status = InstrumentStatus.CALIBRATION_DUE
        else:
            instrument.status = InstrumentStatus.AVAILABLE
        
        self.data_manager.update_instrument(instrument)
        
        history = OperationHistory.create(
            instrument_id=instrument_id,
            operation_type=OperationType.MAINTENANCE_END,
            operator=user.display_name,
            details=f"维修完成: {notes}" if notes else "维修完成",
        )
        self.data_manager.add_operation_history(history)
        
        return True, "维修完成"

    def get_borrow_records(self, instrument_id: Optional[str] = None) -> List[BorrowRecord]:
        return self.data_manager.get_borrow_records(instrument_id)

    def get_active_borrow_record(self, instrument_id: str) -> Optional[BorrowRecord]:
        return self.data_manager.get_active_borrow_record(instrument_id)

    def get_operation_histories(self, instrument_id: Optional[str] = None) -> List[OperationHistory]:
        return self.data_manager.get_operation_histories(instrument_id)

    def get_calibration_records(self, instrument_id: Optional[str] = None) -> List[CalibrationRecord]:
        return self.data_manager.get_calibration_records(instrument_id)

    def get_settings(self) -> dict:
        return self.data_manager.get_settings()

    def update_settings(self, settings: dict) -> None:
        self.data_manager.update_settings(settings)

    def get_inventory_items(self) -> List[InventoryItem]:
        return self.data_manager.get_inventory_items()

    def get_inventory_item_by_id(self, item_id: str) -> Optional[InventoryItem]:
        return self.data_manager.get_inventory_item_by_id(item_id)

    def create_inventory_item(self, name: str, category: str, model: str,
                              total_quantity: int, unit: str = "台",
                              location: str = "", manager: str = "",
                              description: str = "") -> InventoryItem:
        item = InventoryItem.create(
            name=name,
            category=category,
            model=model,
            total_quantity=total_quantity,
            unit=unit,
            location=location,
            manager=manager,
            description=description,
        )
        self.data_manager.add_inventory_item(item)
        return item

    def update_inventory_item(self, item: InventoryItem, **kwargs) -> InventoryItem:
        for key, value in kwargs.items():
            if hasattr(item, key) and getattr(item, key) != value:
                setattr(item, key, value)
        self.data_manager.update_inventory_item(item)
        return item

    def create_reservation(self, inventory_item_id: str, requester: str,
                           department: str, quantity: int,
                           expected_use_date: date, purpose: str = "",
                           notes: str = "") -> Tuple[bool, str, Optional[Reservation]]:
        item = self.get_inventory_item_by_id(inventory_item_id)
        if not item:
            return False, "库存项不存在", None
        
        if quantity <= 0:
            return False, "预约数量必须大于0", None
        
        if quantity > item.total_quantity:
            return False, f"预约数量不能超过总库存（{item.total_quantity}{item.unit}）", None
        
        reservation = Reservation.create(
            inventory_item_id=inventory_item_id,
            requester=requester,
            department=department,
            quantity=quantity,
            expected_use_date=expected_use_date,
            purpose=purpose,
            notes=notes,
        )
        self.data_manager.add_reservation(reservation)
        return True, "预约创建成功", reservation

    def approve_reservation(self, reservation_id: str) -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None
        
        can_approve, reason = reservation.can_approve()
        if not can_approve:
            return False, reason, None
        
        item = self.get_inventory_item_by_id(reservation.inventory_item_id)
        if not item:
            return False, "关联的库存项不存在", None
        
        can_lock, lock_reason = item.can_lock(reservation.quantity)
        if not can_lock:
            return False, lock_reason, None
        
        item.lock(reservation.quantity)
        self.data_manager.update_inventory_item(item)
        
        reservation.mark_approved(user.display_name)
        self.data_manager.update_reservation(reservation)
        
        return True, "审批通过，库存已锁定", reservation

    def reject_reservation(self, reservation_id: str, reason: str = "") -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None
        
        can_reject, reject_reason = reservation.can_reject()
        if not can_reject:
            return False, reject_reason, None
        
        reservation.mark_rejected(user.display_name, reason)
        self.data_manager.update_reservation(reservation)
        
        return True, "预约已拒绝", reservation

    def cancel_reservation(self, reservation_id: str, reason: str = "") -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None
        
        can_cancel, cancel_reason = reservation.can_cancel()
        if not can_cancel:
            return False, cancel_reason, None
        
        was_approved = reservation.status == ReservationStatus.APPROVED
        
        reservation.mark_cancelled(user.display_name, reason)
        self.data_manager.update_reservation(reservation)
        
        if was_approved:
            item = self.get_inventory_item_by_id(reservation.inventory_item_id)
            if item:
                item.unlock(reservation.quantity)
                self.data_manager.update_inventory_item(item)
        
        return True, "预约已取消", reservation

    def reschedule_reservation(self, reservation_id: str, new_use_date: date,
                               new_quantity: Optional[int] = None
                               ) -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None
        
        can_reschedule, reason = reservation.can_reschedule()
        if not can_reschedule:
            return False, reason, None
        
        quantity = new_quantity if new_quantity is not None else reservation.quantity
        item = self.get_inventory_item_by_id(reservation.inventory_item_id)
        if not item:
            return False, "关联的库存项不存在", None
        
        if quantity <= 0:
            return False, "预约数量必须大于0", None
        
        if quantity > item.total_quantity:
            return False, f"预约数量不能超过总库存（{item.total_quantity}{item.unit}）", None
        
        was_approved = reservation.status == ReservationStatus.APPROVED
        original_quantity = reservation.quantity
        
        if was_approved:
            item.unlock(original_quantity)
            self.data_manager.update_inventory_item(item)
        
        new_reservation = Reservation.create(
            inventory_item_id=reservation.inventory_item_id,
            requester=reservation.requester,
            department=reservation.department,
            quantity=quantity,
            expected_use_date=new_use_date,
            purpose=reservation.purpose,
            notes=reservation.notes,
            original_reservation_id=reservation.id,
        )
        
        if was_approved:
            can_lock, lock_reason = item.can_lock(quantity)
            if not can_lock:
                item.lock(original_quantity)
                self.data_manager.update_inventory_item(item)
                return False, lock_reason, None
            
            new_reservation.mark_approved(user.display_name)
            item.lock(quantity)
            self.data_manager.update_inventory_item(item)
        
        self.data_manager.add_reservation(new_reservation)
        
        reservation.mark_rescheduled(new_reservation.id)
        self.data_manager.update_reservation(reservation)
        
        return True, "改期成功", new_reservation

    def fulfill_reservation(self, reservation_id: str) -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None
        
        can_fulfill, reason = reservation.can_fulfill()
        if not can_fulfill:
            return False, reason, None
        
        item = self.get_inventory_item_by_id(reservation.inventory_item_id)
        if not item:
            return False, "关联的库存项不存在", None
        
        if reservation.quantity > item.total_quantity:
            return False, "库存不足，无法完成领用", None
        
        item.total_quantity -= reservation.quantity
        item.unlock(reservation.quantity)
        self.data_manager.update_inventory_item(item)
        
        reservation.mark_fulfilled(user.display_name)
        self.data_manager.update_reservation(reservation)
        
        return True, "领用完成，库存已扣减", reservation

    def get_reservations(self, inventory_item_id: Optional[str] = None) -> List[Reservation]:
        return self.data_manager.get_reservations(inventory_item_id)

    def get_reservation_by_id(self, reservation_id: str) -> Optional[Reservation]:
        return self.data_manager.get_reservation_by_id(reservation_id)

    def recalculate_locked_quantities(self) -> None:
        self.data_manager.recalculate_locked_quantities()

    def parse_inventory_check_file(self, filepath: str
                                    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        if not os.path.exists(filepath):
            return False, f"文件不存在: {filepath}", []
        
        ext = os.path.splitext(filepath)[1].lower()
        
        try:
            if ext == '.csv':
                return self._parse_csv_file(filepath)
            elif ext == '.json':
                return self._parse_json_file(filepath)
            else:
                return False, f"不支持的文件格式: {ext}，请使用 CSV 或 JSON", []
        except Exception as e:
            return False, f"解析文件失败: {str(e)}", []

    def _parse_csv_file(self, filepath: str
                        ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        items = []
        required_fields = {'serial_number', 'actual_location', 'checker', 'check_time'}
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            if not reader.fieldnames:
                return False, "CSV 文件为空", []
            
            csv_fields = {f.lower().strip() for f in reader.fieldnames}
            missing = required_fields - csv_fields
            if missing:
                return False, f"缺少必填字段: {', '.join(missing)}", []
            
            field_map = {f.lower().strip(): f for f in reader.fieldnames}
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    item = {
                        'serial_number': row[field_map['serial_number']].strip(),
                        'actual_location': row[field_map['actual_location']].strip(),
                        'checker': row[field_map['checker']].strip(),
                        'check_time': row[field_map['check_time']].strip(),
                        'remarks': row.get(field_map.get('remarks', ''), '').strip()
                        if field_map.get('remarks') else ''
                    }
                    if not item['serial_number']:
                        continue
                    items.append(item)
                except Exception as e:
                    return False, f"第 {row_num} 行解析失败: {str(e)}", []
        
        return True, f"成功解析 {len(items)} 条记录", items

    def _parse_json_file(self, filepath: str
                         ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'items' in data:
            items = data['items']
        elif isinstance(data, list):
            items = data
        else:
            return False, "JSON 格式不正确，应为数组或包含 items 字段的对象", []
        
        required_fields = {'serial_number', 'actual_location', 'checker', 'check_time'}
        parsed_items = []
        
        for i, item in enumerate(items):
            missing = required_fields - set(item.keys())
            if missing:
                return False, f"第 {i+1} 条记录缺少字段: {', '.join(missing)}", []
            
            parsed_items.append({
                'serial_number': str(item.get('serial_number', '')).strip(),
                'actual_location': str(item.get('actual_location', '')).strip(),
                'checker': str(item.get('checker', '')).strip(),
                'check_time': str(item.get('check_time', '')).strip(),
                'remarks': str(item.get('remarks', '')).strip()
            })
        
        return True, f"成功解析 {len(parsed_items)} 条记录", parsed_items

    def create_inventory_check(self, name: str, checker: str,
                                check_date: Optional[date] = None,
                                notes: str = ""
                                ) -> Tuple[bool, str, Optional[InventoryCheck]]:
        user = self.get_current_user()
        check_date = check_date or date.today()
        
        check = InventoryCheck.create(
            name=name,
            checker=checker,
            check_date=check_date,
            notes=notes
        )
        self.data_manager.add_inventory_check(check)
        
        return True, "盘点任务创建成功", check

    def detect_conflicts(self, check_id: str, check_items: List[Dict[str, Any]]
                         ) -> Tuple[bool, str, List[InventoryCheckConflict]]:
        check = self.data_manager.get_inventory_check_by_id(check_id)
        if not check:
            return False, "盘点任务不存在", []
        
        check.set_processing()
        check.total_items = len(check_items)
        self.data_manager.update_inventory_check(check)
        
        instruments = self.get_instruments()
        instr_by_serial = {instr.serial_number: instr for instr in instruments}
        
        conflicts = []
        seen_serials = set()
        matched_count = 0
        
        for item in check_items:
            serial = item['serial_number']
            
            if serial in seen_serials:
                conflict = InventoryCheckConflict.create(
                    inventory_check_id=check_id,
                    conflict_type=ConflictType.DUPLICATE_SERIAL,
                    serial_number=serial,
                    expected_value="唯一序列号",
                    actual_value=serial,
                    instrument_id=instr_by_serial[serial].id if serial in instr_by_serial else None,
                    instrument_name=instr_by_serial[serial].name if serial in instr_by_serial else "",
                    notes=f"盘点单中重复出现"
                )
                conflicts.append(conflict)
                continue
            
            seen_serials.add(serial)
            
            if serial not in instr_by_serial:
                conflict = InventoryCheckConflict.create(
                    inventory_check_id=check_id,
                    conflict_type=ConflictType.UNKNOWN_INSTRUMENT,
                    serial_number=serial,
                    expected_value="系统中不存在",
                    actual_value=f"盘点位置: {item['actual_location']}",
                    instrument_name="未知仪器",
                    notes=f"盘点人: {item['checker']}, 时间: {item['check_time']}"
                )
                conflicts.append(conflict)
                continue
            
            instr = instr_by_serial[serial]
            
            if instr.status == InstrumentStatus.BORROWED:
                conflict = InventoryCheckConflict.create(
                    inventory_check_id=check_id,
                    conflict_type=ConflictType.BORROWED_BUT_PRESENT,
                    serial_number=serial,
                    expected_value="已借出，不在库",
                    actual_value=f"实际在库，位置: {item['actual_location']}",
                    instrument_id=instr.id,
                    instrument_name=instr.name,
                    notes=f"盘点人: {item['checker']}, 时间: {item['check_time']}"
                )
                conflicts.append(conflict)
                continue
            
            actual_loc = item['actual_location']
            if instr.location != actual_loc:
                conflict = InventoryCheckConflict.create(
                    inventory_check_id=check_id,
                    conflict_type=ConflictType.LOCATION_MISMATCH,
                    serial_number=serial,
                    expected_value=instr.location or "未设置",
                    actual_value=actual_loc,
                    instrument_id=instr.id,
                    instrument_name=instr.name,
                    notes=f"盘点人: {item['checker']}, 时间: {item['check_time']}"
                )
                conflicts.append(conflict)
                continue
            
            matched_count += 1
        
        check.matched_count = matched_count
        check.conflict_count = len(conflicts)
        self.data_manager.update_inventory_check(check)
        
        if conflicts:
            self.data_manager.add_conflicts_batch(conflicts)
        
        return True, f"检测完成：匹配 {matched_count} 条，冲突 {len(conflicts)} 条", conflicts

    def resolve_conflict(self, conflict_id: str, resolution: ConflictResolution,
                         notes: str = ""
                         ) -> Tuple[bool, str, Optional[InventoryCheckConflict]]:
        user = self.get_current_user()
        conflict = self.data_manager.get_conflict_by_id(conflict_id)
        if not conflict:
            return False, "冲突记录不存在", None
        
        conflict.resolve(resolution, user.display_name, notes)
        self.data_manager.update_inventory_check_conflict(conflict)
        
        if resolution in [ConflictResolution.CONFIRM, ConflictResolution.UPDATE]:
            if conflict.instrument_id:
                instr = self.get_instrument_by_id(conflict.instrument_id)
                if instr and conflict.conflict_type == ConflictType.LOCATION_MISMATCH:
                    old_location = instr.location
                    instr.location = conflict.actual_value
                    self.data_manager.update_instrument(instr)
                    
                    history = OperationHistory.create(
                        instrument_id=instr.id,
                        operation_type=OperationType.UPDATE,
                        operator=user.display_name,
                        details=f"盘点位置更新: {old_location} -> {conflict.actual_value}",
                        related_record_id=conflict.inventory_check_id
                    )
                    self.data_manager.add_operation_history(history)
        
        all_conflicts = self.data_manager.get_inventory_check_conflicts(
            conflict.inventory_check_id
        )
        pending = [c for c in all_conflicts if c.resolution == ConflictResolution.PENDING]
        
        if not pending:
            check = self.data_manager.get_inventory_check_by_id(conflict.inventory_check_id)
            if check and check.status == InventoryCheckStatus.PROCESSING:
                self.mark_check_completed(check.id)
        
        return True, f"冲突已标记为{resolution.value}", conflict

    def resolve_all_conflicts(self, check_id: str, resolution: ConflictResolution
                              ) -> Tuple[bool, str, int]:
        conflicts = self.data_manager.get_inventory_check_conflicts(check_id)
        pending = [c for c in conflicts if c.resolution == ConflictResolution.PENDING]
        
        count = 0
        for conflict in pending:
            success, _, _ = self.resolve_conflict(conflict.id, resolution)
            if success:
                count += 1
        
        check = self.data_manager.get_inventory_check_by_id(check_id)
        if check and check.status == InventoryCheckStatus.PROCESSING:
            self.mark_check_completed(check_id)
        
        return True, f"批量处理完成，共处理 {count} 条冲突", count

    def mark_check_completed(self, check_id: str, create_snapshot: bool = True
                             ) -> Tuple[bool, str, Optional[InventoryCheck]]:
        check = self.data_manager.get_inventory_check_by_id(check_id)
        if not check:
            return False, "盘点任务不存在", None
        
        check.mark_completed()
        
        if create_snapshot:
            conflicts = self.data_manager.get_inventory_check_conflicts(check_id)
            confirmed = [c for c in conflicts
                          if c.resolution in [ConflictResolution.CONFIRM, ConflictResolution.UPDATE]
                          and c.instrument_id]
            
            snapshot = {'updates': []}
            for c in confirmed:
                instr = self.get_instrument_by_id(c.instrument_id)
                if instr:
                    snapshot['updates'].append({
                        'instrument_id': instr.id,
                        'old_location': c.expected_value if c.conflict_type == ConflictType.LOCATION_MISMATCH else instr.location,
                        'new_location': c.actual_value if c.conflict_type == ConflictType.LOCATION_MISMATCH else instr.location,
                    })
            
            check.undo_snapshot = snapshot
            check.can_undo = len(snapshot['updates']) > 0
        
        self.data_manager.update_inventory_check(check)
        return True, "盘点任务已完成", check

    def undo_last_inventory_check(self) -> Tuple[bool, str, Optional[InventoryCheck]]:
        user = self.get_current_user()
        checks = self.data_manager.get_inventory_checks()
        
        undoable = [c for c in checks if c.can_undo]
        if not undoable:
            return False, "没有可撤销的盘点记录", None
        
        check = undoable[0]
        if not check.undo_snapshot or 'updates' not in check.undo_snapshot:
            check.can_undo = False
            self.data_manager.update_inventory_check(check)
            return False, "撤销数据已损坏", None
        
        count = 0
        for update in check.undo_snapshot['updates']:
            instr = self.get_instrument_by_id(update['instrument_id'])
            if instr:
                new_loc = instr.location
                instr.location = update['old_location']
                self.data_manager.update_instrument(instr)
                
                history = OperationHistory.create(
                    instrument_id=instr.id,
                    operation_type=OperationType.UPDATE,
                    operator=user.display_name,
                    details=f"撤销盘点位置更新: {new_loc} -> {update['old_location']}",
                    related_record_id=check.id
                )
                self.data_manager.add_operation_history(history)
                count += 1
        
        check.can_undo = False
        check.notes = (check.notes + "\n" if check.notes else "") + f"已撤销 {count} 条位置更新"
        self.data_manager.update_inventory_check(check)
        
        return True, f"已撤销 {count} 条位置更新", check

    def get_inventory_checks(self) -> List[InventoryCheck]:
        return self.data_manager.get_inventory_checks()

    def get_inventory_check_by_id(self, check_id: str) -> Optional[InventoryCheck]:
        return self.data_manager.get_inventory_check_by_id(check_id)

    def get_latest_inventory_check(self) -> Optional[InventoryCheck]:
        return self.data_manager.get_latest_inventory_check()

    def get_inventory_check_conflicts(self, check_id: str
                                       ) -> List[InventoryCheckConflict]:
        return self.data_manager.get_inventory_check_conflicts(check_id)

    def can_undo_last_check(self) -> Tuple[bool, Optional[InventoryCheck]]:
        checks = self.data_manager.get_inventory_checks()
        undoable = [c for c in checks if c.can_undo]
        return (True, undoable[0]) if undoable else (False, None)
