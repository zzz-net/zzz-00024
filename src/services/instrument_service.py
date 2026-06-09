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
    CalibrationSchedule, CalibrationScheduleStatus,
    CalibrationScheduleItem, CalibrationScheduleItemStatus,
    CalibrationScheduleConflict, CalibrationConflictType,
    CalibrationConflictResolution,
)
from ..storage import DataManager, DataExporter


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

    def get_reservations_filtered(self,
                                   status_filter: Optional[str] = None,
                                   department_filter: Optional[str] = None,
                                   date_from: Optional[date] = None,
                                   date_to: Optional[date] = None,
                                   requester_filter: Optional[str] = None) -> List[Reservation]:
        user = self.get_current_user()
        reservations = self.data_manager.get_reservations()

        if not user.can_export_all_reservations():
            requester_filter = user.display_name

        if status_filter:
            reservations = [r for r in reservations if r.status.value == status_filter]

        if department_filter:
            reservations = [r for r in reservations if r.department == department_filter]

        if date_from:
            reservations = [r for r in reservations if r.expected_use_date >= date_from]

        if date_to:
            reservations = [r for r in reservations if r.expected_use_date <= date_to]

        if requester_filter:
            reservations = [r for r in reservations if r.requester == requester_filter]

        return sorted(reservations, key=lambda r: r.created_at, reverse=True)

    def get_reservation_departments(self) -> List[str]:
        reservations = self.data_manager.get_reservations()
        departments = sorted({r.department for r in reservations})
        return departments

    def detect_reservation_conflicts(self, reservation_id: str) -> Tuple[bool, str, List[Reservation], Optional[InventoryItem]]:
        user = self.get_current_user()
        if not user.can_approve_reservations():
            return False, "您没有审批预约的权限", [], None

        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", [], None

        can_approve, reason = reservation.can_approve()
        if not can_approve:
            return False, reason, [], None

        item = self.get_inventory_item_by_id(reservation.inventory_item_id)
        if not item:
            return False, "关联的库存项不存在", [], None

        all_reservations = self.data_manager.get_reservations(reservation.inventory_item_id)
        conflicts = [
            r for r in all_reservations
            if r.id != reservation.id
            and r.expected_use_date == reservation.expected_use_date
            and r.status in [ReservationStatus.APPROVED, ReservationStatus.PENDING]
        ]

        return len(conflicts) > 0, "", conflicts, item

    def approve_reservation_with_conflict(self,
                                          reservation_id: str,
                                          conflict_reason: str = "") -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        if not user.can_approve_reservations():
            return False, "您没有审批预约的权限", None

        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None

        can_approve, reason = reservation.can_approve()
        if not can_approve:
            return False, reason, None

        item = self.get_inventory_item_by_id(reservation.inventory_item_id)
        if not item:
            return False, "关联的库存项不存在", None

        if conflict_reason:
            reservation.notes = (reservation.notes + "\n" if reservation.notes else "") + f"冲突审批原因: {conflict_reason}"

        success, msg, reservation = self.approve_reservation(reservation_id)
        if success:
            history = OperationHistory.create(
                instrument_id="",
                operation_type=OperationType.RESERVATION_APPROVE,
                operator=user.display_name,
                details=f"审批预约[{reservation.id}]: {item.name} {reservation.quantity}{item.unit}, 日期: {reservation.expected_use_date.isoformat()}" + (f", 冲突原因: {conflict_reason}" if conflict_reason else ""),
                related_record_id=reservation.id,
            )
            self.data_manager.add_operation_history(history)

        return success, msg, reservation

    def reject_reservation(self, reservation_id: str, reason: str = "") -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None

        if not user.can_approve_reservations():
            return False, "您没有拒绝预约的权限", None

        success, msg, reservation = self._reject_reservation_internal(reservation_id, reason)
        if success:
            item = self.get_inventory_item_by_id(reservation.inventory_item_id)
            item_name = item.name if item else "未知"
            history = OperationHistory.create(
                instrument_id="",
                operation_type=OperationType.RESERVATION_REJECT,
                operator=user.display_name,
                details=f"拒绝预约[{reservation.id}]: {item_name} {reservation.quantity}, 日期: {reservation.expected_use_date.isoformat()}, 原因: {reason}",
                related_record_id=reservation.id,
            )
            self.data_manager.add_operation_history(history)

        return success, msg, reservation

    def _reject_reservation_internal(self, reservation_id: str, reason: str = "") -> Tuple[bool, str, Optional[Reservation]]:
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None

        can_reject, reject_reason = reservation.can_reject()
        if not can_reject:
            return False, reject_reason, None

        user = self.get_current_user()
        reservation.mark_rejected(user.display_name, reason)
        self.data_manager.update_reservation(reservation)

        return True, "预约已拒绝", reservation

    def cancel_reservation(self, reservation_id: str, reason: str = "") -> Tuple[bool, str, Optional[Reservation]]:
        user = self.get_current_user()
        reservation = self.data_manager.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在", None

        if not user.can_approve_reservations() and reservation.requester != user.display_name:
            return False, "您只能取消自己的预约", None

        success, msg, reservation = self._cancel_reservation_internal(reservation_id, reason)
        if success:
            item = self.get_inventory_item_by_id(reservation.inventory_item_id)
            item_name = item.name if item else "未知"
            history = OperationHistory.create(
                instrument_id="",
                operation_type=OperationType.RESERVATION_CANCEL,
                operator=user.display_name,
                details=f"取消预约[{reservation.id}]: {item_name} {reservation.quantity}, 日期: {reservation.expected_use_date.isoformat()}, 原因: {reason}",
                related_record_id=reservation.id,
            )
            self.data_manager.add_operation_history(history)

        return success, msg, reservation

    def _cancel_reservation_internal(self, reservation_id: str, reason: str = "") -> Tuple[bool, str, Optional[Reservation]]:
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

    def export_reservations(self,
                            reservations: List[Reservation],
                            format_type: str,
                            export_dir: str,
                            filters: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Optional[str]]:
        user = self.get_current_user()

        if not reservations:
            return False, "没有符合条件的预约记录，未生成导出文件", None

        if not user.can_export_all_reservations():
            reservations = [r for r in reservations if r.requester == user.display_name]
            if not reservations:
                return False, "您没有可导出的预约记录，未生成导出文件", None

        try:
            filename = DataExporter.generate_export_filename("reservations", format_type, export_dir)
            inventory_items = self.get_inventory_items()

            if format_type == "csv":
                filepath = DataExporter.export_reservations_to_csv(reservations, filename, inventory_items)
            elif format_type == "json":
                filepath = DataExporter.export_reservations_to_json(reservations, filename)
            else:
                return False, f"不支持的导出格式: {format_type}", None

            filter_desc = ""
            if filters:
                filter_parts = []
                if filters.get('status_filter'):
                    filter_parts.append(f"状态:{filters['status_filter']}")
                if filters.get('department_filter'):
                    filter_parts.append(f"部门:{filters['department_filter']}")
                if filters.get('date_from'):
                    filter_parts.append(f"起始日期:{filters['date_from'].isoformat()}")
                if filters.get('date_to'):
                    filter_parts.append(f"结束日期:{filters['date_to'].isoformat()}")
                if filter_parts:
                    filter_desc = f"，筛选条件: [{', '.join(filter_parts)}]"

            scope = "全部" if user.can_export_all_reservations() else f"本人({user.display_name})"
            details = f"导出预约 {len(reservations)} 条，格式: {format_type.upper()}，范围: {scope}{filter_desc}"
            history = OperationHistory.create(
                instrument_id="",
                operation_type=OperationType.RESERVATION_EXPORT,
                operator=user.display_name,
                details=details,
                related_record_id="",
            )
            self.data_manager.add_operation_history(history)

            return True, f"导出成功，共 {len(reservations)} 条记录", filepath
        except Exception as e:
            return False, f"导出失败: {str(e)}", None

    def export_reservations_with_filters(self,
                                         status_filter: Optional[str] = None,
                                         department_filter: Optional[str] = None,
                                         date_from: Optional[date] = None,
                                         date_to: Optional[date] = None,
                                         format_type: str = "csv",
                                         export_dir: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        if export_dir is None:
            settings = self.get_settings()
            export_dir = settings.get('export_dir', '')

        filters = {
            'status_filter': status_filter,
            'department_filter': department_filter,
            'date_from': date_from,
            'date_to': date_to,
        }

        reservations = self.get_reservations_filtered(
            status_filter=status_filter,
            department_filter=department_filter,
            date_from=date_from,
            date_to=date_to,
        )

        return self.export_reservations(reservations, format_type, export_dir, filters)

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

    def parse_calibration_schedule_file(self, filepath: str
                                        ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        if not os.path.exists(filepath):
            return False, f"文件不存在: {filepath}", []

        ext = os.path.splitext(filepath)[1].lower()

        try:
            if ext == '.csv':
                return self._parse_calibration_csv_file(filepath)
            elif ext == '.json':
                return self._parse_calibration_json_file(filepath)
            else:
                return False, f"不支持的文件格式: {ext}，请使用 CSV 或 JSON", []
        except Exception as e:
            return False, f"解析文件失败: {str(e)}", []

    def _parse_calibration_csv_file(self, filepath: str
                                     ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        items = []
        required_fields = {'serial_number', 'planned_date'}

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
                        'planned_date': row[field_map['planned_date']].strip(),
                        'calibration_agency': row.get(field_map.get('calibration_agency', ''), '').strip()
                        if field_map.get('calibration_agency') else '',
                        'certificate_number': row.get(field_map.get('certificate_number', ''), '').strip()
                        if field_map.get('certificate_number') else '',
                        'notes': row.get(field_map.get('notes', ''), '').strip()
                        if field_map.get('notes') else '',
                    }
                    if not item['serial_number']:
                        continue
                    items.append(item)
                except Exception as e:
                    return False, f"第 {row_num} 行解析失败: {str(e)}", []

        return True, f"成功解析 {len(items)} 条记录", items

    def _parse_calibration_json_file(self, filepath: str
                                      ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict) and 'items' in data:
            items = data['items']
        elif isinstance(data, list):
            items = data
        else:
            return False, "JSON 格式不正确，应为数组或包含 items 字段的对象", []

        required_fields = {'serial_number', 'planned_date'}
        parsed_items = []

        for i, item in enumerate(items):
            missing = required_fields - set(item.keys())
            if missing:
                return False, f"第 {i+1} 条记录缺少字段: {', '.join(missing)}", []

            parsed_items.append({
                'serial_number': str(item.get('serial_number', '')).strip(),
                'planned_date': str(item.get('planned_date', '')).strip(),
                'calibration_agency': str(item.get('calibration_agency', '')).strip(),
                'certificate_number': str(item.get('certificate_number', '')).strip(),
                'notes': str(item.get('notes', '')).strip(),
            })

        return True, f"成功解析 {len(parsed_items)} 条记录", parsed_items

    def create_calibration_schedule(self, name: str, plan_date: Optional[date] = None,
                                    notes: str = ""
                                    ) -> Tuple[bool, str, Optional[CalibrationSchedule]]:
        user = self.get_current_user()

        if not user.can_calibrate():
            return False, "您没有创建校准排程的权限", None

        if not name.strip():
            return False, "请输入排程名称", None

        plan_date = plan_date or date.today()

        schedule = CalibrationSchedule.create(
            name=name.strip(),
            creator=user.display_name,
            plan_date=plan_date,
            notes=notes.strip()
        )

        self.data_manager.add_calibration_schedule(schedule)
        return True, "校准排程创建成功", schedule

    def detect_calibration_conflicts(self, schedule_id: str, import_items: List[Dict[str, Any]]
                                      ) -> Tuple[bool, str, List[CalibrationScheduleConflict]]:
        user = self.get_current_user()
        if not user.can_calibrate():
            return False, "您没有检测校准冲突的权限", []

        schedule = self.data_manager.get_calibration_schedule_by_id(schedule_id)
        if not schedule:
            return False, "校准排程不存在", []

        schedule.mark_processing()
        schedule.total_items = len(import_items)
        self.data_manager.update_calibration_schedule(schedule)

        instruments = self.get_instruments()
        instr_by_serial = {instr.serial_number: instr for instr in instruments}

        existing_calibrations = self.get_calibration_records()
        existing_certificates = {c.certificate_number for c in existing_calibrations if c.certificate_number}

        schedule_items = self.data_manager.get_calibration_schedule_items()
        schedule_certificates = {i.certificate_number for i in schedule_items if i.certificate_number}

        conflicts = []
        seen_serials = set()
        seen_certificates = set()
        valid_items = []

        for item in import_items:
            serial = item['serial_number']

            if serial in seen_serials:
                conflict = CalibrationScheduleConflict.create(
                    schedule_id=schedule_id,
                    conflict_type=CalibrationConflictType.DUPLICATE_SERIAL,
                    serial_number=serial,
                    expected_value="唯一序列号",
                    actual_value=serial,
                    notes="导入文件中序列号重复",
                    row_data=item
                )
                conflicts.append(conflict)
                continue

            seen_serials.add(serial)

            if not item.get('planned_date'):
                conflict = CalibrationScheduleConflict.create(
                    schedule_id=schedule_id,
                    conflict_type=CalibrationConflictType.MISSING_DATE,
                    serial_number=serial,
                    expected_value="校准计划日期",
                    actual_value="空",
                    instrument_id=instr_by_serial[serial].id if serial in instr_by_serial else None,
                    instrument_name=instr_by_serial[serial].name if serial in instr_by_serial else "",
                    notes="缺少计划校准日期",
                    row_data=item
                )
                conflicts.append(conflict)
                continue

            try:
                pd = item['planned_date']
                if isinstance(pd, date):
                    planned_date = pd
                else:
                    planned_date = date.fromisoformat(str(pd))
            except ValueError:
                conflict = CalibrationScheduleConflict.create(
                    schedule_id=schedule_id,
                    conflict_type=CalibrationConflictType.INVALID_DATE,
                    serial_number=serial,
                    expected_value="YYYY-MM-DD 格式",
                    actual_value=item['planned_date'],
                    instrument_id=instr_by_serial[serial].id if serial in instr_by_serial else None,
                    instrument_name=instr_by_serial[serial].name if serial in instr_by_serial else "",
                    notes="日期格式不正确",
                    row_data=item
                )
                conflicts.append(conflict)
                continue

            if serial not in instr_by_serial:
                conflict = CalibrationScheduleConflict.create(
                    schedule_id=schedule_id,
                    conflict_type=CalibrationConflictType.INSTRUMENT_NOT_FOUND,
                    serial_number=serial,
                    expected_value="系统中存在",
                    actual_value="不存在",
                    instrument_name="未知仪器",
                    notes=f"仪器序列号 {serial} 在系统中不存在",
                    row_data=item
                )
                conflicts.append(conflict)
                continue

            instr = instr_by_serial[serial]

            if instr.status == InstrumentStatus.BORROWED:
                conflict = CalibrationScheduleConflict.create(
                    schedule_id=schedule_id,
                    conflict_type=CalibrationConflictType.BORROWED_CONFLICT,
                    serial_number=serial,
                    expected_value="在库可用",
                    actual_value="已借出",
                    instrument_id=instr.id,
                    instrument_name=instr.name,
                    notes="仪器当前处于借出状态，无法安排校准",
                    row_data=item
                )
                conflicts.append(conflict)
                continue

            if instr.status == InstrumentStatus.FROZEN:
                conflict = CalibrationScheduleConflict.create(
                    schedule_id=schedule_id,
                    conflict_type=CalibrationConflictType.FROZEN_CONFLICT,
                    serial_number=serial,
                    expected_value="在库可用",
                    actual_value="已冻结",
                    instrument_id=instr.id,
                    instrument_name=instr.name,
                    notes="仪器当前处于冻结状态，无法安排校准",
                    row_data=item
                )
                conflicts.append(conflict)
                continue

            cert_number = item.get('certificate_number', '').strip()
            if cert_number:
                if cert_number in existing_certificates or cert_number in schedule_certificates or cert_number in seen_certificates:
                    conflict = CalibrationScheduleConflict.create(
                        schedule_id=schedule_id,
                        conflict_type=CalibrationConflictType.DUPLICATE_CERTIFICATE,
                        serial_number=serial,
                        expected_value="唯一证书编号",
                        actual_value=cert_number,
                        instrument_id=instr.id,
                        instrument_name=instr.name,
                        notes=f"证书编号 {cert_number} 已存在",
                        row_data=item
                    )
                    conflicts.append(conflict)
                    continue
                seen_certificates.add(cert_number)

            valid_items.append({
                'instrument': instr,
                'planned_date': planned_date,
                'calibration_agency': item.get('calibration_agency', ''),
                'certificate_number': cert_number,
                'notes': item.get('notes', ''),
                'row_data': item,
            })

        schedule_items_objs = []
        for item in valid_items:
            instr = item['instrument']
            schedule_item = CalibrationScheduleItem.create(
                schedule_id=schedule_id,
                instrument_id=instr.id,
                serial_number=instr.serial_number,
                instrument_name=instr.name,
                planned_date=item['planned_date'],
                calibration_agency=item['calibration_agency'],
                certificate_number=item['certificate_number'],
                notes=item['notes'],
            )
            if schedule_item.is_overdue():
                schedule_item.mark_overdue()
            schedule_items_objs.append(schedule_item)

        if schedule_items_objs:
            self.data_manager.add_calibration_schedule_items_batch(schedule_items_objs)

        schedule.conflict_count = len(conflicts)
        self.data_manager.update_calibration_schedule(schedule)

        if conflicts:
            self.data_manager.add_calibration_schedule_conflicts_batch(conflicts)

        history = OperationHistory.create(
            instrument_id="",
            operation_type=OperationType.CALIBRATION_SCHEDULE_IMPORT,
            operator=user.display_name,
            details=f"导入校准排程: {schedule.name}, 共 {len(import_items)} 条, 冲突 {len(conflicts)} 条",
            related_record_id=schedule.id,
        )
        self.data_manager.add_operation_history(history)

        return True, f"检测完成：成功导入 {len(valid_items)} 条，冲突 {len(conflicts)} 条", conflicts

    def get_calibration_schedule_conflict_by_id(self, conflict_id: str) -> Optional[CalibrationScheduleConflict]:
        return self.data_manager.get_calibration_schedule_conflict_by_id(conflict_id)

    def resolve_calibration_conflict(self, conflict_id: str,
                                     resolution: CalibrationConflictResolution,
                                     notes: str = ""
                                     ) -> Tuple[bool, str, Optional[CalibrationScheduleConflict]]:
        user = self.get_current_user()
        if not user.can_calibrate():
            return False, "您没有处理校准冲突的权限", None

        conflict = self.data_manager.get_calibration_schedule_conflict_by_id(conflict_id)
        if not conflict:
            return False, "冲突记录不存在", None

        conflict.resolve(resolution, user.display_name, notes)
        self.data_manager.update_calibration_schedule_conflict(conflict)

        if resolution == CalibrationConflictResolution.CONFIRM and conflict.row_data:
            instruments = self.get_instruments()
            instr_by_serial = {instr.serial_number: instr for instr in instruments}

            row_data = conflict.row_data
            serial = row_data.get('serial_number', '')

            if conflict.conflict_type in [CalibrationConflictType.INSTRUMENT_NOT_FOUND,
                                           CalibrationConflictType.BORROWED_CONFLICT,
                                           CalibrationConflictType.FROZEN_CONFLICT]:
                pass
            else:
                try:
                    planned_date = date.fromisoformat(row_data['planned_date'])
                except (ValueError, KeyError):
                    planned_date = date.today()

                instr = instr_by_serial.get(serial)
                if instr:
                    schedule_item = CalibrationScheduleItem.create(
                        schedule_id=conflict.schedule_id,
                        instrument_id=instr.id,
                        serial_number=instr.serial_number,
                        instrument_name=instr.name,
                        planned_date=planned_date,
                        calibration_agency=row_data.get('calibration_agency', ''),
                        certificate_number=row_data.get('certificate_number', ''),
                        notes=row_data.get('notes', ''),
                    )
                    if schedule_item.is_overdue():
                        schedule_item.mark_overdue()
                    self.data_manager.add_calibration_schedule_item(schedule_item)

        all_conflicts = self.data_manager.get_calibration_schedule_conflicts(
            conflict.schedule_id
        )
        pending = [c for c in all_conflicts if c.resolution == CalibrationConflictResolution.PENDING]

        if not pending:
            schedule = self.data_manager.get_calibration_schedule_by_id(conflict.schedule_id)
            if schedule and schedule.status == CalibrationScheduleStatus.PROCESSING:
                self.mark_calibration_schedule_import_completed(schedule.id)

        return True, f"冲突已标记为{resolution.value}", conflict

    def resolve_all_calibration_conflicts(self, schedule_id: str,
                                          resolution: CalibrationConflictResolution
                                          ) -> Tuple[bool, str, int]:
        user = self.get_current_user()
        if not user.can_calibrate():
            return False, "您没有处理校准冲突的权限", 0

        conflicts = self.data_manager.get_calibration_schedule_conflicts(schedule_id)
        pending = [c for c in conflicts if c.resolution == CalibrationConflictResolution.PENDING]

        count = 0
        for conflict in pending:
            success, _, _ = self.resolve_calibration_conflict(conflict.id, resolution)
            if success:
                count += 1

        schedule = self.data_manager.get_calibration_schedule_by_id(schedule_id)
        if schedule and schedule.status == CalibrationScheduleStatus.PROCESSING:
            all_conflicts = self.data_manager.get_calibration_schedule_conflicts(schedule_id)
            still_pending = [c for c in all_conflicts if c.resolution == CalibrationConflictResolution.PENDING]
            if not still_pending:
                self.mark_calibration_schedule_import_completed(schedule_id)

        return True, f"批量处理完成，共处理 {count} 条冲突", count

    def mark_calibration_schedule_import_completed(self, schedule_id: str
                                                    ) -> Tuple[bool, str, Optional[CalibrationSchedule]]:
        schedule = self.data_manager.get_calibration_schedule_by_id(schedule_id)
        if not schedule:
            return False, "校准排程不存在", None

        schedule.mark_completed()
        self.data_manager.update_calibration_schedule(schedule)

        return True, "校准排程导入完成", schedule

    def complete_calibration_schedule_item(self, item_id: str,
                                            calibration_date: date,
                                            next_calibration_date: date,
                                            certificate_number: str,
                                            calibration_agency: str,
                                            result: str = "合格",
                                            notes: str = ""
                                            ) -> Tuple[bool, str, Optional[CalibrationScheduleItem]]:
        user = self.get_current_user()
        if not user.can_calibrate():
            return False, "您没有完成校准的权限", None

        item = self.data_manager.get_calibration_schedule_item_by_id(item_id)
        if not item:
            return False, "校准排程项不存在", None

        if item.status == CalibrationScheduleItemStatus.COMPLETED:
            return False, "该排程项已完成校准", None

        if next_calibration_date <= calibration_date:
            return False, "下次校准日期必须晚于本次校准日期", None

        item.mark_completed(
            calibration_date=calibration_date,
            next_calibration_date=next_calibration_date,
            certificate_number=certificate_number,
            result=result,
            processed_by=user.display_name,
            notes=notes
        )

        self.data_manager.update_calibration_schedule_item(item)

        existing_certs = self.get_calibration_records()
        for cert in existing_certs:
            if cert.certificate_number == certificate_number and cert.instrument_id != item.instrument_id:
                pass

        calibration_record = CalibrationRecord.create(
            instrument_id=item.instrument_id,
            calibration_date=calibration_date,
            next_calibration_date=next_calibration_date,
            certificate_number=certificate_number,
            calibration_agency=calibration_agency,
            result=result,
            notes=notes,
        )
        self.data_manager.add_calibration_record(calibration_record)

        instrument = self.get_instrument_by_id(item.instrument_id)
        if instrument:
            old_status = instrument.status
            old_cal_date = instrument.calibration_due_date
            instrument.calibration_due_date = next_calibration_date

            if instrument.is_calibration_expired():
                instrument.status = InstrumentStatus.CALIBRATION_EXPIRED
            elif instrument.is_calibration_due_soon(30):
                instrument.status = InstrumentStatus.CALIBRATION_DUE
            else:
                instrument.status = InstrumentStatus.AVAILABLE

            self.data_manager.update_instrument(instrument)

            if not item.undo_snapshot:
                item.undo_snapshot = {
                    'old_status': old_status.value,
                    'old_calibration_due_date': old_cal_date.isoformat() if old_cal_date else None,
                    'calibration_record_id': calibration_record.id,
                }
                self.data_manager.update_calibration_schedule_item(item)

        schedule = self.data_manager.get_calibration_schedule_by_id(item.schedule_id)
        if schedule:
            schedule.can_undo = True
            if not schedule.undo_snapshot:
                schedule.undo_snapshot = {'items': []}
            if 'items' not in schedule.undo_snapshot:
                schedule.undo_snapshot['items'] = []
            schedule.undo_snapshot['items'].append({
                'item_id': item.id,
                'instrument_id': item.instrument_id,
                'old_status': old_status.value,
                'old_calibration_due_date': old_cal_date.isoformat() if old_cal_date else None,
                'calibration_record_id': calibration_record.id,
            })
            self.data_manager.update_calibration_schedule(schedule)

        history = OperationHistory.create(
            instrument_id=item.instrument_id,
            operation_type=OperationType.CALIBRATION,
            operator=user.display_name,
            details=f"排程校准完成, 证书编号: {certificate_number}, 机构: {calibration_agency}, 结果: {result}",
            related_record_id=item.schedule_id,
        )
        self.data_manager.add_operation_history(history)

        schedule_items = self.data_manager.get_calibration_schedule_items(item.schedule_id)
        schedule.refresh_status(schedule_items)
        self.data_manager.update_calibration_schedule(schedule)

        return True, "校准完成，仪器状态已更新", item

    def undo_last_calibration_completion(self) -> Tuple[bool, str, Optional[CalibrationScheduleItem]]:
        user = self.get_current_user()
        if not user.can_calibrate():
            return False, "您没有撤销校准的权限", None

        can_undo, item = self.data_manager.can_undo_last_calibration_schedule()
        if not can_undo or not item:
            return False, "没有可撤销的校准处理", None

        if not item.undo_snapshot:
            return False, "撤销数据已损坏", None

        undo_data = item.undo_snapshot
        instrument = self.get_instrument_by_id(item.instrument_id)
        if not instrument:
            return False, "关联仪器不存在", None

        old_status = InstrumentStatus(undo_data['old_status'])
        old_cal_date = date.fromisoformat(undo_data['old_calibration_due_date']) if undo_data.get('old_calibration_due_date') else None

        instrument.calibration_due_date = old_cal_date
        instrument.status = old_status
        self.data_manager.update_instrument(instrument)

        item.status = CalibrationScheduleItemStatus.SCHEDULED
        item.actual_calibration_date = None
        item.next_calibration_date = None
        item.certificate_number = ""
        item.result = ""
        item.processed_by = None
        item.processed_at = None
        item.undo_snapshot = None
        self.data_manager.update_calibration_schedule_item(item)

        schedule = self.data_manager.get_calibration_schedule_by_id(item.schedule_id)
        if schedule and schedule.undo_snapshot and 'items' in schedule.undo_snapshot:
            schedule.undo_snapshot['items'] = [
                i for i in schedule.undo_snapshot['items']
                if i.get('item_id') != item.id
            ]
            if not schedule.undo_snapshot['items']:
                schedule.can_undo = False
                schedule.undo_snapshot = {'items': []}
            self.data_manager.update_calibration_schedule(schedule)

        history = OperationHistory.create(
            instrument_id=instrument.id,
            operation_type=OperationType.CALIBRATION_SCHEDULE_UNDO,
            operator=user.display_name,
            details=f"撤销排程校准: 恢复状态为 {old_status.value}",
            related_record_id=item.schedule_id,
        )
        self.data_manager.add_operation_history(history)

        return True, "已撤销最近一次校准处理", item

    def get_calibration_schedules(self) -> List[CalibrationSchedule]:
        self.data_manager.refresh_calibration_schedule_statuses()
        return self.data_manager.get_calibration_schedules()

    def get_calibration_schedule_by_id(self, schedule_id: str) -> Optional[CalibrationSchedule]:
        return self.data_manager.get_calibration_schedule_by_id(schedule_id)

    def get_calibration_schedule_items(self, schedule_id: Optional[str] = None,
                                        instrument_id: Optional[str] = None) -> List[CalibrationScheduleItem]:
        return self.data_manager.get_calibration_schedule_items(schedule_id, instrument_id)

    def get_calibration_schedule_conflicts(self, schedule_id: Optional[str] = None
                                            ) -> List[CalibrationScheduleConflict]:
        return self.data_manager.get_calibration_schedule_conflicts(schedule_id)

    def can_undo_last_calibration_schedule(self) -> Tuple[bool, Optional[CalibrationScheduleItem]]:
        return self.data_manager.can_undo_last_calibration_schedule()

    def get_overdue_calibration_items(self) -> List[CalibrationScheduleItem]:
        self.data_manager.refresh_calibration_schedule_statuses()
        all_items = self.data_manager.get_calibration_schedule_items()
        return [i for i in all_items if i.status == CalibrationScheduleItemStatus.OVERDUE]

    def get_upcoming_calibration_items(self, days: int = 30) -> List[CalibrationScheduleItem]:
        self.data_manager.refresh_calibration_schedule_statuses()
        all_items = self.data_manager.get_calibration_schedule_items()
        today = date.today()
        end_date = today + timedelta(days=days)
        return [
            i for i in all_items
            if i.status in [CalibrationScheduleItemStatus.SCHEDULED, CalibrationScheduleItemStatus.OVERDUE]
            and today <= i.planned_date <= end_date
        ]

    def refresh_calibration_statuses(self) -> None:
        self.data_manager.refresh_calibration_schedule_statuses()

    def refresh_calibration_schedule_statuses(self) -> None:
        self.data_manager.refresh_calibration_schedule_statuses()

    def get_calibration_schedule_item_by_id(self, item_id: str) -> Optional[CalibrationScheduleItem]:
        return self.data_manager.get_calibration_schedule_item_by_id(item_id)
