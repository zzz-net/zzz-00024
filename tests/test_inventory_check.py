import sys
import os
import tempfile
import csv
import json
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    User, UserRole, InstrumentStatus, InstrumentCategory,
    ConflictType, ConflictResolution, InventoryCheckStatus,
)
from src.storage import DataManager, DataExporter
from src.services import InstrumentService


def create_test_instruments(service: InstrumentService):
    instr1 = service.create_instrument(
        name="显微镜", category=InstrumentCategory.OPTICAL, model="XSP-300",
        serial_number="SN001", location="实验室A-101", manager="王主任"
    )
    instr2 = service.create_instrument(
        name="离心机", category=InstrumentCategory.MECHANICAL, model="TD5A-WS",
        serial_number="SN002", location="实验室B-201", manager="李主任"
    )
    instr3 = service.create_instrument(
        name="pH计", category=InstrumentCategory.ANALYSIS, model="PHS-3C",
        serial_number="SN003", location="实验室C-301", manager="张主任"
    )
    instr4 = service.create_instrument(
        name="天平", category=InstrumentCategory.ANALYSIS, model="FA2004",
        serial_number="SN004", location="实验室C-302", manager="张主任"
    )
    return instr1, instr2, instr3, instr4


def create_test_csv_file(filepath: str, items: list):
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['serial_number', 'actual_location', 'checker', 'check_time', 'remarks'])
        for item in items:
            writer.writerow([
                item.get('serial_number', ''),
                item.get('actual_location', ''),
                item.get('checker', ''),
                item.get('check_time', ''),
                item.get('remarks', '')
            ])


def create_test_json_file(filepath: str, items: list):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({'items': items}, f, ensure_ascii=False, indent=2)


def test_csv_parsing():
    print("\n【测试1】CSV文件解析")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        create_test_instruments(service)
        
        csv_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-101', 'checker': '盘点员甲', 'check_time': '2026-06-09 10:00:00', 'remarks': ''},
            {'serial_number': 'SN002', 'actual_location': '实验室B-202', 'checker': '盘点员甲', 'check_time': '2026-06-09 10:05:00', 'remarks': '位置不对'},
        ]
        csv_path = os.path.join(tmpdir, 'check.csv')
        create_test_csv_file(csv_path, csv_items)
        
        success, msg, items = service.parse_inventory_check_file(csv_path)
        assert success, f"CSV解析失败: {msg}"
        assert len(items) == 2
        assert items[0]['serial_number'] == 'SN001'
        assert items[1]['actual_location'] == '实验室B-202'
        print(f"  ✓ CSV解析成功，共 {len(items)} 条记录")


def test_json_parsing():
    print("\n【测试2】JSON文件解析")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        create_test_instruments(service)
        
        json_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-101', 'checker': '盘点员乙', 'check_time': '2026-06-09 11:00:00', 'remarks': ''},
            {'serial_number': 'SN003', 'actual_location': '实验室C-301', 'checker': '盘点员乙', 'check_time': '2026-06-09 11:10:00', 'remarks': ''},
        ]
        json_path = os.path.join(tmpdir, 'check.json')
        create_test_json_file(json_path, json_items)
        
        success, msg, items = service.parse_inventory_check_file(json_path)
        assert success, f"JSON解析失败: {msg}"
        assert len(items) == 2
        print(f"  ✓ JSON解析成功，共 {len(items)} 条记录")


def test_conflict_detection():
    print("\n【测试3】冲突类型检测")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        service.borrow_instrument(
            instrument_id=instr3.id, borrower="测试人员",
            borrower_department="测试部", borrow_date=date.today(),
            expected_return_date=date.today() + timedelta(days=7),
            purpose="测试借用"
        )
        instr3 = service.get_instrument_by_id(instr3.id)
        assert instr3.status == InstrumentStatus.BORROWED
        
        check_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-101', 'checker': '盘点员', 'check_time': '2026-06-09 10:00:00'},
            {'serial_number': 'SN002', 'actual_location': '实验室B-202', 'checker': '盘点员', 'check_time': '2026-06-09 10:05:00'},
            {'serial_number': 'SN003', 'actual_location': '实验室C-301', 'checker': '盘点员', 'check_time': '2026-06-09 10:10:00'},
            {'serial_number': 'SN999', 'actual_location': '实验室D-401', 'checker': '盘点员', 'check_time': '2026-06-09 10:15:00'},
            {'serial_number': 'SN002', 'actual_location': '实验室B-203', 'checker': '盘点员', 'check_time': '2026-06-09 10:20:00'},
        ]
        
        success, msg, check = service.create_inventory_check(
            name="测试盘点", checker="测试盘点员"
        )
        assert success
        
        success, msg, conflicts = service.detect_conflicts(check.id, check_items)
        assert success
        
        conflict_types = [c.conflict_type for c in conflicts]
        print(f"  共检测到 {len(conflicts)} 条冲突")
        print(f"    位置不一致: {conflict_types.count(ConflictType.LOCATION_MISMATCH)}")
        print(f"    已借出却在库: {conflict_types.count(ConflictType.BORROWED_BUT_PRESENT)}")
        print(f"    未知仪器: {conflict_types.count(ConflictType.UNKNOWN_INSTRUMENT)}")
        print(f"    重复序列号: {conflict_types.count(ConflictType.DUPLICATE_SERIAL)}")
        print(f"  匹配数量: {check.matched_count}")
        
        assert ConflictType.LOCATION_MISMATCH in conflict_types
        assert ConflictType.BORROWED_BUT_PRESENT in conflict_types
        assert ConflictType.UNKNOWN_INSTRUMENT in conflict_types
        assert ConflictType.DUPLICATE_SERIAL in conflict_types
        assert check.matched_count == 1
        assert check.conflict_count == 4
        print("  ✓ 所有冲突类型检测正确")


def test_conflict_resolution():
    print("\n【测试4】冲突处理确认")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        check_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-101', 'checker': '盘点员', 'check_time': '2026-06-09 10:00:00'},
            {'serial_number': 'SN002', 'actual_location': '实验室B-202', 'checker': '盘点员', 'check_time': '2026-06-09 10:05:00'},
            {'serial_number': 'SN004', 'actual_location': '实验室C-303', 'checker': '盘点员', 'check_time': '2026-06-09 10:10:00'},
        ]
        
        success, msg, check = service.create_inventory_check(
            name="测试盘点-处理", checker="测试盘点员"
        )
        success, msg, conflicts = service.detect_conflicts(check.id, check_items)
        
        loc_conflict = next(c for c in conflicts if c.conflict_type == ConflictType.LOCATION_MISMATCH)
        old_location = instr2.location
        print(f"  仪器 SN002 原位置: {old_location}")
        print(f"  盘点位置: {loc_conflict.actual_value}")
        
        success, msg, _ = service.resolve_conflict(
            loc_conflict.id, ConflictResolution.CONFIRM, "位置确实变更了"
        )
        assert success
        
        instr2 = service.get_instrument_by_id(instr2.id)
        print(f"  处理后位置: {instr2.location}")
        assert instr2.location == "实验室B-202"
        
        loc_conflict2 = next(c for c in conflicts if c.serial_number == "SN004")
        success, msg, _ = service.resolve_conflict(
            loc_conflict2.id, ConflictResolution.IGNORE, "位置没问题"
        )
        assert success
        
        instr4 = service.get_instrument_by_id(instr4.id)
        assert instr4.location == "实验室C-302"
        
        check = service.get_inventory_check_by_id(check.id)
        assert check.status == InventoryCheckStatus.COMPLETED
        print("  ✓ 冲突处理正确，位置更新和忽略逻辑正常")


def test_batch_resolution():
    print("\n【测试5】批量冲突处理")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        check_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-102', 'checker': '盘点员', 'check_time': '2026-06-09 10:00:00'},
            {'serial_number': 'SN002', 'actual_location': '实验室B-202', 'checker': '盘点员', 'check_time': '2026-06-09 10:05:00'},
            {'serial_number': 'SN003', 'actual_location': '实验室C-302', 'checker': '盘点员', 'check_time': '2026-06-09 10:10:00'},
        ]
        
        success, msg, check = service.create_inventory_check(
            name="测试盘点-批量处理", checker="测试盘点员"
        )
        success, msg, conflicts = service.detect_conflicts(check.id, check_items)
        
        assert len(conflicts) == 3
        
        success, msg, count = service.resolve_all_conflicts(check.id, ConflictResolution.CONFIRM)
        assert success
        assert count == 3
        
        instr1 = service.get_instrument_by_id(instr1.id)
        instr2 = service.get_instrument_by_id(instr2.id)
        instr3 = service.get_instrument_by_id(instr3.id)
        
        assert instr1.location == "实验室A-102"
        assert instr2.location == "实验室B-202"
        assert instr3.location == "实验室C-302"
        
        check = service.get_inventory_check_by_id(check.id)
        assert check.status == InventoryCheckStatus.COMPLETED
        print(f"  ✓ 批量处理 {count} 条冲突，位置全部更新")


def test_undo_functionality():
    print("\n【测试6】撤销最近盘点更新")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        original_locations = {
            instr1.id: instr1.location,
            instr2.id: instr2.location,
        }
        
        check_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-102', 'checker': '盘点员', 'check_time': '2026-06-09 10:00:00'},
            {'serial_number': 'SN002', 'actual_location': '实验室B-202', 'checker': '盘点员', 'check_time': '2026-06-09 10:05:00'},
        ]
        
        success, msg, check = service.create_inventory_check(
            name="测试盘点-撤销", checker="测试盘点员"
        )
        success, msg, conflicts = service.detect_conflicts(check.id, check_items)
        success, msg, count = service.resolve_all_conflicts(check.id, ConflictResolution.CONFIRM)
        service.mark_check_completed(check.id)
        
        check = service.get_inventory_check_by_id(check.id)
        assert check.can_undo == True
        
        instr1 = service.get_instrument_by_id(instr1.id)
        instr2 = service.get_instrument_by_id(instr2.id)
        print(f"  盘点更新后位置: SN001={instr1.location}, SN002={instr2.location}")
        
        success, msg, _ = service.undo_last_inventory_check()
        assert success
        
        instr1 = service.get_instrument_by_id(instr1.id)
        instr2 = service.get_instrument_by_id(instr2.id)
        print(f"  撤销后位置: SN001={instr1.location}, SN002={instr2.location}")
        
        assert instr1.location == original_locations[instr1.id]
        assert instr2.location == original_locations[instr2.id]
        
        check = service.get_inventory_check_by_id(check.id)
        assert check.can_undo == False
        
        can_undo, _ = service.can_undo_last_check()
        assert can_undo == False
        print("  ✓ 撤销功能正常，位置已恢复")


def test_cross_restart_history():
    print("\n【测试7】跨重启盘点历史持久化")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        check_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-101', 'checker': '盘点员', 'check_time': '2026-06-09 10:00:00'},
            {'serial_number': 'SN002', 'actual_location': '实验室B-202', 'checker': '盘点员', 'check_time': '2026-06-09 10:05:00'},
        ]
        
        success, msg, check = service.create_inventory_check(
            name="测试盘点-重启", checker="测试盘点员"
        )
        success, msg, conflicts = service.detect_conflicts(check.id, check_items)
        success, msg, count = service.resolve_all_conflicts(check.id, ConflictResolution.CONFIRM)
        
        checks_before = service.get_inventory_checks()
        conflicts_before = service.get_inventory_check_conflicts(check.id)
        print(f"  重启前: {len(checks_before)} 条盘点记录, {len(conflicts_before)} 条冲突")
        
        dm2 = DataManager(data_dir=tmpdir)
        service2 = InstrumentService(dm2)
        
        checks_after = service2.get_inventory_checks()
        conflicts_after = service2.get_inventory_check_conflicts(check.id)
        print(f"  重启后: {len(checks_after)} 条盘点记录, {len(conflicts_after)} 条冲突")
        
        assert len(checks_after) == len(checks_before)
        assert len(conflicts_after) == len(conflicts_before)
        
        check_after = service2.get_inventory_check_by_id(check.id)
        assert check_after.name == check.name
        assert check_after.checker == check.checker
        assert check_after.status == InventoryCheckStatus.COMPLETED
        
        conflict_after = conflicts_after[0]
        assert conflict_after.resolution == ConflictResolution.CONFIRM
        assert conflict_after.resolved_by == admin.display_name
        print("  ✓ 跨重启数据一致，历史记录和冲突结论完整保留")


def test_export_functionality():
    print("\n【测试8】盘点导出功能")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        check_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-101', 'checker': '盘点员', 'check_time': '2026-06-09 10:00:00'},
            {'serial_number': 'SN002', 'actual_location': '实验室B-202', 'checker': '盘点员', 'check_time': '2026-06-09 10:05:00'},
        ]
        
        success, msg, check = service.create_inventory_check(
            name="测试盘点-导出", checker="测试盘点员"
        )
        success, msg, conflicts = service.detect_conflicts(check.id, check_items)
        success, msg, count = service.resolve_all_conflicts(check.id, ConflictResolution.CONFIRM)
        
        checks = service.get_inventory_checks()
        
        csv_path = os.path.join(tmpdir, 'check_summary.csv')
        DataExporter.export_inventory_checks_summary_to_csv(checks, csv_path)
        assert os.path.exists(csv_path)
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert '测试盘点-导出' in content
            assert '测试盘点员' in content
        print("  ✓ 盘点汇总CSV导出成功")
        
        json_path = os.path.join(tmpdir, 'check_summary.json')
        DataExporter.export_inventory_checks_summary_to_json(checks, json_path)
        assert os.path.exists(json_path)
        print("  ✓ 盘点汇总JSON导出成功")
        
        detail_csv = os.path.join(tmpdir, 'check_detail.csv')
        DataExporter.export_inventory_check_to_csv(check, conflicts, detail_csv)
        assert os.path.exists(detail_csv)
        with open(detail_csv, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert '=== 盘点汇总 ===' in content
            assert '=== 冲突明细 ===' in content
            assert '位置不一致' in content
            assert 'SN002' in content
        print("  ✓ 盘点明细CSV导出成功，包含汇总和冲突明细")
        
        detail_json = os.path.join(tmpdir, 'check_detail.json')
        DataExporter.export_inventory_check_to_json(check, conflicts, detail_json)
        assert os.path.exists(detail_json)
        with open(detail_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'summary' in data
            assert 'conflicts' in data
        print("  ✓ 盘点明细JSON导出成功")


def test_operation_history_tracking():
    print("\n【测试9】操作历史记录")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dm = DataManager(data_dir=tmpdir)
        service = InstrumentService(dm)
        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)
        
        instr1, instr2, instr3, instr4 = create_test_instruments(service)
        
        check_items = [
            {'serial_number': 'SN001', 'actual_location': '实验室A-102', 'checker': '盘点员', 'check_time': '2026-06-09 10:00:00'},
        ]
        
        success, msg, check = service.create_inventory_check(
            name="测试盘点-历史", checker="测试盘点员"
        )
        success, msg, conflicts = service.detect_conflicts(check.id, check_items)
        success, msg, _ = service.resolve_conflict(
            conflicts[0].id, ConflictResolution.CONFIRM
        )
        
        histories = service.get_operation_histories(instr1.id)
        check_history = next(
            (h for h in histories if '盘点位置更新' in h.details),
            None
        )
        assert check_history is not None
        assert check_history.related_record_id == check.id
        print(f"  ✓ 操作历史已记录，关联盘点ID正确")
        
        success, msg, _ = service.undo_last_inventory_check()
        
        histories = service.get_operation_histories(instr1.id)
        undo_history = next(
            (h for h in histories if '撤销盘点位置更新' in h.details),
            None
        )
        assert undo_history is not None
        print("  ✓ 撤销操作历史也已记录")


if __name__ == "__main__":
    print("=" * 60)
    print("批量盘点功能测试套件")
    print("=" * 60)
    
    all_passed = True
    tests = [
        test_csv_parsing,
        test_json_parsing,
        test_conflict_detection,
        test_conflict_resolution,
        test_batch_resolution,
        test_undo_functionality,
        test_cross_restart_history,
        test_export_functionality,
        test_operation_history_tracking,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"\n  ✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！✓")
    else:
        print("部分测试失败！✗")
    print("=" * 60)
    sys.exit(0 if all_passed else 1)
