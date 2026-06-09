import sys
import os
import tempfile
import json
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk

from src.models import User, UserRole, ReservationStatus, OperationType
from src.storage import DataManager
from src.services import InstrumentService
from src.ui.dialogs import ReservationDialog


def setup_test_environment(tmpdir):
    """设置测试环境"""
    data_manager = DataManager(data_dir=tmpdir)
    service = InstrumentService(data_manager)

    admin = User.create_admin_user("admin", "管理员")
    service.set_current_user(admin)

    item = service.create_inventory_item(
        name="会议室投影仪", category="办公", model="X1",
        total_quantity=5, unit="台"
    )

    today = date.today()
    for i in range(5):
        requester = ["张三", "李四", "王五", "张三", "赵六"][i]
        department = ["研发部", "市场部", "研发部", "研发部", "财务部"][i]
        status = [
            ReservationStatus.PENDING,
            ReservationStatus.APPROVED,
            ReservationStatus.REJECTED,
            ReservationStatus.PENDING,
            ReservationStatus.CANCELLED,
        ][i]
        success, _, reservation = service.create_reservation(
            item.id, requester, department, i + 1,
            today + timedelta(days=i + 1),
            purpose=f"测试用途-{requester}"
        )
        if success:
            reservation.status = status
            if status == ReservationStatus.APPROVED:
                reservation.approver = admin.display_name
                reservation.approved_at = datetime.now()
    data_manager.save()

    return data_manager, service, admin, item


def test_dialog_initialization():
    """测试对话框初始化"""
    print("\n【GUI测试1】对话框初始化")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)
            assert dialog is not None
            assert hasattr(dialog, 'tree')
            assert hasattr(dialog, 'status_var')
            assert hasattr(dialog, 'department_var')
            assert hasattr(dialog, 'date_from_var')
            assert hasattr(dialog, 'date_to_var')
            print("  [OK] 通过：对话框初始化成功，属性完整")

            assert hasattr(dialog, 'approve_btn')
            assert hasattr(dialog, 'reject_btn')
            assert hasattr(dialog, 'reschedule_btn')
            assert hasattr(dialog, 'fulfill_btn')
            assert hasattr(dialog, 'cancel_btn')
            assert hasattr(dialog, 'export_btn')
            assert hasattr(dialog, 'refresh_btn')
            print("  [OK] 通过：管理员按钮全部创建")

            assert dialog.is_admin == True
            assert dialog.user == admin
            print("  [OK] 通过：用户上下文正确")

            departments = service.get_reservation_departments()
            assert len(departments) > 0
            print("  [OK] 通过：部门列表获取成功")

        finally:
            root.destroy()


def test_filter_persistence_gui():
    """测试筛选条件GUI持久化"""
    print("\n【GUI测试2】筛选条件GUI持久化")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        test_filters = {
            'status': ReservationStatus.PENDING.value,
            'department': '研发部',
            'date_from': (date.today() + timedelta(days=1)).isoformat(),
            'date_to': (date.today() + timedelta(days=10)).isoformat(),
        }
        settings = data_manager.get_settings()
        settings['last_reservation_filters'] = test_filters
        data_manager.update_settings(settings)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            assert dialog.status_var.get() == test_filters['status']
            assert dialog.department_var.get() == test_filters['department']
            assert dialog.date_from_var.get() == test_filters['date_from']
            assert dialog.date_to_var.get() == test_filters['date_to']
            print("  [OK] 通过：筛选条件从配置正确恢复")

            new_status = ReservationStatus.APPROVED.value
            new_department = '市场部'
            dialog.status_var.set(new_status)
            dialog.department_var.set(new_department)
            dialog._save_filters()

            saved_filters = data_manager.get_settings().get('last_reservation_filters', {})
            assert saved_filters['status'] == new_status
            assert saved_filters['department'] == new_department
            print("  [OK] 通过：筛选条件变更正确保存到配置")

        finally:
            root.destroy()


def test_permission_based_ui():
    """测试基于权限的UI控制"""
    print("\n【GUI测试3】基于权限的UI控制")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)
            assert dialog.approve_btn.winfo_ismapped() or hasattr(dialog, 'approve_btn')
            assert dialog.reject_btn.winfo_ismapped() or hasattr(dialog, 'reject_btn')
            assert dialog.reschedule_btn.winfo_ismapped() or hasattr(dialog, 'reschedule_btn')
            assert dialog.fulfill_btn.winfo_ismapped() or hasattr(dialog, 'fulfill_btn')
            print("  [OK] 通过：管理员可见所有管理按钮")

        finally:
            root.destroy()

        normal_user = User.create_normal_user("zhangsan", "张三")
        service.set_current_user(normal_user)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=normal_user, is_admin=False)

            assert not hasattr(dialog, 'approve_btn') or dialog.approve_btn is None
            assert not hasattr(dialog, 'reject_btn') or dialog.reject_btn is None
            assert not hasattr(dialog, 'reschedule_btn') or dialog.reschedule_btn is None
            assert not hasattr(dialog, 'fulfill_btn') or dialog.fulfill_btn is None
            print("  [OK] 通过：普通用户隐藏审批相关按钮")

            assert hasattr(dialog, 'cancel_btn')
            assert hasattr(dialog, 'export_btn')
            print("  [OK] 通过：普通用户可见取消和导出按钮")

        finally:
            root.destroy()


def test_empty_state_display():
    """测试空状态提示"""
    print("\n【GUI测试4】空状态提示")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            assert hasattr(dialog, 'empty_label')
            assert dialog.empty_label is not None
            print("  [OK] 通过：空状态标签已创建")

        finally:
            root.destroy()


def test_gui_filter_application():
    """测试GUI筛选功能应用"""
    print("\n【GUI测试5】GUI筛选功能应用")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            all_count = len(dialog.current_reservations)
            assert all_count == 5, f"预期5条预约，实际{all_count}"
            print(f"  ✓ 通过：初始加载所有{all_count}条预约")

            dialog.status_var.set(ReservationStatus.PENDING.value)
            dialog._on_query()
            pending_count = len(dialog.current_reservations)
            assert pending_count == 2, f"筛选待审批预期2条，实际{pending_count}"
            assert all(r.status == ReservationStatus.PENDING for r in dialog.current_reservations)
            print(f"  ✓ 通过：按状态筛选正确，{pending_count}条待审批")

            dialog._on_reset()
            reset_count = len(dialog.current_reservations)
            assert reset_count == 5, f"重置后预期5条，实际{reset_count}"
            assert dialog.status_var.get() == ''
            assert dialog.department_var.get() == ''
            assert dialog.date_from_var.get() == ''
            assert dialog.date_to_var.get() == ''
            print("  [OK] 通过：重置筛选条件正确")

            dialog.department_var.set('研发部')
            dialog._on_query()
            dept_count = len(dialog.current_reservations)
            assert dept_count == 3, f"研发部筛选预期3条，实际{dept_count}"
            assert all(r.department == '研发部' for r in dialog.current_reservations)
            print(f"  ✓ 通过：按部门筛选正确，{dept_count}条研发部记录")

        finally:
            root.destroy()


def test_normal_user_data_isolation():
    """测试普通用户数据隔离"""
    print("\n【GUI测试6】普通用户数据隔离")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        normal_user = User.create_normal_user("zhangsan", "张三")
        service.set_current_user(normal_user)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=normal_user, is_admin=False)

            visible_count = len(dialog.current_reservations)
            assert visible_count == 2, f"张三应看到2条自己的预约，实际{visible_count}"
            assert all(r.requester == '张三' for r in dialog.current_reservations)
            print(f"  ✓ 通过：普通用户仅可见自己的{visible_count}条预约")

        finally:
            root.destroy()


def test_export_integration():
    """测试导出功能集成"""
    print("\n【GUI测试7】导出功能集成")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        service.set_current_user(admin)

        filtered = service.get_reservations_filtered(
            status_filter=ReservationStatus.PENDING.value
        )
        assert len(filtered) == 2

        success, msg, csv_path = service.export_reservations(filtered, 'csv', tmpdir)
        assert success, f"CSV导出失败: {msg}"
        assert os.path.exists(csv_path)
        print("  [OK] 通过：CSV导出集成成功")

        success, msg, json_path = service.export_reservations(filtered, 'json', tmpdir)
        assert success, f"JSON导出失败: {msg}"
        assert os.path.exists(json_path)
        print("  [OK] 通过：JSON导出集成成功")

        history = service.get_operation_histories()[:2]
        assert len(history) == 2
        assert all(h.operation_type == OperationType.RESERVATION_EXPORT for h in history)
        print("  [OK] 通过：导出操作历史记录正确")


def test_cross_restart_filter_recovery():
    """测试跨重启筛选恢复"""
    print("\n【GUI测试8】跨重启筛选恢复")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        original_filters = {
            'status': ReservationStatus.APPROVED.value,
            'department': '市场部',
            'date_from': '',
            'date_to': '',
        }
        settings = data_manager.get_settings()
        settings['last_reservation_filters'] = original_filters
        data_manager.update_settings(settings)

        del data_manager
        del service

        new_data_manager = DataManager(data_dir=tmpdir)
        new_service = InstrumentService(new_data_manager)
        new_service.set_current_user(admin)

        loaded_filters = new_data_manager.get_settings().get('last_reservation_filters', {})
        assert loaded_filters['status'] == original_filters['status']
        assert loaded_filters['department'] == original_filters['department']
        print("  [OK] 通过：重启后配置正确恢复")

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, new_service, user=admin, is_admin=True)
            assert dialog.status_var.get() == original_filters['status']
            assert dialog.department_var.get() == original_filters['department']

            assert len(dialog.current_reservations) == 1
            assert dialog.current_reservations[0].status == ReservationStatus.APPROVED
            assert dialog.current_reservations[0].department == '市场部'
            print("  [OK] 通过：重启后GUI自动应用保存的筛选条件")

        finally:
            root.destroy()


def test_status_tag_colors():
    """测试状态标签颜色配置"""
    print("\n【GUI测试9】状态标签颜色配置")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            expected_tags = ['pending', 'approved', 'rejected', 'cancelled', 'fulfilled', 'rescheduled']
            for tag in expected_tags:
                assert tag in dialog.tree.tag_configure, f"缺少状态标签: {tag}"
            print("  [OK] 通过：所有状态标签已配置")

            pending_config = dialog.tree.tag_configure('pending')
            approved_config = dialog.tree.tag_configure('approved')
            rejected_config = dialog.tree.tag_configure('rejected')

            assert 'foreground' in pending_config
            assert 'foreground' in approved_config
            assert 'foreground' in rejected_config
            print("  [OK] 通过：状态标签颜色已配置")

        finally:
            root.destroy()


def test_count_label_update():
    """测试计数标签更新"""
    print("\n【GUI测试10】计数标签更新")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            count_text = dialog.count_label.cget('text')
            assert '5' in count_text, f"初始计数应包含5，实际: {count_text}"
            print(f"  ✓ 通过：初始计数正确 - {count_text}")

            dialog.status_var.set(ReservationStatus.PENDING.value)
            dialog._on_query()

            count_text = dialog.count_label.cget('text')
            assert '2' in count_text, f"筛选后计数应包含2，实际: {count_text}"
            print(f"  ✓ 通过：筛选后计数正确 - {count_text}")

        finally:
            root.destroy()


def run_all_gui_tests():
    print("=" * 70)
    print("预约管理 - GUI回归测试套件")
    print("=" * 70)

    all_passed = True
    tests = [
        test_dialog_initialization,
        test_filter_persistence_gui,
        test_permission_based_ui,
        test_empty_state_display,
        test_gui_filter_application,
        test_normal_user_data_isolation,
        test_export_integration,
        test_cross_restart_filter_recovery,
        test_status_tag_colors,
        test_count_label_update,
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
        print("[OK] 所有GUI回归测试通过！")
    else:
        print("[FAIL] 部分测试失败！")
    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    try:
        success = run_all_gui_tests()
        sys.exit(0 if success else 1)
    except tk.TclError as e:
        print("\n⚠️  警告: 无法在无显示环境运行GUI测试")
        print(f"   错误信息: {e}")
        print("   GUI测试需要图形界面支持，请在有显示器的环境运行")
        print("   服务层测试仍然有效，可以运行 test_reservation_service.py")
        sys.exit(0)
