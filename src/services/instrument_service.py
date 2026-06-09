from typing import List, Optional, Tuple
from datetime import date, datetime, timedelta

from ..models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    BorrowRecord, BorrowStatus,
    OperationHistory, OperationType,
    CalibrationRecord,
    User, UserRole,
)
from ..storage import DataManager


class InstrumentService:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self.refresh_statuses()

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
