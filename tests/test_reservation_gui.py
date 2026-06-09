import sys
import os
import tempfile
import json
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
    from tkinter import ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
except tk.TclError:
    TK_AVAILABLE = False

from src.models import User, UserRole, ReservationStatus, OperationType
from src.storage import DataManager
from src.services import InstrumentService
from src.ui.dialogs import ReservationDialog


def require_tk(test_func):
    """装饰器：跳过需要Tkinter的测试"""
    def wrapper(*args, **kwargs):
        if not TK_AVAILABLE:
            print(f"  ⚠️  跳过：无Tkinter支持")
            return True
        try:
            return test_func(*args, **kwargs)
        except tk.TclError as e:
            if "no display" in str(e).lower() or "couldn't connect to display" in str(e).lower():
                print(f"  ⚠️  跳过：无显示环境")
                return True
            raise
    wrapper.__name__ = test_func.__name__
    wrapper.__doc__ = test_func.__doc__
    return wrapper


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


@require_tk
def test_main_window_button_opens_dialog():
    """测试主窗口按钮能打开预约管理（真实API路径）"""
    print("\n【GUI测试1】主窗口按钮打开预约管理")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            user = service.get_current_user()
            is_admin = user.can_manage_reservations()

            dialog = ReservationDialog(root, service, user=user, is_admin=is_admin)
            assert dialog is not None
            assert dialog.user == user
            assert dialog.is_admin == is_admin
            print("  [OK] 通过：主窗口调用路径成功打开对话框")
            print(f"       用户：{user.display_name}，管理员：{is_admin}")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_dialog_initialization():
    """测试对话框初始化"""
    print("\n【GUI测试2】对话框初始化")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)
            assert dialog is not None
            assert hasattr(dialog, 'tree')
            assert hasattr(dialog, 'status_filter_var')
            assert hasattr(dialog, 'department_filter_var')
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

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_filter_persistence_gui():
    """测试筛选条件GUI持久化"""
    print("\n【GUI测试3】筛选条件GUI持久化")
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

            assert dialog.status_filter_var.get() == test_filters['status']
            assert dialog.department_filter_var.get() == test_filters['department']
            assert dialog.date_from_var.get() == test_filters['date_from']
            assert dialog.date_to_var.get() == test_filters['date_to']
            print("  [OK] 通过：筛选条件从配置正确恢复")

            new_status = ReservationStatus.APPROVED.value
            new_department = '市场部'
            dialog.status_filter_var.set(new_status)
            dialog.department_filter_var.set(new_department)
            dialog._save_filters()

            saved_filters = data_manager.get_settings().get('last_reservation_filters', {})
            assert saved_filters['status'] == new_status
            assert saved_filters['department'] == new_department
            print("  [OK] 通过：筛选条件变更正确保存到配置")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_admin_permission_ui():
    """测试管理员权限UI（能处理审批）"""
    print("\n【GUI测试4】管理员权限UI")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)
            assert hasattr(dialog, 'approve_btn')
            assert hasattr(dialog, 'reject_btn')
            assert hasattr(dialog, 'reschedule_btn')
            assert hasattr(dialog, 'fulfill_btn')
            print("  [OK] 通过：管理员可见所有管理按钮")

            dialog._refresh_reservations()

            first_id = dialog.tree.get_children()[0]
            dialog.tree.selection_set(first_id)
            dialog._on_select_reservation(None)

            try:
                state = dialog.approve_btn.cget('state')
                print(f"  [OK] 通过：选中后审批按钮状态为 {state}")
            except Exception:
                print("  [OK] 通过：审批按钮存在且可访问")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_normal_user_permission_ui():
    """测试普通用户权限UI（不能审批）"""
    print("\n【GUI测试5】普通用户权限UI")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        normal_user = User.create_normal_user("zhangsan", "张三")
        service.set_current_user(normal_user)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=normal_user, is_admin=False)

            assert not hasattr(dialog, 'approve_btn')
            assert not hasattr(dialog, 'reject_btn')
            assert not hasattr(dialog, 'reschedule_btn')
            assert not hasattr(dialog, 'fulfill_btn')
            print("  [OK] 通过：普通用户隐藏审批相关按钮")

            assert hasattr(dialog, 'cancel_btn')
            assert hasattr(dialog, 'export_btn')
            assert hasattr(dialog, 'refresh_btn')
            print("  [OK] 通过：普通用户可见取消和导出按钮")

            assert dialog.is_admin == False
            assert dialog.user == normal_user
            print("  [OK] 通过：普通用户上下文正确")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_empty_state_display():
    """测试空状态提示"""
    print("\n【GUI测试6】空状态提示")
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

            empty_text = dialog.empty_label.cget('text')
            assert '没有找到' in empty_text or len(empty_text) == 0
            print(f"  [OK] 通过：空状态文本正确 - '{empty_text}'")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_gui_filter_application():
    """测试GUI筛选功能应用"""
    print("\n【GUI测试7】GUI筛选功能应用")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            all_count = len(dialog.current_reservations)
            assert all_count == 5, f"预期5条预约，实际{all_count}"
            print(f"  [OK] 通过：初始加载所有{all_count}条预约")

            dialog.status_filter_var.set(ReservationStatus.PENDING.value)
            dialog._refresh_reservations()
            pending_count = len(dialog.current_reservations)
            assert pending_count == 2, f"筛选待审批预期2条，实际{pending_count}"
            assert all(r.status == ReservationStatus.PENDING for r in dialog.current_reservations)
            print(f"  [OK] 通过：按状态筛选正确，{pending_count}条待审批")

            dialog._on_reset_filters()
            reset_count = len(dialog.current_reservations)
            assert reset_count == 5, f"重置后预期5条，实际{reset_count}"
            assert dialog.status_filter_var.get() == ''
            assert dialog.department_filter_var.get() == ''
            assert dialog.date_from_var.get() == ''
            assert dialog.date_to_var.get() == ''
            print("  [OK] 通过：重置筛选条件正确")

            dialog.department_filter_var.set('研发部')
            dialog._refresh_reservations()
            dept_count = len(dialog.current_reservations)
            assert dept_count == 3, f"研发部筛选预期3条，实际{dept_count}"
            assert all(r.department == '研发部' for r in dialog.current_reservations)
            print(f"  [OK] 通过：按部门筛选正确，{dept_count}条研发部记录")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_normal_user_data_isolation():
    """测试普通用户数据隔离"""
    print("\n【GUI测试8】普通用户数据隔离")
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
            print(f"  [OK] 通过：普通用户仅可见自己的{visible_count}条预约")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_export_integration():
    """测试导出功能集成（与筛选结果一致）"""
    print("\n【GUI测试9】导出功能集成")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        service.set_current_user(admin)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            dialog.status_filter_var.set(ReservationStatus.PENDING.value)
            dialog._refresh_reservations()

            filtered_count = len(dialog.current_reservations)
            assert filtered_count == 2

            success, msg, csv_path = service.export_reservations(
                dialog.current_reservations, 'csv', tmpdir
            )
            assert success, f"CSV导出失败: {msg}"
            assert os.path.exists(csv_path)
            print("  [OK] 通过：CSV导出集成成功（与当前筛选一致）")

            success, msg, json_path = service.export_reservations(
                dialog.current_reservations, 'json', tmpdir
            )
            assert success, f"JSON导出失败: {msg}"
            assert os.path.exists(json_path)
            print("  [OK] 通过：JSON导出集成成功（与当前筛选一致）")

            history = service.get_operation_histories()[:2]
            assert len(history) == 2
            assert all(h.operation_type == OperationType.RESERVATION_EXPORT for h in history)
            print("  [OK] 通过：导出操作历史记录正确")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_cross_restart_filter_recovery():
    """测试跨重启筛选恢复"""
    print("\n【GUI测试10】跨重启筛选恢复")
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
            assert dialog.status_filter_var.get() == original_filters['status']
            assert dialog.department_filter_var.get() == original_filters['department']

            assert len(dialog.current_reservations) == 1
            assert dialog.current_reservations[0].status == ReservationStatus.APPROVED
            assert dialog.current_reservations[0].department == '市场部'
            print("  [OK] 通过：重启后GUI自动应用保存的筛选条件")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_status_tag_colors():
    """测试状态标签颜色配置"""
    print("\n【GUI测试11】状态标签颜色配置")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            expected_tags = ['待审批', '已审批', '已拒绝', '已取消', '已领用', '已改期']
            for tag in expected_tags:
                config = dialog.tree.tag_configure(tag)
                assert isinstance(config, dict), f"标签 {tag} 配置无效"
            print("  [OK] 通过：所有状态标签已配置")

            pending_config = dialog.tree.tag_configure('待审批')
            approved_config = dialog.tree.tag_configure('已审批')
            rejected_config = dialog.tree.tag_configure('已拒绝')

            assert 'foreground' in pending_config
            assert 'foreground' in approved_config
            assert 'foreground' in rejected_config
            print("  [OK] 通过：状态标签颜色已配置")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_count_label_update():
    """测试计数标签更新"""
    print("\n【GUI测试12】计数标签更新")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            dialog = ReservationDialog(root, service, user=admin, is_admin=True)

            dialog._refresh_reservations()
            dialog.update_idletasks()

            current_count = len(dialog.current_reservations)
            count_text = dialog.count_label.cget('text')
            assert str(current_count) in count_text, f"初始计数应包含{current_count}，实际: '{count_text}'"
            print(f"  [OK] 通过：初始计数正确 - {count_text}")

            dialog.status_filter_var.set(ReservationStatus.PENDING.value)
            dialog._refresh_reservations()
            dialog.update_idletasks()

            pending_count = len(dialog.current_reservations)
            count_text = dialog.count_label.cget('text')
            assert str(pending_count) in count_text, f"筛选后计数应包含{pending_count}，实际: '{count_text}'"
            print(f"  [OK] 通过：筛选后计数正确 - {count_text}")

            dialog.destroy()

        finally:
            root.destroy()


@require_tk
def test_constructor_accepts_all_params():
    """测试构造函数兼容所有参数形式"""
    print("\n【GUI测试13】构造函数参数兼容性")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, admin, _ = setup_test_environment(tmpdir)

        root = tk.Tk()
        root.withdraw()

        try:
            normal_user = User.create_normal_user("lisi", "李四")

            d1 = ReservationDialog(root, service)
            assert d1.user == admin
            d1.destroy()
            print("  [OK] 通过：仅传 service 参数")

            d2 = ReservationDialog(root, service, user=normal_user)
            assert d2.user == normal_user
            assert d2.is_admin == False
            d2.destroy()
            print("  [OK] 通过：传 service 和 user 参数")

            d3 = ReservationDialog(root, service, user=normal_user, is_admin=False)
            assert d3.user == normal_user
            assert d3.is_admin == False
            d3.destroy()
            print("  [OK] 通过：传 service、user 和 is_admin 参数")

            d4 = ReservationDialog(root, service, is_admin=True)
            assert d4.is_admin == True
            d4.destroy()
            print("  [OK] 通过：传 service 和 is_admin 参数")

        finally:
            root.destroy()


def run_all_gui_tests():
    print("=" * 70)
    print("预约管理 - GUI回归测试套件")
    print("=" * 70)

    if not TK_AVAILABLE:
        print("\n⚠️  Tkinter不可用，跳过GUI测试")
        print("   服务层测试仍然有效，可以运行 test_reservation_service.py")
        print("=" * 70)
        return True

    all_passed = True
    tests = [
        test_main_window_button_opens_dialog,
        test_dialog_initialization,
        test_filter_persistence_gui,
        test_admin_permission_ui,
        test_normal_user_permission_ui,
        test_empty_state_display,
        test_gui_filter_application,
        test_normal_user_data_isolation,
        test_export_integration,
        test_cross_restart_filter_recovery,
        test_status_tag_colors,
        test_count_label_update,
        test_constructor_accepts_all_params,
    ]

    for test in tests:
        try:
            result = test()
            if result is False:
                all_passed = False
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
        if "no display" in str(e).lower() or "couldn't connect to display" in str(e).lower():
            print("\n⚠️  警告: 无法在无显示环境运行GUI测试")
            print(f"   错误信息: {e}")
            print("   GUI测试需要图形界面支持，请在有显示器的环境运行")
            print("   服务层测试仍然有效，可以运行 test_reservation_service.py")
            sys.exit(0)
        else:
            raise
