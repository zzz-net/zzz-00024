import sys
import os
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import User, UserRole
from src.storage import DataManager
from src.services import InstrumentService


def test_reschedule_bug():
    print("=" * 60)
    print("测试：已审批预约改期的库存锁定bug")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)
        
        admin_user = User.create_admin_user("admin", "管理员")
        service.set_current_user(admin_user)
        
        print("\n步骤1: 创建库存项（总库存 100）")
        item = service.create_inventory_item(
            name="测试仪器",
            category="测量仪器",
            model="TEST-100",
            total_quantity=100,
            unit="台",
            location="实验室A"
        )
        print(f"  ✓ 库存创建成功")
        print(f"    总库存: {item.total_quantity}, 锁定: {item.locked_quantity}, 可用: {item.available_quantity}")
        
        assert item.total_quantity == 100
        assert item.locked_quantity == 0
        assert item.available_quantity == 100
        
        print("\n步骤2: 创建预约（数量 30）")
        success, msg, reservation = service.create_reservation(
            inventory_item_id=item.id,
            requester="张三",
            department="研发部",
            quantity=30,
            expected_use_date=date.today() + timedelta(days=7),
            purpose="项目测试"
        )
        print(f"  ✓ 预约创建成功: {msg}")
        print(f"    预约状态: {reservation.status.value}")
        print(f"    总库存: {item.total_quantity}, 锁定: {item.locked_quantity}, 可用: {item.available_quantity}")
        
        assert reservation.status.value == "待审批"
        assert item.locked_quantity == 0
        assert item.available_quantity == 100
        
        print("\n步骤3: 审批通过预约")
        success, msg, reservation = service.approve_reservation(reservation.id)
        print(f"  ✓ 审批结果: {msg}")
        print(f"    预约状态: {reservation.status.value}")
        print(f"    总库存: {item.total_quantity}, 锁定: {item.locked_quantity}, 可用: {item.available_quantity}")
        
        assert reservation.status.value == "已审批"
        assert item.locked_quantity == 30, f"预期锁定30，实际锁定{item.locked_quantity}"
        assert item.available_quantity == 70, f"预期可用70，实际可用{item.available_quantity}"
        
        print("\n步骤4: 对已审批预约进行改期")
        print(f"  改期前: 锁定={item.locked_quantity}, 可用={item.available_quantity}")
        old_reservation_id = reservation.id
        success, msg, new_reservation = service.reschedule_reservation(
            reservation_id=old_reservation_id,
            new_use_date=date.today() + timedelta(days=14)
        )
        print(f"  ✓ 改期结果: {msg}")
        print(f"    旧预约状态: {reservation.status.value}")
        print(f"    新预约状态: {new_reservation.status.value}")
        print(f"    总库存: {item.total_quantity}, 锁定: {item.locked_quantity}, 可用: {item.available_quantity}")
        
        print("\n" + "=" * 60)
        print("BUG验证:")
        print("=" * 60)
        print(f"  预期: 锁定=30, 可用=70（改期不改变真实占用量）")
        print(f"  实际: 锁定={item.locked_quantity}, 可用={item.available_quantity}")
        
        if item.locked_quantity == 60:
            print("\n  ✗ BUG存在！锁定数量变成了60，重复累加了！")
            print(f"    旧预约ID: {old_reservation_id}（状态: {reservation.status.value}）")
            print(f"    新预约ID: {new_reservation.id}（状态: {new_reservation.status.value}）")
            print("    两个已审批状态的预约都锁定了30台，导致重复占用")
            return False
        elif item.locked_quantity == 30:
            print("\n  ✓ BUG已修复！锁定数量保持30，正确。")
            return True
        else:
            print(f"\n  ? 意外的锁定数量: {item.locked_quantity}")
            return False


if __name__ == "__main__":
    bug_exists = not test_reschedule_bug()
    print("\n" + "=" * 60)
    if bug_exists:
        print("结论: BUG存在，需要修复。")
    else:
        print("结论: BUG已修复。")
    print("=" * 60)
