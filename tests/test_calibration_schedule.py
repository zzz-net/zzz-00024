import sys
import os
import tempfile
import csv
import json
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    User, UserRole, InstrumentStatus, InstrumentCategory,
    CalibrationConflictType, CalibrationConflictResolution,
    CalibrationScheduleStatus, CalibrationScheduleItemStatus,
    OperationType,
)
from src.storage import DataManager, DataExporter
from src.services import InstrumentService


def create_test_instruments(service: InstrumentService):
    instr1 = service.create_instrument(
        name="显微镜", category=InstrumentCategory.OPTICAL, model="XSP-300",
        serial_number="SN001", location="实验室A-101", manager="王主任",
        calibration_due_date=date.today() + timedelta(days=30)
    )
    instr2 = service.create_instrument(
        name="离心机", category=InstrumentCategory.MECHANICAL, model="TD5A-WS",
        serial_number="SN002", location="实验室B-201", manager="李主任",
        calibration_due_date=date.today() + timedelta(days=60)
    )
    instr3 = service.create_instrument(
        name="pH计", category=InstrumentCategory.ANALYSIS, model="PHS-3C",
        serial_number="SN003", location="实验室C-301", manager="张主任",
        calibration_due_date=date.today() + timedelta(days=90)
    )
    instr4 = service.create_instrument(
        name="天平", category=InstrumentCategory.ANALYSIS, model="FA2004",
        serial_number="SN004", location="实验室C-302", manager="张主任",
        calibration_due_date=date.today() - timedelta(days=10)
    )
    return instr1, instr2, instr3, instr4


def create_calibration_test_csv(filepath: str, items: list):
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['serial_number', 'planned_date', 'calibration_agency', 'certificate_number', 'notes'])
        for item in items:
            writer.writerow([
                item.get('serial_number', ''),
                item.get('planned_date', ''),
                item.get('calibration_agency', ''),
                item.get('certificate_number', ''),
                item.get('notes', '')
            ])


def create_calibration_test_json(filepath: str, items: list):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({'items': items}, f, ensure_ascii=False, indent=2)


def test_csv_import_parsing():
    print("\n【测试1】CSV校准计划导入解析")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        create_test_instruments(service)
        
        planned_date = date.today() + timedelta(days=7)
        csv_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date.isoformat(), 'calibration_agency': '计量院', 'certificate_number': 'CERT2026001', 'notes': '年度校准'},
            {'serial_number': 'SN002', 'planned_date': planned_date.isoformat(), 'calibration_agency': '计量院', 'certificate_number': 'CERT2026002', 'notes': ''},
        ]
        csv_path = os.path.join(tmpdir, 'calibration_plan.csv')
        create_calibration_test_csv(csv_path, csv_items)
        
        success, msg, items = service.parse_calibration_schedule_file(csv_path)
        assert success, f"CSV解析失败: {msg}"
        assert len(items) == 2
        assert items[0]['serial_number'] == 'SN001'
        assert items[1]['planned_date'] == planned_date.isoformat()
        print(f"  [OK] CSV解析成功，共 {len(items)} 条记录")


def test_json_import_parsing():
    print("\n【测试2】JSON校准计划导入解析")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        create_test_instruments(service)
        
        planned_date = date.today() + timedelta(days=14)
        json_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date.isoformat(), 'calibration_agency': '测试中心', 'certificate_number': 'CERT2026003'},
            {'serial_number': 'SN003', 'planned_date': planned_date.isoformat(), 'calibration_agency': '测试中心', 'certificate_number': 'CERT2026004'},
        ]
        json_path = os.path.join(tmpdir, 'calibration_plan.json')
        create_calibration_test_json(json_path, json_items)
        
        success, msg, items = service.parse_calibration_schedule_file(json_path)
        assert success, f"JSON解析失败: {msg}"
        assert len(items) == 2
        assert items[0]['planned_date'] == planned_date.isoformat()
        print(f"  [OK] JSON解析成功，共 {len(items)} 条记录")


def test_conflict_detection():
    print("\n【测试3】冲突类型检测")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        instr5 = service.create_instrument(
            name="温度计", category=InstrumentCategory.ANALYSIS, model="TM-100",
            serial_number="SN005", location="实验室C-303", manager="张主任"
        )
        
        service.borrow_instrument(
            instrument_id=instr3.id, borrower="测试人员",
            borrower_department="测试部", borrow_date=date.today(),
            expected_return_date=date.today() + timedelta(days=7),
            purpose="测试借用"
        )
        service.freeze_instrument(instr4.id, "设备维修中")
        
        instr3 = service.get_instrument_by_id(instr3.id)
        instr4 = service.get_instrument_by_id(instr4.id)
        assert instr3.status == InstrumentStatus.BORROWED
        assert instr4.status == InstrumentStatus.FROZEN
        
        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026001'},
            {'serial_number': 'SN002', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026001'},
            {'serial_number': 'SN005', 'planned_date': None, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026002'},
            {'serial_number': 'SN003', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026003'},
            {'serial_number': 'SN004', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026004'},
            {'serial_number': 'SN999', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026005'},
            {'serial_number': 'SN001', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026006'},
        ]
        
        success, msg, schedule = service.create_calibration_schedule(
            name="2026年Q2校准计划", plan_date=date.today()
        )
        assert success
        
        success, msg, conflicts = service.detect_calibration_conflicts(schedule.id, import_items)
        assert success
        
        conflict_types = [c.conflict_type for c in conflicts]
        print(f"  共检测到 {len(conflicts)} 条冲突")
        print(f"    日期缺失: {conflict_types.count(CalibrationConflictType.MISSING_DATE)}")
        print(f"    证书号重复: {conflict_types.count(CalibrationConflictType.DUPLICATE_CERTIFICATE)}")
        print(f"    仪器不存在: {conflict_types.count(CalibrationConflictType.INSTRUMENT_NOT_FOUND)}")
        print(f"    已借出冲突: {conflict_types.count(CalibrationConflictType.BORROWED_CONFLICT)}")
        print(f"    已冻结冲突: {conflict_types.count(CalibrationConflictType.FROZEN_CONFLICT)}")
        print(f"    序列号重复: {conflict_types.count(CalibrationConflictType.DUPLICATE_SERIAL)}")
        
        assert CalibrationConflictType.MISSING_DATE in conflict_types
        assert CalibrationConflictType.DUPLICATE_CERTIFICATE in conflict_types
        assert CalibrationConflictType.INSTRUMENT_NOT_FOUND in conflict_types
        assert CalibrationConflictType.BORROWED_CONFLICT in conflict_types
        assert CalibrationConflictType.FROZEN_CONFLICT in conflict_types
        assert CalibrationConflictType.DUPLICATE_SERIAL in conflict_types
        print("  [OK] 所有冲突类型检测正确")


def test_permission_control():
    print("\n【测试4】权限控制")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        
        regular_user = User.create_normal_user("user1", "普通用户")
        service.set_current_user(regular_user)
        
        success, msg, _ = service.create_calibration_schedule(name="测试计划", plan_date=date.today())
        assert not success, "普通用户应该无法创建校准排程"
        print(f"  [OK] 普通用户创建排程被拒绝: {msg}")
        
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        success, msg, schedule = service.create_calibration_schedule(
            name="管理员测试计划", plan_date=date.today()
        )
        assert success
        print(f"  [OK] 管理员成功创建排程: {schedule.name}")
        
        service.set_current_user(regular_user)
        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026001'},
        ]
        
        success, msg, _ = service.detect_calibration_conflicts(schedule.id, import_items)
        assert not success, "普通用户应该无法检测冲突"
        print(f"  [OK] 普通用户检测冲突被拒绝: {msg}")
        
        print("  [OK] 权限控制正常")


def test_conflict_resolution():
    print("\n【测试5】冲突处理确认")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026001'},
            {'serial_number': 'SN999', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026002'},
        ]
        
        success, msg, schedule = service.create_calibration_schedule(
            name="测试校准计划", plan_date=date.today()
        )
        assert success
        
        success, msg, conflicts = service.detect_calibration_conflicts(schedule.id, import_items)
        assert success
        assert len(conflicts) == 1
        
        not_found_conflict = conflicts[0]
        assert not_found_conflict.conflict_type == CalibrationConflictType.INSTRUMENT_NOT_FOUND
        
        success, msg, _ = service.resolve_calibration_conflict(
            not_found_conflict.id, CalibrationConflictResolution.IGNORE, "忽略不存在的仪器"
        )
        assert success
        
        success, msg, _ = service.mark_calibration_schedule_import_completed(schedule.id)
        assert success
        
        schedule = service.get_calibration_schedule_by_id(schedule.id)
        assert schedule.status == CalibrationScheduleStatus.COMPLETED
        
        items = service.get_calibration_schedule_items(schedule_id=schedule.id)
        assert len(items) == 1
        assert items[0].serial_number == 'SN001'
        
        print("  [OK] 冲突处理正确，导入完成")


def test_calibration_completion_and_undo():
    print("\n【测试6】校准完成和撤销")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        old_due_date = instr1.calibration_due_date
        
        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': ''},
        ]
        
        success, msg, schedule = service.create_calibration_schedule(
            name="校准完成测试", plan_date=date.today()
        )
        success, msg, conflicts = service.detect_calibration_conflicts(schedule.id, import_items)
        success, msg, _ = service.mark_calibration_schedule_import_completed(schedule.id)
        
        items = service.get_calibration_schedule_items(schedule_id=schedule.id)
        assert len(items) == 1
        item = items[0]
        
        print(f"  仪器原校准到期日: {old_due_date}")
        print(f"  排程项目状态: {item.status.value}")
        
        calibration_date = date.today()
        next_calibration_date = date.today() + timedelta(days=365)
        
        success, msg, updated_item = service.complete_calibration_schedule_item(
            item_id=item.id,
            calibration_date=calibration_date,
            next_calibration_date=next_calibration_date,
            certificate_number="CERT2026-COMP001",
            calibration_agency="国家计量院",
            result="合格",
            notes="校准完成"
        )
        assert success
        
        instr1 = service.get_instrument_by_id(instr1.id)
        assert instr1.calibration_due_date == next_calibration_date
        assert instr1.status == InstrumentStatus.AVAILABLE
        
        updated_item = service.get_calibration_schedule_item_by_id(item.id)
        assert updated_item.status == CalibrationScheduleItemStatus.COMPLETED
        assert updated_item.certificate_number == "CERT2026-COMP001"
        
        print(f"  校准后到期日: {instr1.calibration_due_date}")
        print(f"  排程项目状态: {updated_item.status.value}")
        
        can_undo, undo_item = service.can_undo_last_calibration_schedule()
        assert can_undo
        assert undo_item.id == item.id
        
        success, msg, reverted_item = service.undo_last_calibration_completion()
        assert success
        
        instr1 = service.get_instrument_by_id(instr1.id)
        assert instr1.calibration_due_date == old_due_date
        
        reverted_item = service.get_calibration_schedule_item_by_id(item.id)
        assert reverted_item.status == CalibrationScheduleItemStatus.SCHEDULED
        assert reverted_item.certificate_number == ""
        
        print(f"  撤销后期日: {instr1.calibration_due_date}")
        print(f"  排程项目状态: {reverted_item.status.value}")
        
        print("  [OK] 校准完成和撤销功能正常")


def test_cross_restart_persistence():
    print("\n【测试7】跨重启持久化")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm1 = DataManager(data_dir=tmpdir)
        service1 = InstrumentService(dm1)
        admin = User.create_admin_user("admin", "管理员")
        service1.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service1)
        
        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026001'},
            {'serial_number': 'SN002', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': ''},
        ]
        
        success, msg, schedule = service1.create_calibration_schedule(
            name="持久化测试计划", plan_date=date.today(), notes="测试重启后数据保留"
        )
        success, msg, conflicts = service1.detect_calibration_conflicts(schedule.id, import_items)
        
        for conflict in conflicts:
            service1.resolve_calibration_conflict(
                conflict.id, CalibrationConflictResolution.IGNORE, "测试处理"
            )
        
        success, msg, _ = service1.mark_calibration_schedule_import_completed(schedule.id)
        
        calibration_date = date.today()
        next_date = date.today() + timedelta(days=365)
        items = service1.get_calibration_schedule_items(schedule_id=schedule.id)
        service1.complete_calibration_schedule_item(
            item_id=items[0].id,
            calibration_date=calibration_date,
            next_calibration_date=next_date,
            certificate_number="CERT2026-PERSIST",
            calibration_agency="测试机构",
            result="合格"
        )
        
        schedules_before = service1.get_calibration_schedules()
        items_before = service1.get_calibration_schedule_items()
        conflicts_before = service1.get_calibration_schedule_conflicts()
        histories_before = [
            h for h in service1.get_operation_histories()
            if h.operation_type == OperationType.CALIBRATION_SCHEDULE_IMPORT
        ]
        
        print(f"  重启前排程数: {len(schedules_before)}")
        print(f"  重启前项目数: {len(items_before)}")
        print(f"  重启前冲突数: {len(conflicts_before)}")
        print(f"  重启前操作日志数: {len(histories_before)}")
        
        del service1
        del dm1
        
        dm2 = DataManager(data_dir=tmpdir)
        service2 = InstrumentService(dm2)
        service2.set_current_user(admin)
        
        schedules_after = service2.get_calibration_schedules()
        items_after = service2.get_calibration_schedule_items()
        conflicts_after = service2.get_calibration_schedule_conflicts()
        histories_after = [
            h for h in service2.get_operation_histories()
            if h.operation_type == OperationType.CALIBRATION_SCHEDULE_IMPORT
        ]
        
        print(f"  重启后排程数: {len(schedules_after)}")
        print(f"  重启后项目数: {len(items_after)}")
        print(f"  重启后冲突数: {len(conflicts_after)}")
        print(f"  重启后操作日志数: {len(histories_after)}")
        
        assert len(schedules_after) == len(schedules_before)
        assert len(items_after) == len(items_before)
        assert len(conflicts_after) == len(conflicts_before)
        assert len(histories_after) == len(histories_before)
        
        schedule_after = service2.get_calibration_schedule_by_id(schedule.id)
        assert schedule_after.name == "持久化测试计划"
        assert schedule_after.status == CalibrationScheduleStatus.COMPLETED
        
        item_after = service2.get_calibration_schedule_item_by_id(items[0].id)
        assert item_after.status == CalibrationScheduleItemStatus.COMPLETED
        assert item_after.certificate_number == "CERT2026-PERSIST"
        assert item_after.processed_by == admin.display_name
        
        print("  [OK] 跨重启数据持久化正常")


def test_export_functionality():
    print("\n【测试8】导出功能")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026001'},
            {'serial_number': 'SN999', 'planned_date': planned_date, 'calibration_agency': '计量院', 'certificate_number': 'CERT2026002'},
        ]
        
        success, msg, schedule = service.create_calibration_schedule(
            name="导出测试计划", plan_date=date.today()
        )
        success, msg, conflicts = service.detect_calibration_conflicts(schedule.id, import_items)
        success, msg, _ = service.mark_calibration_schedule_import_completed(schedule.id)
        
        items = service.get_calibration_schedule_items(schedule_id=schedule.id)
        service.complete_calibration_schedule_item(
            item_id=items[0].id,
            calibration_date=date.today(),
            next_calibration_date=date.today() + timedelta(days=365),
            certificate_number="CERT2026-EXPORT",
            calibration_agency="测试机构",
            result="合格"
        )
        
        export_dir = os.path.join(tmpdir, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        schedules = service.get_calibration_schedules()
        csv_path = DataExporter.generate_export_filename("calibration_schedules_summary", "csv", export_dir)
        filepath = DataExporter.export_calibration_schedules_summary_to_csv(schedules, csv_path)
        assert os.path.exists(filepath)
        print(f"  [OK] 校准排程汇总CSV导出: {os.path.basename(filepath)}")
        
        all_items = service.get_calibration_schedule_items()
        instruments = service.get_instruments()
        csv_path = DataExporter.generate_export_filename("calibration_schedule_items", "csv", export_dir)
        filepath = DataExporter.export_calibration_schedule_items_to_csv(all_items, csv_path, instruments)
        assert os.path.exists(filepath)
        print(f"  [OK] 校准排程明细CSV导出: {os.path.basename(filepath)}")
        
        all_conflicts = service.get_calibration_schedule_conflicts()
        csv_path = DataExporter.generate_export_filename("calibration_schedule_conflicts", "csv", export_dir)
        filepath = DataExporter.export_calibration_schedule_conflicts_to_csv(all_conflicts, csv_path)
        assert os.path.exists(filepath)
        print(f"  [OK] 冲突明细CSV导出: {os.path.basename(filepath)}")
        
        overdue_items = service.get_overdue_calibration_items()
        csv_path = DataExporter.generate_export_filename("overdue_calibration_items", "csv", export_dir)
        filepath = DataExporter.export_overdue_calibration_items_to_csv(overdue_items, csv_path)
        assert os.path.exists(filepath)
        print(f"  [OK] 逾期清单CSV导出: {os.path.basename(filepath)}")
        
        json_path = DataExporter.generate_export_filename("calibration_schedules_summary", "json", export_dir)
        filepath = DataExporter.export_calibration_schedules_summary_to_json(schedules, json_path)
        assert os.path.exists(filepath)
        print(f"  [OK] 校准排程汇总JSON导出: {os.path.basename(filepath)}")
        
        json_path = DataExporter.generate_export_filename("overdue_calibration_items", "json", export_dir)
        filepath = DataExporter.export_overdue_calibration_items_to_json(overdue_items, json_path)
        assert os.path.exists(filepath)
        print(f"  [OK] 逾期清单JSON导出: {os.path.basename(filepath)}")
        
        print("  [OK] 所有导出功能正常")


def test_overdue_detection():
    print("\n【测试9】逾期和快到期检测")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        past_date = date.today() - timedelta(days=15)
        soon_date = date.today() + timedelta(days=7)
        future_date = date.today() + timedelta(days=60)
        
        import_items = [
            {'serial_number': 'SN001', 'planned_date': past_date, 'calibration_agency': '计量院', 'certificate_number': ''},
            {'serial_number': 'SN002', 'planned_date': soon_date, 'calibration_agency': '计量院', 'certificate_number': ''},
            {'serial_number': 'SN003', 'planned_date': future_date, 'calibration_agency': '计量院', 'certificate_number': ''},
            {'serial_number': 'SN004', 'planned_date': past_date, 'calibration_agency': '计量院', 'certificate_number': ''},
        ]
        
        success, msg, schedule = service.create_calibration_schedule(
            name="逾期检测测试", plan_date=date.today()
        )
        success, msg, conflicts = service.detect_calibration_conflicts(schedule.id, import_items)
        success, msg, _ = service.mark_calibration_schedule_import_completed(schedule.id)
        
        service.refresh_calibration_schedule_statuses()
        
        items = service.get_calibration_schedule_items(schedule_id=schedule.id)
        statuses = [item.status for item in items]
        
        print(f"  已过期项目数: {statuses.count(CalibrationScheduleItemStatus.OVERDUE)}")
        print(f"  排期中项目数: {statuses.count(CalibrationScheduleItemStatus.SCHEDULED)}")
        
        overdue_items = service.get_overdue_calibration_items()
        print(f"  检测到逾期项目: {len(overdue_items)}")
        
        upcoming_items = service.get_upcoming_calibration_items(days=30)
        print(f"  30天内到期项目: {len(upcoming_items)}")
        
        assert statuses.count(CalibrationScheduleItemStatus.OVERDUE) >= 2
        assert len(overdue_items) >= 2
        assert len(upcoming_items) >= 1
        
        print("  [OK] 逾期和快到期检测正常")


def test_gui_dialog_construction_with_is_admin():
    print("\n【测试10】GUI对话框is_admin参数传递（修复TypeError）")
    print("-" * 60)

    import tkinter as tk
    from src.ui.dialogs import CalibrationScheduleDialog, CalibrationScheduleHistoryDialog

    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        create_test_instruments(service)

        root = tk.Tk()
        root.withdraw()

        try:
            print("  测试CalibrationScheduleDialog接受is_admin参数...")
            dialog1 = CalibrationScheduleDialog(root, service, is_admin=True)
            assert dialog1.is_admin == True, "is_admin应该为True"
            dialog1.destroy()
            print("    [OK] CalibrationScheduleDialog接受is_admin=True")

            dialog2 = CalibrationScheduleDialog(root, service, is_admin=False)
            assert dialog2.is_admin == False, "is_admin应该为False"
            dialog2.destroy()
            print("    [OK] CalibrationScheduleDialog接受is_admin=False")

            dialog3 = CalibrationScheduleDialog(root, service)
            assert dialog3.is_admin == True, "默认is_admin应该根据用户权限判断"
            dialog3.destroy()
            print("    [OK] CalibrationScheduleDialog默认is_admin正常")

            print("  测试CalibrationScheduleHistoryDialog接受is_admin参数...")
            dialog4 = CalibrationScheduleHistoryDialog(root, service, is_admin=True)
            assert dialog4.is_admin == True, "is_admin应该为True"
            dialog4.destroy()
            print("    [OK] CalibrationScheduleHistoryDialog接受is_admin=True")

            dialog5 = CalibrationScheduleHistoryDialog(root, service, is_admin=False)
            assert dialog5.is_admin == False, "is_admin应该为False"
            dialog5.destroy()
            print("    [OK] CalibrationScheduleHistoryDialog接受is_admin=False")

            print("  测试普通用户权限...")
            regular_user = User.create_normal_user("user1", "普通用户")
            service.set_current_user(regular_user)
            dialog6 = CalibrationScheduleDialog(root, service)
            assert dialog6.is_admin == False, "普通用户is_admin应该为False"
            dialog6.destroy()
            print("    [OK] 普通用户is_admin正确为False")

        finally:
            root.destroy()

        print("  [OK] 所有GUI对话框is_admin参数传递正常")


def test_service_get_calibration_schedule_conflict_by_id():
    print("\n【测试11】服务层get_calibration_schedule_conflict_by_id方法（修复AttributeError）")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        create_test_instruments(service)

        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date.isoformat(),
             'calibration_agency': '计量院', 'certificate_number': 'CERT-GUI-001'},
            {'serial_number': 'NOT_EXIST', 'planned_date': planned_date.isoformat(),
             'calibration_agency': '计量院', 'certificate_number': 'CERT-GUI-002'},
        ]

        csv_path = os.path.join(tmpdir, 'gui_test.csv')
        create_calibration_test_csv(csv_path, import_items)

        print("  导入数据生成冲突...")
        success, msg, schedule = service.create_calibration_schedule(
            name="GUI测试排程", plan_date=date.today(), notes="测试"
        )
        assert success, f"创建排程应该成功: {msg}"
        assert schedule is not None

        success, msg, items = service.parse_calibration_schedule_file(csv_path)
        assert success, f"解析文件应该成功: {msg}"

        success, msg, conflicts = service.detect_calibration_conflicts(schedule.id, items)
        assert success, f"检测冲突应该成功: {msg}"
        assert len(conflicts) == 1, f"应该有1个冲突，实际有{len(conflicts)}个"

        conflict = conflicts[0]
        print(f"  生成冲突ID: {conflict.id}")

        print("  测试服务层get_calibration_schedule_conflict_by_id方法存在...")
        assert hasattr(service, 'get_calibration_schedule_conflict_by_id'), \
            "服务层应该有get_calibration_schedule_conflict_by_id方法"
        print("    [OK] 方法存在")

        print("  测试通过ID获取冲突...")
        fetched_conflict = service.get_calibration_schedule_conflict_by_id(conflict.id)
        assert fetched_conflict is not None, "应该能获取到冲突"
        assert fetched_conflict.id == conflict.id, "冲突ID应该匹配"
        assert fetched_conflict.conflict_type == conflict.conflict_type, "冲突类型应该匹配"
        assert fetched_conflict.serial_number == conflict.serial_number, "序列号应该匹配"
        print("    [OK] 能正确获取冲突")

        print("  测试获取不存在的冲突...")
        not_found = service.get_calibration_schedule_conflict_by_id("non-existent-id")
        assert not_found is None, "不存在的冲突应该返回None"
        print("    [OK] 不存在的冲突返回None")

        print("  [OK] 服务层get_calibration_schedule_conflict_by_id方法正常")


def test_single_conflict_resolution_flow():
    print("\n【测试12】单条冲突处理完整流程（修复选中冲突后处理的AttributeError）")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        instr1, instr2, instr3, instr4 = create_test_instruments(service)

        planned_date = date.today() + timedelta(days=7)
        import_items = [
            {'serial_number': 'SN001', 'planned_date': planned_date.isoformat(),
             'calibration_agency': '计量院', 'certificate_number': 'CERT-SINGLE-001'},
            {'serial_number': 'NOT_EXIST', 'planned_date': planned_date.isoformat(),
             'calibration_agency': '计量院', 'certificate_number': 'CERT-SINGLE-002'},
            {'serial_number': 'SN002', 'planned_date': '',
             'calibration_agency': '计量院', 'certificate_number': 'CERT-SINGLE-003'},
        ]

        csv_path = os.path.join(tmpdir, 'single_conflict_test.csv')
        create_calibration_test_csv(csv_path, import_items)

        print("  导入数据生成多个冲突...")
        success, msg, schedule = service.create_calibration_schedule(
            name="单条冲突处理测试", plan_date=date.today(), notes="测试单条处理"
        )
        assert success, f"创建排程应该成功: {msg}"
        assert schedule is not None

        success, msg, items = service.parse_calibration_schedule_file(csv_path)
        assert success, f"解析文件应该成功: {msg}"

        success, msg, conflicts = service.detect_calibration_conflicts(schedule.id, items)
        assert success, f"检测冲突应该成功: {msg}"
        assert len(conflicts) == 2, f"应该有2个冲突，实际有{len(conflicts)}个"

        schedule = service.get_calibration_schedules()[0]
        print(f"  排程ID: {schedule.id}")
        print(f"  冲突数量: {len(conflicts)}")

        print("  测试获取所有冲突...")
        all_conflicts = service.get_calibration_schedule_conflicts(schedule.id)
        assert len(all_conflicts) == 2, f"应该有2个冲突"
        print("    [OK] 能获取所有冲突")

        print("  测试选中第一条冲突进行处理...")
        conflict1 = all_conflicts[0]
        print(f"  处理冲突: {conflict1.conflict_type.value} - {conflict1.serial_number}")

        success, msg, updated_conflict = service.resolve_calibration_conflict(
            conflict_id=conflict1.id,
            resolution=CalibrationConflictResolution.IGNORE,
            notes="测试忽略"
        )
        assert success, f"处理应该成功: {msg}"
        assert updated_conflict is not None, "应该返回更新后的冲突"
        assert updated_conflict.resolution == CalibrationConflictResolution.IGNORE, "处理结果应该为忽略"
        assert updated_conflict.resolved_by == admin.display_name, "处理人应该正确"
        assert updated_conflict.resolved_at is not None, "处理时间应该设置"
        print("    [OK] 第一条冲突处理成功")

        print("  验证冲突已更新...")
        fetched = service.get_calibration_schedule_conflict_by_id(conflict1.id)
        assert fetched.resolution == CalibrationConflictResolution.IGNORE, "冲突状态应该已更新"
        print("    [OK] 冲突状态已持久化")

        print("  测试处理第二条冲突...")
        conflict2 = all_conflicts[1]
        print(f"  处理冲突: {conflict2.conflict_type.value} - {conflict2.serial_number}")

        success, msg, updated_conflict2 = service.resolve_calibration_conflict(
            conflict_id=conflict2.id,
            resolution=CalibrationConflictResolution.CONFIRM,
            notes="测试确认"
        )
        assert success, f"处理应该成功: {msg}"
        assert updated_conflict2.resolution == CalibrationConflictResolution.CONFIRM, "处理结果应该为确认"
        print("    [OK] 第二条冲突处理成功")

        print("  验证所有冲突处理完毕后排程状态更新...")
        schedule_after = service.get_calibration_schedule_by_id(schedule.id)
        assert schedule_after.status == CalibrationScheduleStatus.COMPLETED, \
            f"排程应该为完成状态，实际为{schedule_after.status.value}"
        print(f"    [OK] 排程状态: {schedule_after.status.value}")

        items = service.get_calibration_schedule_items(schedule.id)
        print(f"  排程项目数量: {len(items)}")
        assert len(items) >= 1, "应该至少有1条有效项目"

        print("  [OK] 单条冲突处理完整流程正常")


def run_all_tests():
    print("\n" + "=" * 70)
    print("校准排程功能回归测试")
    print("=" * 70)

    test_csv_import_parsing()
    test_json_import_parsing()
    test_conflict_detection()
    test_permission_control()
    test_conflict_resolution()
    test_calibration_completion_and_undo()
    test_cross_restart_persistence()
    test_export_functionality()
    test_overdue_detection()
    test_gui_dialog_construction_with_is_admin()
    test_service_get_calibration_schedule_conflict_by_id()
    test_single_conflict_resolution_flow()

    print("\n" + "=" * 70)
    print("所有测试通过! [OK]")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
