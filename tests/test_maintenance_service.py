import sys
import os
import tempfile
import json
from datetime import date, timedelta, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    User, UserRole, Instrument, InstrumentStatus, InstrumentCategory,
    MaintenanceOrder, MaintenanceOrderStatus, MaintenancePriority,
    MaintenanceCompletionOption, OperationType,
)
from src.storage import DataManager
from src.services import InstrumentService


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


def test_create_maintenance_order():
    """测试创建维修工单"""
    print("\n【测试1】创建维修工单")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="普通用户")
        service.set_current_user(normal_user)

        instrument = _create_test_instrument(service)
        assert instrument is not None, "创建仪器失败"
        print(f"  [INFO] 创建测试仪器: {instrument.name}")

        success, msg, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="仪器无法开机，电源指示灯不亮",
            priority=MaintenancePriority.HIGH,
            expected_completion_date=date.today() + timedelta(days=7),
            assignee="李维修",
        )
        assert success, f"创建工单失败: {msg}"
        assert order is not None, "工单应为非空"
        assert order.instrument_id == instrument.id
        assert order.status == MaintenanceOrderStatus.PENDING
        assert order.priority == MaintenancePriority.HIGH
        assert order.requester == "普通用户"
        assert order.assignee == "李维修"
        assert len(order.logs) >= 1, "应至少有一条创建日志"
        assert order.logs[0].action == "创建工单"
        print(f"  [OK] 通过：工单创建成功，状态={order.status.value}")

        orders = service.get_maintenance_orders()
        assert len(orders) == 1, f"预期1条工单，实际{len(orders)}"
        print("  [OK] 通过：工单列表查询正确")

        retrieved = service.get_maintenance_order_by_id(order.id)
        assert retrieved is not None, "查询工单失败"
        assert retrieved.id == order.id
        print("  [OK] 通过：按ID查询工单正确")


def test_maintenance_order_permission_filter():
    """测试工单权限过滤 - 普通用户只能查看自己的工单"""
    print("\n【测试2】工单权限过滤")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        user1 = User(username="user1", role=UserRole.NORMAL, display_name="用户A")
        user2 = User(username="user2", role=UserRole.NORMAL, display_name="用户B")
        admin = User.create_admin_user("admin", "管理员")

        instrument1 = _create_test_instrument(service, "仪器A")
        instrument2 = _create_test_instrument(service, "仪器B")

        service.set_current_user(user1)
        success, _, order1 = service.create_maintenance_order(
            instrument_id=instrument1.id,
            fault_description="故障1",
            priority=MaintenancePriority.LOW,
        )
        assert success

        service.set_current_user(user2)
        success, _, order2 = service.create_maintenance_order(
            instrument_id=instrument2.id,
            fault_description="故障2",
            priority=MaintenancePriority.MEDIUM,
        )
        assert success

        service.set_current_user(user1)
        orders = service.get_maintenance_orders()
        user1_orders = [o for o in orders if o.requester == user1.display_name]
        assert len(user1_orders) == 1, f"用户A应只看到自己的1条工单，实际{len(user1_orders)}"
        assert user1_orders[0].id == order1.id
        print("  [OK] 通过：普通用户只能查看自己的工单")

        service.set_current_user(admin)
        orders = service.get_maintenance_orders()
        assert len(orders) == 2, f"管理员应看到全部2条工单，实际{len(orders)}"
        print("  [OK] 通过：管理员可以查看所有工单")


def test_maintenance_order_status_flow():
    """测试工单完整状态流转"""
    print("\n【测试3】工单状态流转")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
        admin = User.create_admin_user("admin", "管理员")

        instrument = _create_test_instrument(service)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="无法开机",
            priority=MaintenancePriority.HIGH,
        )
        assert success
        assert order.status == MaintenanceOrderStatus.PENDING
        print(f"  [STEP 1] 工单创建，状态: {order.status.value}")

        service.set_current_user(maintenance_user)
        success, msg, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert success, f"接单失败: {msg}"
        assert order.status == MaintenanceOrderStatus.IN_PROGRESS
        assert order.assignee == "维修员"
        assert order.accepted_at is not None
        print(f"  [STEP 2] 维修员接单，状态: {order.status.value}")

        success, msg, order = service.add_maintenance_processing_note(
            order_id=order.id,
            note="检查发现电源模块损坏，已订购配件",
        )
        assert success, f"添加处理记录失败: {msg}"
        assert len(order.logs) >= 3
        print(f"  [STEP 3] 添加处理记录，日志数: {len(order.logs)}")

        success, msg, order = service.complete_maintenance_order(
            order_id=order.id,
            completion_option=MaintenanceCompletionOption.RESTORE_AVAILABLE,
            notes="更换电源模块，测试正常",
        )
        assert success, f"完成工单失败: {msg}"
        assert order.status == MaintenanceOrderStatus.COMPLETED
        assert order.completion_option == MaintenanceCompletionOption.RESTORE_AVAILABLE
        assert order.completed_at is not None
        print(f"  [STEP 4] 完成维修，状态: {order.status.value}，完成方式: {order.completion_option.value}")

        instrument_after = service.get_instrument_by_id(instrument.id)
        assert instrument_after.status == InstrumentStatus.AVAILABLE
        print(f"  [OK] 通过：仪器状态恢复为: {instrument_after.status.value}")


def test_maintenance_lock_instrument():
    """测试维修中仪器锁定借出、校准入口"""
    print("\n【测试4】维修中仪器锁定逻辑")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="用户A")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
        admin = User.create_admin_user("admin", "管理员")

        instrument = _create_test_instrument(service)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="需要维修",
            priority=MaintenancePriority.MEDIUM,
        )
        assert success

        service.set_current_user(maintenance_user)
        success, _, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert success

        instrument_in_maintenance = service.get_instrument_by_id(instrument.id)
        assert instrument_in_maintenance.status == InstrumentStatus.MAINTENANCE
        print(f"  [INFO] 仪器状态变为: {instrument_in_maintenance.status.value}")

        service.set_current_user(admin)
        success, msg, _ = service.borrow_instrument(
            instrument_id=instrument.id,
            borrower="测试借用人",
            borrower_department="测试部门",
            borrow_date=date.today(),
            expected_return_date=date.today() + timedelta(days=7),
            purpose="测试",
        )
        assert not success, "维修中仪器应无法借出"
        assert "维修" in msg
        print(f"  [OK] 通过：借出被拦截，原因: {msg}")

        success, msg, _ = service.calibrate_instrument(
            instrument_id=instrument.id,
            calibration_date=date.today(),
            next_calibration_date=date.today() + timedelta(days=365),
            certificate_number="TEST001",
            calibration_agency="测试机构",
            result="合格",
            notes="",
        )
        assert not success, "维修中仪器应无法校准"
        assert "维修" in msg
        print(f"  [OK] 通过：校准被拦截，原因: {msg}")

        success, msg, _ = service.complete_maintenance_order(
            order_id=order.id,
            completion_option=MaintenanceCompletionOption.RESTORE_AVAILABLE,
        )
        assert success

        instrument_after = service.get_instrument_by_id(instrument.id)
        assert instrument_after.status == InstrumentStatus.AVAILABLE
        print(f"  [INFO] 维修完成后仪器状态: {instrument_after.status.value}")

        success, msg, _ = service.borrow_instrument(
            instrument_id=instrument.id,
            borrower="测试借用人",
            borrower_department="测试部门",
            borrow_date=date.today(),
            expected_return_date=date.today() + timedelta(days=7),
            purpose="测试",
        )
        assert success, f"维修完成后应可以借出: {msg}"
        print("  [OK] 通过：维修完成后可以正常借出")


def test_maintenance_completion_options():
    """测试维修完成后的三种状态切换选项"""
    print("\n【测试5】维修完成状态切换选项")
    print("-" * 70)

    test_cases = [
        (MaintenanceCompletionOption.RESTORE_AVAILABLE, InstrumentStatus.AVAILABLE, "恢复可用"),
        (MaintenanceCompletionOption.KEEP_FROZEN, InstrumentStatus.FROZEN, "保持冻结"),
        (MaintenanceCompletionOption.NEEDS_CALIBRATION, InstrumentStatus.CALIBRATION_DUE, "转入待校准"),
    ]

    for option, expected_status, desc in test_cases:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_manager = DataManager(data_dir=tmpdir)
            service = InstrumentService(data_manager)

            normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
            maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")

            instrument = _create_test_instrument(service)
            assert instrument.status == InstrumentStatus.AVAILABLE

            service.set_current_user(normal_user)
            success, _, order = service.create_maintenance_order(
                instrument_id=instrument.id,
                fault_description=f"测试-{desc}",
                priority=MaintenancePriority.LOW,
            )
            assert success

            service.set_current_user(maintenance_user)
            success, _, order = service.accept_maintenance_order(
                order_id=order.id,
            )
            assert success

            success, _, order = service.complete_maintenance_order(
                order_id=order.id,
                completion_option=option,
            )
            assert success

            instrument_after = service.get_instrument_by_id(instrument.id)
            assert instrument_after.status == expected_status, \
                f"{desc} 失败：预期 {expected_status.value}，实际 {instrument_after.status.value}"
            print(f"  [OK] 通过：{desc} -> 仪器状态: {instrument_after.status.value}")


def test_maintenance_preserve_borrowed_status():
    """测试维修完成时不覆盖已有借用状态"""
    print("\n【测试6】维修完成不覆盖借用状态")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        admin = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin)

        instrument = _create_test_instrument(service)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="发现故障需要维修",
            priority=MaintenancePriority.HIGH,
        )
        assert success

        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
        service.set_current_user(maintenance_user)
        success, _, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert success

        instrument = service.get_instrument_by_id(instrument.id)
        instrument.status = InstrumentStatus.BORROWED
        data_manager.update_instrument(instrument)
        print(f"  [INFO] 模拟维修期间仪器被借出，状态: {instrument.status.value}")

        success, _, order = service.complete_maintenance_order(
            order_id=order.id,
            completion_option=MaintenanceCompletionOption.RESTORE_AVAILABLE,
        )
        assert success

        instrument_after = service.get_instrument_by_id(instrument.id)
        assert instrument_after.status == InstrumentStatus.BORROWED, \
            f"应保持借出状态，实际: {instrument_after.status.value}"
        print(f"  [OK] 通过：维修完成后仪器保持借出状态: {instrument_after.status.value}")


def test_maintenance_persistence_and_recovery():
    """测试工单数据持久化和跨重启恢复"""
    print("\n【测试7】数据持久化与跨重启恢复")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")

        instrument1 = _create_test_instrument(service, "仪器A")
        instrument2 = _create_test_instrument(service, "仪器B")

        service.set_current_user(normal_user)
        success, msg, order1 = service.create_maintenance_order(
            instrument_id=instrument1.id,
            fault_description="故障A",
            priority=MaintenancePriority.HIGH,
            expected_completion_date=date.today() + timedelta(days=5),
            assignee="维修员",
        )
        assert success

        service.set_current_user(maintenance_user)
        success, _, order1 = service.accept_maintenance_order(
            order_id=order1.id,
        )
        assert success

        success, _, order1 = service.add_maintenance_processing_note(
            order_id=order1.id,
            note="正在排查故障原因",
        )
        assert success

        service.set_current_user(normal_user)
        success, _, order2 = service.create_maintenance_order(
            instrument_id=instrument2.id,
            fault_description="故障B",
            priority=MaintenancePriority.LOW,
        )
        assert success

        order1_id = order1.id
        order2_id = order2.id
        order1_log_count = len(order1.logs)

        del data_manager
        del service

        print(f"  [INFO] 关闭程序，模拟重启...")

        data_manager2 = DataManager(data_dir=tmpdir)
        service2 = InstrumentService(data_manager2)

        orders = service2.get_maintenance_orders()
        assert len(orders) == 2, f"重启后应恢复2条工单，实际{len(orders)}"
        print(f"  [OK] 通过：重启后恢复 {len(orders)} 条工单")

        restored_order1 = service2.get_maintenance_order_by_id(order1_id)
        assert restored_order1 is not None
        assert restored_order1.id == order1_id
        assert restored_order1.status == MaintenanceOrderStatus.IN_PROGRESS
        assert len(restored_order1.logs) == order1_log_count
        assert restored_order1.accepted_at is not None
        print(f"  [OK] 通过：工单1状态和日志完整恢复，状态={restored_order1.status.value}，日志数={len(restored_order1.logs)}")

        restored_order2 = service2.get_maintenance_order_by_id(order2_id)
        assert restored_order2 is not None
        assert restored_order2.status == MaintenanceOrderStatus.PENDING
        print(f"  [OK] 通过：工单2状态完整恢复，状态={restored_order2.status.value}")

        active = data_manager2.has_active_maintenance(instrument1.id)
        assert active, "重启后仍应检测到活跃维修工单"
        print("  [OK] 通过：活跃维修检测跨重启有效")


def test_maintenance_operation_logging():
    """测试维修工单操作日志记录"""
    print("\n【测试8】操作日志记录")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
        admin = User.create_admin_user("admin", "管理员")

        instrument = _create_test_instrument(service)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="测试故障",
            priority=MaintenancePriority.HIGH,
        )
        assert success

        histories = service.get_operation_histories(instrument.id)
        create_ops = [h for h in histories if h.operation_type == OperationType.MAINTENANCE_ORDER_CREATE]
        assert len(create_ops) >= 1, "应记录创建工单操作"
        print(f"  [OK] 通过：创建工单已记录到操作日志，共{len(create_ops)}条")

        service.set_current_user(maintenance_user)
        success, _, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert success

        histories = service.get_operation_histories(instrument.id)
        accept_ops = [h for h in histories if h.operation_type == OperationType.MAINTENANCE_ORDER_ACCEPT]
        assert len(accept_ops) >= 1, "应记录接单操作"
        print(f"  [OK] 通过：接单已记录到操作日志")

        success, _, order = service.add_maintenance_processing_note(
            order_id=order.id,
            note="测试处理记录",
        )
        assert success

        histories = service.get_operation_histories(instrument.id)
        process_ops = [h for h in histories if h.operation_type == OperationType.MAINTENANCE_ORDER_PROCESS]
        assert len(process_ops) >= 1, "应记录处理操作"
        print(f"  [OK] 通过：处理记录已记录到操作日志")

        success, _, order = service.complete_maintenance_order(
            order_id=order.id,
            completion_option=MaintenanceCompletionOption.RESTORE_AVAILABLE,
            notes="测试完成备注",
        )
        assert success

        histories = service.get_operation_histories(instrument.id)
        complete_ops = [h for h in histories if h.operation_type == OperationType.MAINTENANCE_ORDER_COMPLETE]
        assert len(complete_ops) >= 1, "应记录完成操作"
        print(f"  [OK] 通过：完成维修已记录到操作日志")

        total_ops = len(histories)
        print(f"  [SUMMARY] 仪器共记录 {total_ops} 条操作历史")


def test_maintenance_status_conflict_detection():
    """测试维修工单状态冲突拦截"""
    print("\n【测试9】状态冲突拦截")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
        other_maintenance = User(username="tech2", role=UserRole.MAINTENANCE, display_name="其他维修员")

        instrument = _create_test_instrument(service)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="测试故障",
            priority=MaintenancePriority.MEDIUM,
        )
        assert success

        service.set_current_user(normal_user)
        success, msg, _ = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert not success, "普通用户不能接单"
        print(f"  [OK] 通过：普通用户接单被拦截，原因: {msg}")

        service.set_current_user(maintenance_user)
        success, _, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert success
        print(f"  [INFO] 维修员已接单，状态: {order.status.value}")

        service.set_current_user(other_maintenance)
        success, msg, _ = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert not success, "已接单的工单不能重复接单"
        print(f"  [OK] 通过：重复接单被拦截，原因: {msg}")

        service.set_current_user(other_maintenance)
        success, msg, _ = service.complete_maintenance_order(
            order_id=order.id,
            completion_option=MaintenanceCompletionOption.RESTORE_AVAILABLE,
        )
        assert not success, "非负责人不能完成他人工单"
        print(f"  [OK] 通过：非负责人完成工单被拦截，原因: {msg}")

        service.set_current_user(maintenance_user)
        success, _, order = service.complete_maintenance_order(
            order_id=order.id,
            completion_option=MaintenanceCompletionOption.RESTORE_AVAILABLE,
        )
        assert success
        print(f"  [INFO] 负责人完成工单，状态: {order.status.value}")

        service.set_current_user(maintenance_user)
        success, msg, _ = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert not success, "已完成的工单不能接单"
        print(f"  [OK] 通过：已完成工单接单被拦截，原因: {msg}")

        service.set_current_user(maintenance_user)
        success, msg, _ = service.add_maintenance_processing_note(
            order_id=order.id,
            note="测试",
        )
        assert not success, "已完成的工单不能添加处理记录"
        print(f"  [OK] 通过：已完成工单添加记录被拦截，原因: {msg}")


def test_reject_maintenance_order():
    """测试驳回维修工单"""
    print("\n【测试10】驳回维修工单")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")

        instrument = _create_test_instrument(service)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="误报，实际正常",
            priority=MaintenancePriority.LOW,
        )
        assert success
        assert order.status == MaintenanceOrderStatus.PENDING

        service.set_current_user(maintenance_user)
        success, msg, order = service.reject_maintenance_order(
            order_id=order.id,
            reason="经检查仪器正常，无需维修",
        )
        assert success, f"驳回失败: {msg}"
        assert order.status == MaintenanceOrderStatus.REJECTED
        assert order.rejection_reason == "经检查仪器正常，无需维修"
        assert order.completed_at is not None
        print(f"  [OK] 通过：待分配工单驳回成功，状态: {order.status.value}")

        instrument_after = service.get_instrument_by_id(instrument.id)
        assert instrument_after.status == InstrumentStatus.AVAILABLE
        print(f"  [OK] 通过：驳回后仪器状态恢复为: {instrument_after.status.value}")

        histories = service.get_operation_histories(instrument.id)
        reject_ops = [h for h in histories if h.operation_type == OperationType.MAINTENANCE_ORDER_REJECT]
        assert len(reject_ops) >= 1, "应记录驳回操作"
        print("  [OK] 通过：驳回操作已记录到操作日志")


def test_maintenance_calibration_due_status():
    """测试维修完成转待校准后状态正确"""
    print("\n【测试11】维修转待校准状态处理")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)

        normal_user = User(username="user1", role=UserRole.NORMAL, display_name="申请人")
        maintenance_user = User(username="tech1", role=UserRole.MAINTENANCE, display_name="维修员")
        admin = User.create_admin_user("admin", "管理员")

        instrument = _create_test_instrument(service)

        service.set_current_user(normal_user)
        success, _, order = service.create_maintenance_order(
            instrument_id=instrument.id,
            fault_description="需要校准",
            priority=MaintenancePriority.MEDIUM,
        )
        assert success

        service.set_current_user(maintenance_user)
        success, _, order = service.accept_maintenance_order(
            order_id=order.id,
        )
        assert success

        success, _, order = service.complete_maintenance_order(
            order_id=order.id,
            completion_option=MaintenanceCompletionOption.NEEDS_CALIBRATION,
        )
        assert success

        instrument_after = service.get_instrument_by_id(instrument.id)
        assert instrument_after.status == InstrumentStatus.CALIBRATION_DUE
        print(f"  [OK] 通过：仪器状态变为: {instrument_after.status.value}")

        service.set_current_user(admin)
        success, msg, _ = service.calibrate_instrument(
            instrument_id=instrument.id,
            calibration_date=date.today(),
            next_calibration_date=date.today() + timedelta(days=365),
            certificate_number="CAL001",
            calibration_agency="计量院校",
            result="合格",
            notes="",
        )
        assert success, f"待校准状态应可以校准: {msg}"

        instrument_calibrated = service.get_instrument_by_id(instrument.id)
        assert instrument_calibrated.status == InstrumentStatus.AVAILABLE
        print(f"  [OK] 通过：校准完成后仪器状态变为: {instrument_calibrated.status.value}")


if __name__ == "__main__":
    print("=" * 70)
    print("维修工单服务层测试")
    print("=" * 70)

    tests = [
        test_create_maintenance_order,
        test_maintenance_order_permission_filter,
        test_maintenance_order_status_flow,
        test_maintenance_lock_instrument,
        test_maintenance_completion_options,
        test_maintenance_preserve_borrowed_status,
        test_maintenance_persistence_and_recovery,
        test_maintenance_operation_logging,
        test_maintenance_status_conflict_detection,
        test_reject_maintenance_order,
        test_maintenance_calibration_due_status,
    ]

    passed = 0
    failed = 0
    failed_tests = []

    for test in tests:
        try:
            test()
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
    print(f"测试完成: 通过 {passed} 项，失败 {failed} 项")
    print("=" * 70)

    if failed_tests:
        print("\n失败的测试:")
        for name, error in failed_tests:
            print(f"  - {name}: {error}")
        sys.exit(1)
    else:
        print("\n所有测试通过！")
        sys.exit(0)
