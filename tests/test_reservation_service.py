import sys
import os
import tempfile
import json
from datetime import date, timedelta
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import User, UserRole, Reservation, ReservationStatus, OperationType, InventoryItem
from src.storage import DataManager, DataExporter
from src.services import InstrumentService


def test_filtered_reservations():
    """测试带筛选条件的预约查询"""
    print("\n【测试1】带筛选条件的预约查询")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1), ReservationStatus.PENDING)
        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2), ReservationStatus.APPROVED)
        r3, _ = _create_test_reservation(service, item.id, "王五", "研发部", 3, today + timedelta(days=3), ReservationStatus.REJECTED)
        r4, _ = _create_test_reservation(service, item.id, "赵六", "财务部", 1, today + timedelta(days=10), ReservationStatus.PENDING)

        results = service.get_reservations_filtered(status_filter=ReservationStatus.PENDING.value)
        assert len(results) == 2, f"待审批筛选预期2条，实际{len(results)}"
        assert all(r.status == ReservationStatus.PENDING for r in results)
        print("  [OK] 通过：按状态筛选正确")

        results = service.get_reservations_filtered(department_filter="研发部")
        assert len(results) == 2, f"研发部筛选预期2条，实际{len(results)}"
        assert all(r.department == "研发部" for r in results)
        print("  [OK] 通过：按部门筛选正确")

        results = service.get_reservations_filtered(
            date_from=today + timedelta(days=1),
            date_to=today + timedelta(days=3)
        )
        assert len(results) == 3, f"日期范围筛选预期3条，实际{len(results)}"
        assert all(today + timedelta(days=1) <= r.expected_use_date <= today + timedelta(days=3) for r in results)
        print("  [OK] 通过：按日期范围筛选正确")

        results = service.get_reservations_filtered(
            status_filter=ReservationStatus.PENDING.value,
            department_filter="研发部",
            date_from=today + timedelta(days=1),
            date_to=today + timedelta(days=1)
        )
        assert len(results) == 1, f"组合筛选预期1条，实际{len(results)}"
        assert results[0].id == r1.id
        print("  [OK] 通过：组合筛选正确")


def test_department_list():
    """测试获取部门列表"""
    print("\n【测试2】获取部门列表")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1))
        _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2))
        _create_test_reservation(service, item.id, "王五", "研发部", 3, today + timedelta(days=3))

        departments = service.get_reservation_departments()
        assert len(departments) == 2, f"预期2个部门，实际{len(departments)}"
        assert "研发部" in departments
        assert "市场部" in departments
        print("  [OK] 通过：部门列表去重正确")


def test_conflict_detection():
    """测试库存冲突检测"""
    print("\n【测试3】库存冲突检测")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="会议室投影仪", category="办公", model="X1",
            total_quantity=2, unit="台"
        )

        today = date.today()
        target_date = today + timedelta(days=7)

        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 1, target_date)
        service.approve_reservation(r1.id)

        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, target_date)

        has_conflict, msg, conflicts, inv_item = service.detect_reservation_conflicts(r2.id)
        assert has_conflict, "应该检测到冲突"
        assert len(conflicts) == 1, f"预期1条冲突记录，实际{len(conflicts)}"
        assert conflicts[0].id == r1.id
        assert inv_item.id == item.id
        assert inv_item.locked_quantity == 1
        assert inv_item.available_quantity == 1
        print("  [OK] 通过：冲突检测正确，已审批预约产生冲突")

        r3, _ = _create_test_reservation(service, item.id, "王五", "财务部", 1, target_date)
        has_conflict, msg, conflicts, inv_item = service.detect_reservation_conflicts(r3.id)
        assert has_conflict, "应该检测到冲突（待审批也算）"
        assert len(conflicts) == 2, f"预期2条冲突记录（已审批+待审批），实际{len(conflicts)}"
        print("  [OK] 通过：待审批预约也计入冲突")

        r4, _ = _create_test_reservation(service, item.id, "赵六", "人事部", 1, target_date + timedelta(days=1))
        has_conflict, _, _, _ = service.detect_reservation_conflicts(r4.id)
        assert not has_conflict, "不同日期不应有冲突"
        print("  [OK] 通过：不同日期无冲突")


def test_approve_with_conflict_reason():
    """测试带冲突原因的审批"""
    print("\n【测试4】带冲突原因的审批")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="会议室投影仪", category="办公", model="X1",
            total_quantity=2, unit="台"
        )

        today = date.today()
        target_date = today + timedelta(days=7)

        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 1, target_date)
        service.approve_reservation(r1.id)

        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, target_date)

        success, msg, updated = service.approve_reservation_with_conflict(
            r2.id, conflict_reason="紧急会议，特批使用"
        )
        assert success, f"审批失败: {msg}"
        assert updated.status == ReservationStatus.APPROVED
        assert "紧急会议，特批使用" in updated.notes

        history = service.get_operation_histories()[:1]
        assert len(history) == 1
        assert history[0].operation_type == OperationType.RESERVATION_APPROVE
        assert "紧急会议，特批使用" in history[0].details
        print("  [OK] 通过：带冲突原因审批成功，操作历史记录正确")

        assert item.locked_quantity == 2, f"预期锁定2，实际{item.locked_quantity}"
        assert item.available_quantity == 0, f"预期可用0，实际{item.available_quantity}"
        print("  [OK] 通过：冲突审批后库存锁定正确")


def test_permission_restrictions():
    """测试权限限制 - 普通用户只能看自己的预约"""
    print("\n【测试5】权限限制 - 普通用户视图")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1))
        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2))
        r3, _ = _create_test_reservation(service, item.id, "张三", "研发部", 3, today + timedelta(days=3))

        normal_user = User.create_normal_user("zhangsan", "张三")
        service.set_current_user(normal_user)

        results = service.get_reservations_filtered()
        assert len(results) == 2, f"张三应看到2条自己的预约，实际{len(results)}"
        ids = [r.id for r in results]
        assert r1.id in ids
        assert r3.id in ids
        assert r2.id not in ids
        print("  [OK] 通过：普通用户只能看到自己的预约")

        success, msg, _ = service.approve_reservation_with_conflict(r1.id)
        assert not success, "普通用户不能审批"
        assert "权限" in msg
        print("  [OK] 通过：普通用户无法审批")

        success, msg, _ = service.reject_reservation(r1.id)
        assert not success, "普通用户不能拒绝"
        assert "权限" in msg
        print("  [OK] 通过：普通用户无法拒绝他人预约")

        success, msg, _ = service.cancel_reservation(r2.id)
        assert not success, "普通用户不能取消别人的预约"
        assert "只能取消自己" in msg
        print("  [OK] 通过：普通用户无法取消他人预约")

        success, msg, _ = service.cancel_reservation(r1.id)
        assert success, "普通用户可以取消自己的预约"
        print("  [OK] 通过：普通用户可以取消自己的预约")


def test_filter_persistence_across_restart():
    """测试筛选条件跨重启持久化"""
    print("\n【测试6】筛选条件跨重启持久化")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        test_filters = {
            'status': ReservationStatus.PENDING.value,
            'department': '研发部',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
        }
        settings = data_manager.get_settings()
        settings['last_reservation_filters'] = test_filters
        data_manager.update_settings(settings)

        new_data_manager = DataManager(data_dir=tmpdir)
        loaded_filters = new_data_manager.get_settings().get('last_reservation_filters', {})

        assert loaded_filters['status'] == test_filters['status']
        assert loaded_filters['department'] == test_filters['department']
        assert loaded_filters['date_from'] == test_filters['date_from']
        assert loaded_filters['date_to'] == test_filters['date_to']
        print("  [OK] 通过：筛选条件持久化和恢复正确")


def test_export_functionality():
    """测试导出功能"""
    print("\n【测试7】导出功能 - CSV和JSON")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1), ReservationStatus.PENDING)
        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2), ReservationStatus.APPROVED)

        filtered = service.get_reservations_filtered(status_filter=ReservationStatus.PENDING.value)
        assert len(filtered) == 1

        success, msg, csv_path = service.export_reservations(filtered, 'csv', tmpdir)
        assert success, f"CSV导出失败: {msg}"
        assert os.path.exists(csv_path)
        assert csv_path.endswith('.csv')
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert "张三" in content
            assert "李四" not in content
        print("  [OK] 通过：CSV导出成功，内容与筛选结果一致")

        success, msg, json_path = service.export_reservations(filtered, 'json', tmpdir)
        assert success, f"JSON导出失败: {msg}"
        assert os.path.exists(json_path)
        assert json_path.endswith('.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]['requester'] == '张三'
        print("  [OK] 通过：JSON导出成功，内容与筛选结果一致")

        history = service.get_operation_histories()[:2]
        assert len(history) == 2
        assert all(h.operation_type == OperationType.RESERVATION_EXPORT for h in history)
        assert any('CSV' in h.details for h in history)
        assert any('JSON' in h.details for h in history)
        print("  [OK] 通过：导出操作已记录到操作历史")


def test_operation_history_logging():
    """测试操作历史记录"""
    print("\n【测试8】操作历史记录")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1))

        service.approve_reservation_with_conflict(r1.id)
        history = service.get_operation_histories()[:1]
        assert history[0].operation_type == OperationType.RESERVATION_APPROVE
        assert r1.id in history[0].details
        print("  [OK] 通过：审批操作已记录")

        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2))
        service.reject_reservation(r2.id, reason="数量不足")
        history = service.get_operation_histories()[:1]
        assert history[0].operation_type == OperationType.RESERVATION_REJECT
        assert "数量不足" in history[0].details
        print("  [OK] 通过：拒绝操作已记录")

        r3, _ = _create_test_reservation(service, item.id, "王五", "财务部", 1, today + timedelta(days=3))
        service.cancel_reservation(r3.id, reason="行程变更")
        history = service.get_operation_histories()[:1]
        assert history[0].operation_type == OperationType.RESERVATION_CANCEL
        assert "行程变更" in history[0].details
        print("  [OK] 通过：取消操作已记录")


def test_normal_user_export_own_only():
    """测试普通用户只能导出自己的预约"""
    print("\n【测试9】普通用户导出权限")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1))
        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2))

        normal_user = User.create_normal_user("zhangsan", "张三")
        service.set_current_user(normal_user)

        filtered = service.get_reservations_filtered()
        assert len(filtered) == 1
        assert filtered[0].requester == "张三"

        success, msg, csv_path = service.export_reservations(filtered, 'csv', tmpdir)
        assert success
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert "张三" in content
            assert "李四" not in content
        print("  [OK] 通过：普通用户只能导出自己的预约")


def test_empty_filter_defaults():
    """测试空筛选条件默认值"""
    print("\n【测试10】空筛选条件默认值")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        default_filters = data_manager.get_settings().get('last_reservation_filters', {})
        assert 'status' in default_filters
        assert 'department' in default_filters
        assert 'date_from' in default_filters
        assert 'date_to' in default_filters
        print("  [OK] 通过：默认筛选条件结构完整")


def test_export_empty_result_no_file():
    """测试空结果不生成导出文件"""
    print("\n【测试11】空结果不生成文件")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        success, msg, filepath = service.export_reservations([], 'csv', tmpdir)
        assert not success, "空结果应该导出失败"
        assert "没有符合条件" in msg
        assert filepath is None, "空结果不应返回文件路径"

        files_before = os.listdir(tmpdir)
        service.export_reservations([], 'csv', tmpdir)
        files_after = os.listdir(tmpdir)
        assert files_before == files_after, "空结果不应生成文件"
        print("  [OK] 通过：空结果不生成导出文件，提示正确")


def test_export_permission_filter_enforced():
    """测试服务层强制权限过滤，即使传入包含他人预约的列表"""
    print("\n【测试12】服务层强制权限过滤")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1))
        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2))
        r3, _ = _create_test_reservation(service, item.id, "张三", "研发部", 3, today + timedelta(days=3))

        all_reservations = [r1, r2, r3]

        normal_user = User.create_normal_user("zhangsan", "张三")
        service.set_current_user(normal_user)

        success, msg, filepath = service.export_reservations(all_reservations, 'csv', tmpdir)
        assert success, f"导出失败: {msg}"

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert "张三" in content
            assert "李四" not in content, "普通用户导出时应过滤掉他人预约"

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            data_lines = [l for l in lines if l.strip() and not l.startswith('ID')]
            assert len(data_lines) == 2, f"应导出2条张三的预约，实际{len(data_lines)}条"
        print("  [OK] 通过：服务层强制权限过滤，普通用户只能导出自己的预约")


def test_export_log_includes_filters():
    """测试导出日志包含筛选条件信息"""
    print("\n【测试13】导出日志包含筛选条件")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1), ReservationStatus.PENDING)

        filters = {
            'status_filter': ReservationStatus.PENDING.value,
            'department_filter': '研发部',
            'date_from': today,
            'date_to': today + timedelta(days=7),
        }

        reservations = service.get_reservations_filtered(**filters)
        success, msg, filepath = service.export_reservations(reservations, 'csv', tmpdir, filters)
        assert success

        history = service.get_operation_histories()[0]
        assert history.operation_type == OperationType.RESERVATION_EXPORT
        assert ReservationStatus.PENDING.value in history.details
        assert "研发部" in history.details
        assert today.isoformat() in history.details
        assert (today + timedelta(days=7)).isoformat() in history.details
        assert "范围: 全部" in history.details
        print("  [OK] 通过：导出日志包含筛选条件和范围信息")


def test_export_format_setting_persistence():
    """测试导出格式设置跨重启持久化"""
    print("\n【测试14】导出格式设置跨重启持久化")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        settings = service.get_settings()
        assert settings.get('last_export_format') == 'csv', "默认导出格式应为csv"
        print("  [OK] 通过：默认导出格式为csv")

        settings['last_export_format'] = 'json'
        settings['last_reservation_export_dir'] = '/custom/path'
        service.update_settings(settings)

        new_data_manager = DataManager(data_dir=tmpdir)
        new_service = InstrumentService(new_data_manager)
        new_settings = new_service.get_settings()

        assert new_settings.get('last_export_format') == 'json'
        assert new_settings.get('last_reservation_export_dir') == '/custom/path'
        print("  [OK] 通过：导出格式和目录跨重启持久化")


def test_export_with_filters_method():
    """测试 export_reservations_with_filters 方法"""
    print("\n【测试15】export_reservations_with_filters 方法")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "张三", "研发部", 2, today + timedelta(days=1), ReservationStatus.PENDING)
        r2, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=2), ReservationStatus.APPROVED)

        success, msg, filepath = service.export_reservations_with_filters(
            status_filter=ReservationStatus.PENDING.value,
            department_filter='研发部',
            format_type='csv',
            export_dir=tmpdir,
        )
        assert success, f"导出失败: {msg}"

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert "张三" in content
            assert "李四" not in content
            assert "研发部" in content

        history = service.get_operation_histories()[0]
        assert ReservationStatus.PENDING.value in history.details
        assert "研发部" in history.details
        print("  [OK] 通过：export_reservations_with_filters 正确应用筛选条件")


def test_normal_user_export_others_empty():
    """测试普通用户尝试导出仅包含他人预约的列表时返回空结果提示"""
    print("\n【测试16】普通用户导出他人预约返回空结果")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        item = service.create_inventory_item(
            name="投影仪", category="办公", model="X1",
            total_quantity=10, unit="台"
        )

        today = date.today()
        r1, _ = _create_test_reservation(service, item.id, "李四", "市场部", 1, today + timedelta(days=1))

        normal_user = User.create_normal_user("zhangsan", "张三")
        service.set_current_user(normal_user)

        success, msg, filepath = service.export_reservations([r1], 'csv', tmpdir)
        assert not success
        assert "您没有可导出的预约记录" in msg
        assert filepath is None
        print("  [OK] 通过：普通用户导出他人预约时返回空结果提示")


def _create_test_reservation(service, item_id, requester, department, quantity, expected_date, status=None):
    """创建测试预约的辅助方法"""
    success, msg, reservation = service.create_reservation(
        item_id, requester, department, quantity, expected_date,
        purpose=f"测试用途-{requester}"
    )
    assert success, f"创建预约失败: {msg}"
    if status:
        reservation.status = status
    service.data_manager.save()
    return reservation, success


def run_all_tests():
    print("=" * 70)
    print("预约管理 - 服务层测试套件")
    print("=" * 70)

    all_passed = True
    tests = [
        test_filtered_reservations,
        test_department_list,
        test_conflict_detection,
        test_approve_with_conflict_reason,
        test_permission_restrictions,
        test_filter_persistence_across_restart,
        test_export_functionality,
        test_operation_history_logging,
        test_normal_user_export_own_only,
        test_empty_filter_defaults,
        test_export_empty_result_no_file,
        test_export_permission_filter_enforced,
        test_export_log_includes_filters,
        test_export_format_setting_persistence,
        test_export_with_filters_method,
        test_normal_user_export_others_empty,
    ]

    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"  [FAIL] 失败: {e}")
            all_passed = False
        except Exception as e:
            print(f"  [ERROR] 异常: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("[OK] 所有服务层测试通过！")
    else:
        print("[FAIL] 部分测试失败！")
    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
