from datetime import date, timedelta
from typing import List

from ..models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    BorrowRecord, BorrowStatus,
    OperationHistory, OperationType,
    CalibrationRecord,
    User, UserRole,
)
from ..storage import DataManager


def create_sample_data(data_manager: DataManager) -> None:
    data_manager.clear_all_data()
    
    today = date.today()
    
    instr1 = Instrument.create(
        name="高效液相色谱仪",
        category=InstrumentCategory.ANALYSIS,
        model="Agilent 1260",
        serial_number="HPLC-001",
        location="分析实验室A区",
        manager="张工",
        calibration_due_date=today + timedelta(days=45),
        description="用于有机化合物定量分析",
    )
    
    instr2 = Instrument.create(
        name="电子分析天平",
        category=InstrumentCategory.MEASUREMENT,
        model="Sartorius BSA224S",
        serial_number="BAL-002",
        location="称量室",
        manager="李工",
        calibration_due_date=today + timedelta(days=15),
        description="万分之一精度天平",
    )
    instr2.status = InstrumentStatus.CALIBRATION_DUE
    
    instr3 = Instrument.create(
        name="紫外可见分光光度计",
        category=InstrumentCategory.OPTICAL,
        model="Shimadzu UV-2600",
        serial_number="UV-003",
        location="光谱实验室",
        manager="王工",
        calibration_due_date=today - timedelta(days=10),
        description="波长范围190-900nm",
    )
    instr3.status = InstrumentStatus.CALIBRATION_EXPIRED
    
    instr4 = Instrument.create(
        name="数字示波器",
        category=InstrumentCategory.ELECTRONIC,
        model="Tektronix MSO54",
        serial_number="OSC-004",
        location="电子实验室",
        manager="赵工",
        calibration_due_date=today + timedelta(days=180),
        description="500MHz带宽，4通道",
    )
    
    instr5 = Instrument.create(
        name="万能材料试验机",
        category=InstrumentCategory.MECHANICAL,
        model="Instron 5967",
        serial_number="UTM-005",
        location="力学实验室",
        manager="刘工",
        calibration_due_date=today + timedelta(days=90),
        description="最大载荷30kN",
    )
    instr5.status = InstrumentStatus.FROZEN
    
    instr6 = Instrument.create(
        name="pH计",
        category=InstrumentCategory.ANALYSIS,
        model="Mettler FiveEasy",
        serial_number="PH-006",
        location="分析实验室B区",
        manager="陈工",
        calibration_due_date=today + timedelta(days=60),
        description="实验室常规pH测量",
    )
    
    instruments = [instr1, instr2, instr3, instr4, instr5, instr6]
    for instr in instruments:
        data_manager.add_instrument(instr)
    
    borrow_date1 = today - timedelta(days=7)
    expected_return1 = today + timedelta(days=7)
    borrow_record1 = BorrowRecord.create(
        instrument_id=instr4.id,
        borrower="孙研究员",
        borrower_department="材料研究所",
        borrow_date=borrow_date1,
        expected_return_date=expected_return1,
        purpose="电子元器件测试",
        notes="需在无尘环境使用",
    )
    instr4.status = InstrumentStatus.BORROWED
    data_manager.update_instrument(instr4)
    data_manager.add_borrow_record(borrow_record1)
    
    borrow_date2 = today - timedelta(days=20)
    return_date2 = today - timedelta(days=5)
    borrow_record2 = BorrowRecord.create(
        instrument_id=instr1.id,
        borrower="周博士",
        borrower_department="化学系",
        borrow_date=borrow_date2,
        expected_return_date=today - timedelta(days=10),
        purpose="药物成分分析",
        notes="",
    )
    borrow_record2.mark_returned(return_date2, "仪器状态良好")
    data_manager.add_borrow_record(borrow_record2)
    
    cal_date1 = today - timedelta(days=365)
    next_cal1 = instr1.calibration_due_date
    cal_record1 = CalibrationRecord.create(
        instrument_id=instr1.id,
        calibration_date=cal_date1,
        next_calibration_date=next_cal1,
        certificate_number="CAL-HPLC-2024-001",
        calibration_agency="国家计量科学研究院",
        result="合格",
        notes="各项指标符合要求",
    )
    data_manager.add_calibration_record(cal_record1)
    
    cal_date2 = today - timedelta(days=330)
    next_cal2 = instr2.calibration_due_date
    cal_record2 = CalibrationRecord.create(
        instrument_id=instr2.id,
        calibration_date=cal_date2,
        next_calibration_date=next_cal2,
        certificate_number="CAL-BAL-2024-002",
        calibration_agency="省计量测试研究院",
        result="合格",
        notes="线性误差在允许范围内",
    )
    data_manager.add_calibration_record(cal_record2)
    
    cal_date3 = today - timedelta(days=400)
    next_cal3 = instr3.calibration_due_date
    cal_record3 = CalibrationRecord.create(
        instrument_id=instr3.id,
        calibration_date=cal_date3,
        next_calibration_date=next_cal3,
        certificate_number="CAL-UV-2024-003",
        calibration_agency="市计量检定所",
        result="合格",
        notes="波长准确度符合要求",
    )
    data_manager.add_calibration_record(cal_record3)
    
    admin_user = User.create_admin_user("admin", "系统管理员")
    data_manager.set_current_user(admin_user)
    
    operator = admin_user.display_name
    
    for instr in instruments:
        history = OperationHistory.create(
            instrument_id=instr.id,
            operation_type=OperationType.CREATE,
            operator=operator,
            details=f"新增样例仪器: {instr.name}",
        )
        data_manager.add_operation_history(history)
    
    history_borrow1 = OperationHistory.create(
        instrument_id=instr4.id,
        operation_type=OperationType.BORROW,
        operator=operator,
        details=f"借给 {borrow_record1.borrower} ({borrow_record1.borrower_department}), 用途: {borrow_record1.purpose}",
        related_record_id=borrow_record1.id,
    )
    data_manager.add_operation_history(history_borrow1)
    
    history_return2 = OperationHistory.create(
        instrument_id=instr1.id,
        operation_type=OperationType.RETURN,
        operator=operator,
        details=f"归还确认, 借用人: {borrow_record2.borrower}",
        related_record_id=borrow_record2.id,
    )
    data_manager.add_operation_history(history_return2)
    
    history_freeze = OperationHistory.create(
        instrument_id=instr5.id,
        operation_type=OperationType.FREEZE,
        operator=operator,
        details="待年度检修后重新校准",
    )
    data_manager.add_operation_history(history_freeze)
    
    normal_user = User.create_normal_user("user", "普通用户")
    data_manager.set_current_user(normal_user)
    
    data_manager.save()
