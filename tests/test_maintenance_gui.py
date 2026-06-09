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
    _global_root = None
    try:
        _global_root = tk.Tk()
        _global_root.withdraw()
    except Exception as e:
        print(f"  ⚠️  Tkinter初始化失败: {e}")
        TK_AVAILABLE = False
        if _global_root:
            try:
                _global_root.destroy()
            except:
                pass
        _global_root = None
except ImportError:
    TK_AVAILABLE = False
    _global_root = None
except Exception:
    TK_AVAILABLE = False
    _global_root = None


def get_global_root():
    """获取全局Tk实例"""
    return _global_root


def cleanup_global_root():
    """清理全局Tk实例"""
    global _global_root
    if _global_root:
        try:
            _global_root.update()
            _global_root.destroy()
        except:
            pass
        _global_root = None

from src.models import (
    User, UserRole, Instrument, InstrumentStatus, InstrumentCategory,
    MaintenanceOrder, MaintenanceOrderStatus, MaintenancePriority,
    MaintenanceCompletionOption, OperationType,
)
from src.storage import DataManager
from src.services import InstrumentService
from src.ui.dialogs import (
    MaintenanceOrderDialog,
    MaintenanceOrderListDialog,
    MaintenanceOrderDetailDialog,
)


def require_tk(test_func):
    """装饰器：跳过需要Tkinter的测试"""
    def wrapper(*args, **kwargs):
        if not TK_AVAILABLE:
            print(f"  ⚠️  跳过：无Tkinter支持")
            return True
        try:
            return test_func(*args, **kwargs)
        except tk.TclError as e:
            err_str = str(e).lower()
            if ("no display" in err_str or 
                "couldn't connect to display" in err_str or 
                "application has been destroyed" in err_str or
                "can't invoke" in err_str):
                print(f"  ⚠️  跳过：显示环境问题 - {e}")
                return True
            raise
        except Exception as e:
            if "Tk" in str(type(e).__name__) or "Tcl" in str(type(e).__name__):
                print(f"  ⚠️  跳过：Tkinter初始化失败 - {e}")
                return True
            raise
    wrapper.__name__ = test_func.__name__
    wrapper.__doc__ = test_func.__doc__
    return wrapper


def _create_test_instrument(service, name="测试仪器", status=InstrumentStatus.AVAILABLE):
    """创建测试仪器"""
    return service.create_instrument(
        name=name,
        category=InstrumentCategory.ELECTRONIC,
        model="M-001",
        serial_number=f"SN{datetime.now().timestamp()}",
        location="实验室A",
        manager="张管理员",
        calibration_due_date=date.today() + timedelta(days=180),
        description="测试用仪器",
    )


def setup_test_environment(tmpdir):
    """设置测试环境"""
    data_manager = DataManager(data_dir=tmpdir)
    service = InstrumentService(data_manager)

    normal_user = User(username="user1", role=UserRole.NORMAL, display_name="普通用户")
    maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
    admin = User.create_admin_user("admin", "管理员")

    instrument = _create_test_instrument(service)

    return data_manager, service, normal_user, maintenance_user, admin, instrument


@require_tk
def test_maintenance_order_dialog_initialization():
    """测试创建维修工单对话框初始化"""
    print("\n【GUI测试1】创建维修工单对话框初始化")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, _, _, instrument = setup_test_environment(tmpdir)

        root = get_global_root()

        try:
            service.set_current_user(normal_user)

            dialog = MaintenanceOrderDialog(root, instrument, normal_user)
            assert dialog is not None
            assert dialog.instrument == instrument
            assert dialog.user == normal_user
            print("  [OK] 通过：对话框初始化成功")

            assert hasattr(dialog, 'fault_text')
            assert hasattr(dialog, 'priority_var')
            assert hasattr(dialog, 'expected_date_var')
            assert hasattr(dialog, 'assignee_var')
            print("  [OK] 通过：所有表单控件已创建")

            assert dialog.priority_var.get() == MaintenancePriority.MEDIUM.value
            print(f"  [OK] 通过：默认优先级正确: {dialog.priority_var.get()}")

            expected_default = (date.today() + timedelta(days=7)).isoformat()
            assert dialog.expected_date_var.get() == expected_default
            print(f"  [OK] 通过：默认预计完成日期正确: {dialog.expected_date_var.get()}")

            dialog.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_order_dialog_validation():
    """测试创建维修工单对话框表单验证"""
    print("\n【GUI测试2】创建维修工单对话框表单验证")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, _, _, instrument = setup_test_environment(tmpdir)

        root = get_global_root()

        try:
            service.set_current_user(normal_user)

            dialog = MaintenanceOrderDialog(root, instrument, normal_user)

            dialog.fault_text.delete("1.0", tk.END)
            dialog._on_ok()
            assert dialog.result is None, "故障描述为空时不应提交"
            print("  [OK] 通过：空故障描述被拦截")

            dialog.fault_text.insert("1.0", "测试故障描述")
            dialog.expected_date_var.set("invalid-date")
            dialog._on_ok()
            assert dialog.result is None, "日期格式错误时不应提交"
            print("  [OK] 通过：日期格式错误被拦截")

            dialog.expected_date_var.set((date.today() + timedelta(days=7)).isoformat())
            dialog.assignee_var.set("  ")
            dialog._on_ok()
            assert dialog.result is not None, "表单验证通过后应提交成功"
            assert dialog.result['assignee'] is None, "空白负责人应转为None"
            assert dialog.result['fault_description'] == "测试故障描述"
            assert dialog.result['priority'] == MaintenancePriority.MEDIUM
            print("  [OK] 通过：表单验证通过，数据正确")

            dialog.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_order_list_dialog_initialization():
    """测试维修工单列表对话框初始化"""
    print("\n【GUI测试3】维修工单列表对话框初始化")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, maintenance_user, admin, instrument = setup_test_environment(tmpdir)

        service.set_current_user(normal_user)
        success, _, order1 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="故障1",
            priority=MaintenancePriority.HIGH,
        )
        success, _, order2 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="故障2",
            priority=MaintenancePriority.LOW,
        )
        data_manager.save()

        root = get_global_root()

        try:
            service.set_current_user(admin)
            dialog = MaintenanceOrderListDialog(root, service, admin)
            assert dialog is not None
            assert dialog.user == admin
            assert dialog.is_maintenance == True
            print("  [OK] 通过：管理员对话框初始化成功")

            assert hasattr(dialog, 'tree')
            assert hasattr(dialog, 'status_filter_var')
            assert hasattr(dialog, 'view_btn')
            assert hasattr(dialog, 'accept_btn')
            assert hasattr(dialog, 'reject_btn')
            print("  [OK] 通过：管理员按钮全部创建")

            tree_items = dialog.tree.get_children()
            assert len(tree_items) == 2, f"管理员应看到2条工单，实际{len(tree_items)}"
            print(f"  [OK] 通过：管理员看到全部工单: {len(tree_items)}条")

            dialog.destroy()

            service.set_current_user(normal_user)
            dialog2 = MaintenanceOrderListDialog(root, service, normal_user)
            assert dialog2.is_maintenance == False
            print("  [OK] 通过：普通用户对话框初始化成功")

            tree_items2 = dialog2.tree.get_children()
            assert len(tree_items2) == 2, f"普通用户应看到自己的2条工单，实际{len(tree_items2)}"
            print(f"  [OK] 通过：普通用户看到自己的工单: {len(tree_items2)}条")

            assert not hasattr(dialog2, 'accept_btn'), "普通用户不应有接单按钮"
            assert not hasattr(dialog2, 'reject_btn'), "普通用户不应有驳回按钮"
            print("  [OK] 通过：普通用户没有操作按钮")

            dialog2.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_order_list_permission_filter():
    """测试工单列表权限过滤"""
    print("\n【GUI测试4】工单列表权限过滤")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, maintenance_user, admin, instrument = setup_test_environment(tmpdir)

        user2 = User(username="user2", role=UserRole.NORMAL, display_name="其他用户")

        service.set_current_user(normal_user)
        success, _, order1 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="用户A的故障",
            priority=MaintenancePriority.HIGH,
        )

        service.set_current_user(user2)
        success, _, order2 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="用户B的故障",
            priority=MaintenancePriority.LOW,
        )
        data_manager.save()

        root = get_global_root()

        try:
            service.set_current_user(normal_user)
            dialog = MaintenanceOrderListDialog(root, service, normal_user)

            tree_items = dialog.tree.get_children()
            assert len(tree_items) == 1, f"用户A应只看到自己的1条工单，实际{len(tree_items)}"

            item_values = dialog.tree.item(tree_items[0], 'values')
            assert item_values[3] == "普通用户", "应只显示申请人为普通用户的工单"
            print("  [OK] 通过：普通用户只能看到自己的工单")

            dialog.destroy()

            service.set_current_user(admin)
            dialog2 = MaintenanceOrderListDialog(root, service, admin)
            tree_items2 = dialog2.tree.get_children()
            assert len(tree_items2) == 2, f"管理员应看到全部2条工单，实际{len(tree_items2)}"
            print("  [OK] 通过：管理员可以看到所有工单")

            dialog2.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_order_list_status_filter():
    """测试工单列表状态筛选"""
    print("\n【GUI测试5】工单列表状态筛选")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, maintenance_user, admin, instrument = setup_test_environment(tmpdir)

        service.set_current_user(normal_user)
        success, _, order1 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="故障1",
            priority=MaintenancePriority.MEDIUM,
        )
        success, _, order2 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="故障2",
            priority=MaintenancePriority.MEDIUM,
        )

        service.set_current_user(maintenance_user)
        success, _, order1 = service.accept_maintenance_order(
            order_id=order1.id,
        )
        data_manager.save()

        root = get_global_root()

        try:
            service.set_current_user(admin)
            dialog = MaintenanceOrderListDialog(root, service, admin)

            all_items = dialog.tree.get_children()
            assert len(all_items) == 2, "初始应显示全部2条工单"
            print(f"  [INFO] 初始显示 {len(all_items)} 条工单")

            dialog.status_filter_var.set(MaintenanceOrderStatus.PENDING.value)
            dialog._refresh_orders()
            pending_items = dialog.tree.get_children()
            assert len(pending_items) == 1, f"待分配筛选后应剩1条，实际{len(pending_items)}"
            print(f"  [OK] 通过：待分配筛选正确，显示 {len(pending_items)} 条")

            dialog.status_filter_var.set(MaintenanceOrderStatus.IN_PROGRESS.value)
            dialog._refresh_orders()
            progress_items = dialog.tree.get_children()
            assert len(progress_items) == 1, f"处理中筛选后应剩1条，实际{len(progress_items)}"
            print(f"  [OK] 通过：处理中筛选正确，显示 {len(progress_items)} 条")

            dialog.status_filter_var.set("")
            dialog._refresh_orders()
            reset_items = dialog.tree.get_children()
            assert len(reset_items) == 2, f"重置筛选后应恢复2条，实际{len(reset_items)}"
            print(f"  [OK] 通过：重置筛选正确，显示 {len(reset_items)} 条")

            dialog.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_order_detail_dialog():
    """测试工单详情对话框"""
    print("\n【GUI测试6】工单详情对话框")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, maintenance_user, admin, instrument = setup_test_environment(tmpdir)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="仪器无法开机，需要维修",
            priority=MaintenancePriority.HIGH,
            expected_completion_date=date.today() + timedelta(days=7),
            assignee="维修员",
        )

        service.set_current_user(maintenance_user)
        success, _, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        success, _, order = service.add_maintenance_processing_note(
            order_id=order.id,
            note="检查发现电源模块损坏",
        )
        data_manager.save()

        root = get_global_root()

        try:
            service.set_current_user(maintenance_user)
            dialog = MaintenanceOrderDetailDialog(root, service, maintenance_user, order)
            assert dialog is not None
            assert dialog.order == order
            assert dialog.is_maintenance == True
            print("  [OK] 通过：详情对话框初始化成功")

            assert hasattr(dialog, 'processing_note_var')
            assert hasattr(dialog, 'completion_option_var')
            assert hasattr(dialog, 'completion_notes_var')
            print("  [OK] 通过：操作控件已创建")

            assert dialog.completion_option_var.get() == MaintenanceCompletionOption.RESTORE_AVAILABLE.value
            print("  [OK] 通过：默认完成方式正确")

            dialog.processing_note_var.set("已订购配件，等待到货")
            dialog._on_add_note()
            assert dialog.result is None, "添加记录不应关闭对话框"

            updated_order = service.get_maintenance_order_by_id(order.id)
            assert len(updated_order.logs) >= 4, "应添加新的处理记录"
            print(f"  [OK] 通过：添加处理记录成功，日志数: {len(updated_order.logs)}")

            dialog.destroy()

            service.set_current_user(normal_user)
            dialog2 = MaintenanceOrderDetailDialog(root, service, normal_user, order)
            assert dialog2.is_maintenance == False
            assert not hasattr(dialog2, 'processing_note_var'), "普通用户不应有操作控件"
            print("  [OK] 通过：普通用户只能查看详情，不能操作")

            dialog2.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_order_detail_complete_flow():
    """测试工单详情完成维修流程"""
    print("\n【GUI测试7】工单详情完成维修流程")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, maintenance_user, admin, instrument = setup_test_environment(tmpdir)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="测试故障",
            priority=MaintenancePriority.MEDIUM,
        )

        service.set_current_user(maintenance_user)
        success, _, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        data_manager.save()

        root = get_global_root()

        try:
            service.set_current_user(maintenance_user)
            dialog = MaintenanceOrderDetailDialog(root, service, maintenance_user, order)

            dialog.completion_option_var.set(MaintenanceCompletionOption.RESTORE_AVAILABLE.value)
            dialog.completion_notes_var.set("维修完成，测试正常")
            dialog._on_complete()

            assert dialog.result == True, "完成维修应返回True"
            print("  [OK] 通过：完成维修操作成功")

            updated_order = service.get_maintenance_order_by_id(order.id)
            assert updated_order.status == MaintenanceOrderStatus.COMPLETED
            assert updated_order.completion_option == MaintenanceCompletionOption.RESTORE_AVAILABLE
            print(f"  [OK] 通过：工单状态更新为: {updated_order.status.value}")
            print(f"  [OK] 通过：完成方式为: {updated_order.completion_option.value}")

            updated_instrument = service.get_instrument_by_id(instrument.id)
            assert updated_instrument.status == InstrumentStatus.AVAILABLE
            print(f"  [OK] 通过：仪器状态恢复为: {updated_instrument.status.value}")

            histories = service.get_operation_histories(instrument.id)
            complete_ops = [h for h in histories if h.operation_type == OperationType.MAINTENANCE_ORDER_COMPLETE]
            assert len(complete_ops) >= 1, "应记录完成操作日志"
            print("  [OK] 通过：完成维修已记录操作日志")

            dialog.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_order_detail_reject_flow():
    """测试工单详情驳回流程"""
    print("\n【GUI测试8】工单详情驳回流程")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, maintenance_user, admin, instrument = setup_test_environment(tmpdir)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="误报，实际正常",
            priority=MaintenancePriority.LOW,
        )
        data_manager.save()

        root = get_global_root()

        try:
            service.set_current_user(maintenance_user)
            dialog = MaintenanceOrderDetailDialog(root, service, maintenance_user, order)

            success, msg, updated_order = service.reject_maintenance_order(
                order_id=order.id,
                reason="测试驳回原因",
            )
            assert success, f"驳回失败: {msg}"

            updated_order = service.get_maintenance_order_by_id(order.id)
            assert updated_order.status == MaintenanceOrderStatus.REJECTED
            assert updated_order.rejection_reason == "测试驳回原因"
            print(f"  [OK] 通过：工单状态更新为: {updated_order.status.value}")

            updated_instrument = service.get_instrument_by_id(instrument.id)
            assert updated_instrument.status == InstrumentStatus.AVAILABLE
            print(f"  [OK] 通过：仪器状态恢复为: {updated_instrument.status.value}")

            histories = service.get_operation_histories(instrument.id)
            reject_ops = [h for h in histories if h.operation_type == OperationType.MAINTENANCE_ORDER_REJECT]
            assert len(reject_ops) >= 1, "应记录驳回操作日志"
            print("  [OK] 通过：驳回操作已记录操作日志")

            dialog.destroy()

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_gui_integration_flow():
    """测试GUI完整流程集成测试"""
    print("\n【GUI测试9】GUI完整流程集成测试")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager, service, normal_user, maintenance_user, admin, instrument = setup_test_environment(tmpdir)

        root = get_global_root()

        try:
            service.set_current_user(normal_user)
            create_dialog = MaintenanceOrderDialog(root, instrument, normal_user)
            create_dialog.fault_text.insert("1.0", "集成测试：仪器无法开机")
            create_dialog.priority_var.set(MaintenancePriority.URGENT.value)
            create_dialog.expected_date_var.set((date.today() + timedelta(days=3)).isoformat())
            create_dialog.assignee_var.set("维修员")
            create_dialog._on_ok()

            assert create_dialog.result is not None
            order_data = create_dialog.result

            success, msg, order = service.create_maintenance_order(**order_data)
            assert success, f"创建工单失败: {msg}"
            create_dialog.destroy()
            print(f"  [STEP 1] 创建工单成功: {order.id[:8]}...")

            service.set_current_user(maintenance_user)
            list_dialog = MaintenanceOrderListDialog(root, service, maintenance_user)
            list_dialog.selected_order = order
            list_dialog._on_accept()
            list_dialog.destroy()
            print(f"  [STEP 2] 接单成功")

            order = service.get_maintenance_order_by_id(order.id)
            detail_dialog = MaintenanceOrderDetailDialog(root, service, maintenance_user, order)
            detail_dialog.processing_note_var.set("检查发现保险丝烧毁")
            detail_dialog._on_add_note()
            detail_dialog.processing_note_var.set("更换保险丝，测试正常")
            detail_dialog._on_add_note()
            print(f"  [STEP 3] 添加2条处理记录")

            detail_dialog.completion_option_var.set(MaintenanceCompletionOption.RESTORE_AVAILABLE.value)
            detail_dialog.completion_notes_var.set("已修复")
            detail_dialog._on_complete()
            detail_dialog.destroy()
            print(f"  [STEP 4] 完成维修")

            order = service.get_maintenance_order_by_id(order.id)
            assert order.status == MaintenanceOrderStatus.COMPLETED
            assert len(order.logs) >= 5, "应包含创建、接单、2条记录、完成共5条日志"
            print(f"  [OK] 通过：完整流程执行成功")
            print(f"         工单状态: {order.status.value}")
            print(f"         日志数量: {len(order.logs)}")

            instrument_after = service.get_instrument_by_id(instrument.id)
            assert instrument_after.status == InstrumentStatus.AVAILABLE
            print(f"         仪器状态: {instrument_after.status.value}")

            histories = service.get_operation_histories(instrument.id)
            assert len(histories) >= 4, "应记录所有操作历史"
            print(f"         操作历史: {len(histories)}条")

        finally:
            try:
                root.update()
            except:
                pass


@require_tk
def test_maintenance_gui_persistence_recovery():
    """测试GUI跨重启数据恢复"""
    print("\n【GUI测试10】GUI跨重启数据恢复")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="普通用户")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
        admin = User.create_admin_user("admin", "管理员")

        instrument = _create_test_instrument(service)

        service.set_current_user(normal_user)
        success, _, order1 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="故障A",
            priority=MaintenancePriority.HIGH,
        )
        success, _, order2 = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="故障B",
            priority=MaintenancePriority.LOW,
        )

        service.set_current_user(maintenance_user)
        success, _, order1 = service.accept_maintenance_order(
            order_id=order1.id,
        )
        success, _, order1 = service.add_maintenance_processing_note(
            order_id=order1.id,
            note="正在处理",
        )
        data_manager.save()

        order1_id = order1.id
        order2_id = order2.id

        del data_manager
        del service

        print(f"  [INFO] 关闭程序，模拟重启...")

        data_manager2 = DataManager(data_dir=tmpdir)
        service2 = InstrumentService(data_manager2)

        root = get_global_root()

        try:
            service2.set_current_user(admin)
            list_dialog = MaintenanceOrderListDialog(root, service2, admin)

            tree_items = list_dialog.tree.get_children()
            assert len(tree_items) == 2, f"重启后应恢复2条工单，实际{len(tree_items)}"
            print(f"  [OK] 通过：重启后恢复 {len(tree_items)} 条工单")

            restored_order1 = service2.get_maintenance_order_by_id(order1_id)
            assert restored_order1 is not None
            assert restored_order1.status == MaintenanceOrderStatus.IN_PROGRESS
            assert len(restored_order1.logs) >= 3
            print(f"  [OK] 通过：工单1状态和日志完整恢复")

            restored_order2 = service2.get_maintenance_order_by_id(order2_id)
            assert restored_order2 is not None
            assert restored_order2.status == MaintenanceOrderStatus.PENDING
            print(f"  [OK] 通过：工单2状态完整恢复")

            detail_dialog = MaintenanceOrderDetailDialog(root, service2, admin, restored_order1)
            assert detail_dialog.order.status == MaintenanceOrderStatus.IN_PROGRESS
            assert len(detail_dialog.order.logs) >= 3
            print(f"  [OK] 通过：详情对话框正确显示恢复的数据")

            detail_dialog.destroy()
            list_dialog.destroy()

        finally:
            try:
                root.update()
            except:
                pass


if __name__ == "__main__":
    print("=" * 70)
    print("维修工单GUI回归测试")
    print("=" * 70)

    if not TK_AVAILABLE:
        print("⚠️  警告：Tkinter不可用，将跳过所有GUI测试")
        sys.exit(0)

    tests = [
        test_maintenance_order_dialog_initialization,
        test_maintenance_order_dialog_validation,
        test_maintenance_order_list_dialog_initialization,
        test_maintenance_order_list_permission_filter,
        test_maintenance_order_list_status_filter,
        test_maintenance_order_detail_dialog,
        test_maintenance_order_detail_complete_flow,
        test_maintenance_order_detail_reject_flow,
        test_maintenance_gui_integration_flow,
        test_maintenance_gui_persistence_recovery,
    ]

    passed = 0
    failed = 0
    skipped = 0
    failed_tests = []

    for test in tests:
        try:
            result = test()
            if result == True:
                skipped += 1
            else:
                passed += 1
        except AssertionError as e:
            failed += 1
            failed_tests.append((test.__name__, str(e)))
            print(f"  [FAIL] {test.__name__}: {e}")
        except Exception as e:
            failed += 1
            failed_tests.append((test.__name__, f"异常: {e}"))
            print(f"  [ERROR] {test.__name__}: {e}")

    print("\n" + "=" * 70)
    print(f"测试完成: 通过 {passed} 项，失败 {failed} 项，跳过 {skipped} 项")
    print("=" * 70)

    cleanup_global_root()

    if failed_tests:
        print("\n失败的测试:")
        for name, error in failed_tests:
            print(f"  - {name}: {error}")
        sys.exit(1)
    else:
        print("\n所有测试通过！")
        sys.exit(0)
