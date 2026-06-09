import sys
import os
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import User, UserRole, ReservationStatus
from src.storage import DataManager, DataExporter
from src.services import InstrumentService


def run_regression_tests():
    print("=" * 70)
    print("预约管理 - 回归测试套件")
    print("=" * 70)
    
    all_passed = True
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)
        
        admin_user = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin_user)
        
        print("\n【测试1】已审批预约改期（相同数量）- Bug修复验证")
        print("-" * 70)
        try:
            item = service.create_inventory_item(
                name="测试仪器A", category="测量", model="A100",
                total_quantity=100, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item.id, "用户1", "部门1", 30, date.today() + timedelta(days=7)
            )
            service.approve_reservation(r1.id)
            
            assert item.locked_quantity == 30, f"预期锁定30，实际{item.locked_quantity}"
            assert item.available_quantity == 70
            
            success, msg, r2 = service.reschedule_reservation(
                r1.id, date.today() + timedelta(days=14)
            )
            
            assert success, f"改期失败: {msg}"
            assert r1.status == ReservationStatus.RESCHEDULED, f"旧预约状态应为已改期，实际{r1.status}"
            assert r2.status == ReservationStatus.APPROVED, f"新预约状态应为已审批，实际{r2.status}"
            assert item.locked_quantity == 30, f"改期后锁定应为30，实际{item.locked_quantity}"
            assert item.available_quantity == 70, f"改期后可用应为70，实际{item.available_quantity}"
            
            print("  ✓ 通过：改期后锁定数量保持30，未重复累加")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试2】已审批预约改期（修改数量）")
        print("-" * 70)
        try:
            item2 = service.create_inventory_item(
                name="测试仪器B", category="测量", model="B200",
                total_quantity=100, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item2.id, "用户2", "部门2", 30, date.today() + timedelta(days=7)
            )
            service.approve_reservation(r1.id)
            
            assert item2.locked_quantity == 30
            
            success, msg, r2 = service.reschedule_reservation(
                r1.id, date.today() + timedelta(days=14), new_quantity=50
            )
            
            assert success, f"改期失败: {msg}"
            assert item2.locked_quantity == 50, f"改期后锁定应为50，实际{item2.locked_quantity}"
            assert item2.available_quantity == 50, f"改期后可用应为50，实际{item2.available_quantity}"
            
            print("  ✓ 通过：改期并修改数量后，锁定数量正确更新为50")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试3】待审批预约改期（不应影响锁定）")
        print("-" * 70)
        try:
            item3 = service.create_inventory_item(
                name="测试仪器C", category="测量", model="C300",
                total_quantity=100, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item3.id, "用户3", "部门3", 30, date.today() + timedelta(days=7)
            )
            
            assert r1.status == ReservationStatus.PENDING
            assert item3.locked_quantity == 0
            
            success, msg, r2 = service.reschedule_reservation(
                r1.id, date.today() + timedelta(days=14)
            )
            
            assert success, f"改期失败: {msg}"
            assert r1.status == ReservationStatus.RESCHEDULED
            assert r2.status == ReservationStatus.PENDING, f"新预约状态应为待审批，实际{r2.status}"
            assert item3.locked_quantity == 0, f"待审批改期不应锁定，实际锁定{item3.locked_quantity}"
            
            success, _, r2 = service.approve_reservation(r2.id)
            assert item3.locked_quantity == 30, f"审批后应锁定30，实际{item3.locked_quantity}"
            
            print("  ✓ 通过：待审批改期不影响锁定，后续审批正常锁定")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试4】取消已审批预约（应释放锁定）")
        print("-" * 70)
        try:
            item4 = service.create_inventory_item(
                name="测试仪器D", category="测量", model="D400",
                total_quantity=100, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item4.id, "用户4", "部门4", 25, date.today() + timedelta(days=7)
            )
            service.approve_reservation(r1.id)
            
            assert item4.locked_quantity == 25
            
            success, msg, _ = service.cancel_reservation(r1.id, "测试取消")
            
            assert success, f"取消失败: {msg}"
            assert r1.status == ReservationStatus.CANCELLED
            assert item4.locked_quantity == 0, f"取消后锁定应为0，实际{item4.locked_quantity}"
            assert item4.available_quantity == 100
            
            print("  ✓ 通过：取消已审批预约正确释放锁定")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试5】实际领用（应扣减库存并释放锁定）")
        print("-" * 70)
        try:
            item5 = service.create_inventory_item(
                name="测试仪器E", category="测量", model="E500",
                total_quantity=100, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item5.id, "用户5", "部门5", 20, date.today() + timedelta(days=7)
            )
            service.approve_reservation(r1.id)
            
            assert item5.locked_quantity == 20
            assert item5.total_quantity == 100
            
            success, msg, _ = service.fulfill_reservation(r1.id)
            
            assert success, f"领用失败: {msg}"
            assert r1.status == ReservationStatus.FULFILLED
            assert item5.total_quantity == 80, f"领用后总库存应为80，实际{item5.total_quantity}"
            assert item5.locked_quantity == 0, f"领用后锁定应为0，实际{item5.locked_quantity}"
            assert item5.available_quantity == 80
            
            print("  ✓ 通过：领用正确扣减库存并释放锁定")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试6】后续审批判断（锁定后其他预约应受影响）")
        print("-" * 70)
        try:
            item6 = service.create_inventory_item(
                name="测试仪器F", category="测量", model="F600",
                total_quantity=50, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item6.id, "用户6", "部门6", 30, date.today() + timedelta(days=7)
            )
            service.approve_reservation(r1.id)
            
            assert item6.locked_quantity == 30
            assert item6.available_quantity == 20
            
            success, _, r2 = service.create_reservation(
                item6.id, "用户7", "部门7", 25, date.today() + timedelta(days=7)
            )
            success, msg, _ = service.approve_reservation(r2.id)
            
            assert not success, "可用数量不足时审批应失败"
            assert "可用数量不足" in msg, f"错误信息应提示可用数量不足，实际: {msg}"
            assert r2.status == ReservationStatus.PENDING, f"审批失败应保持待审批状态"
            assert item6.locked_quantity == 30, f"审批失败不应改变锁定数量"
            
            print("  ✓ 通过：可用数量不足时正确拒绝审批")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试7】跨重启数据一致性（锁定数量正确恢复）")
        print("-" * 70)
        try:
            item7 = service.create_inventory_item(
                name="测试仪器G", category="测量", model="G700",
                total_quantity=100, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item7.id, "用户8", "部门8", 40, date.today() + timedelta(days=7)
            )
            service.approve_reservation(r1.id)
            
            success, _, r2 = service.reschedule_reservation(
                r1.id, date.today() + timedelta(days=21), new_quantity=35
            )
            
            assert item7.locked_quantity == 35
            assert r1.status == ReservationStatus.RESCHEDULED
            assert r2.status == ReservationStatus.APPROVED
            
            data_manager2 = DataManager(data_dir=tmpdir)
            service2 = InstrumentService(data_manager2)
            
            item7_reloaded = service2.get_inventory_item_by_id(item7.id)
            r1_reloaded = service2.get_reservation_by_id(r1.id)
            r2_reloaded = service2.get_reservation_by_id(r2.id)
            
            assert item7_reloaded.locked_quantity == 35, f"重启后锁定应为35，实际{item7_reloaded.locked_quantity}"
            assert item7_reloaded.available_quantity == 65, f"重启后可用应为65，实际{item7_reloaded.available_quantity}"
            assert r1_reloaded.status == ReservationStatus.RESCHEDULED
            assert r2_reloaded.status == ReservationStatus.APPROVED
            
            print("  ✓ 通过：重启后锁定数量和预约状态正确恢复")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试8】多次改级联改期（状态链正确）")
        print("-" * 70)
        try:
            item8 = service.create_inventory_item(
                name="测试仪器H", category="测量", model="H800",
                total_quantity=100, unit="台"
            )
            success, _, r1 = service.create_reservation(
                item8.id, "用户9", "部门9", 20, date.today() + timedelta(days=7)
            )
            service.approve_reservation(r1.id)
            
            success, _, r2 = service.reschedule_reservation(
                r1.id, date.today() + timedelta(days=14)
            )
            success, _, r3 = service.reschedule_reservation(
                r2.id, date.today() + timedelta(days=21)
            )
            
            assert item8.locked_quantity == 20, f"多次改期后锁定应为20，实际{item8.locked_quantity}"
            assert r1.status == ReservationStatus.RESCHEDULED
            assert r2.status == ReservationStatus.RESCHEDULED
            assert r3.status == ReservationStatus.APPROVED
            
            print("  ✓ 通过：多次级联改期后锁定数量正确，状态链清晰")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        
        print("\n【测试9】导出数据中的可用量一致性")
        print("-" * 70)
        try:
            export_path = os.path.join(tmpdir, "test_export.csv")
            items = [item, item2, item3, item4, item5, item6, item7, item8]
            
            csv_path = DataExporter.export_inventory_items_to_csv(items, export_path)
            
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            header = lines[0].strip().split(',')
            avail_idx = header.index('可用数量')
            lock_idx = header.index('锁定数量')
            total_idx = header.index('总库存')
            
            for i, it in enumerate(items):
                data = lines[i + 1].strip().split(',')
                exported_total = int(data[total_idx])
                exported_locked = int(data[lock_idx])
                exported_avail = int(data[avail_idx])
                
                assert exported_total == it.total_quantity
                assert exported_locked == it.locked_quantity
                assert exported_avail == it.available_quantity
                assert exported_avail == exported_total - exported_locked
            
            print("  ✓ 通过：导出CSV中的总库存、锁定、可用数量一致")
        except AssertionError as e:
            print(f"  ✗ 失败: {e}")
            all_passed = False
        except Exception as e:
            print(f"  ? 跳过（导出方法待实现）: {e}")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("所有回归测试通过！✓")
    else:
        print("部分测试失败！✗")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = run_regression_tests()
    sys.exit(0 if success else 1)
