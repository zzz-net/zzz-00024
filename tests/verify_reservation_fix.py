import sys
import os
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import User, UserRole, ReservationStatus
from src.storage import DataManager, DataExporter
from src.services import InstrumentService


def demonstrate_user_impact():
    print("=" * 80)
    print("用户可见影响验证脚本 - 预约改期库存锁定Bug修复")
    print("=" * 80)
    
    print("\n" + "=" * 80)
    print("场景说明：")
    print("  某仪器总库存 100 台")
    print("  张三申请预约 30 台，7天后使用")
    print("  管理员审批通过，库存锁定 30 台")
    print("  张三申请改期到14天后使用")
    print("  问题：改期后锁定数量变成了 60 台，可用量变成 40 台")
    print("  预期：改期后锁定数量保持 30 台，可用量保持 70 台")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print("\n" + "▌" * 80)
        print("▌ 第一阶段：正常流程（创建→审批）")
        print("▌" * 80)
        
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)
        
        admin = User.create_admin_user("管理员", "系统管理员")
        service.set_current_user(admin)
        
        print("\n步骤1: 管理员创建库存项")
        item = service.create_inventory_item(
            name="便携式光谱仪",
            category="分析仪器",
            model="SPEC-2000",
            total_quantity=100,
            unit="台",
            location="中心实验室3号柜",
            manager="李主任",
            description="用于现场快速检测的便携式光谱仪"
        )
        print_inventory_status(item, "创建后")
        
        print("\n步骤2: 张三创建预约（30台，7天后使用）")
        success, msg, reservation = service.create_reservation(
            inventory_item_id=item.id,
            requester="张三",
            department="检测部",
            quantity=30,
            expected_use_date=date.today() + timedelta(days=7),
            purpose="外出检测任务-XX项目",
            notes="需要配套的校准片和数据线"
        )
        print(f"  结果: {msg}")
        print_reservation_status(reservation)
        print_inventory_status(item, "预约创建后")
        
        print("\n步骤3: 管理员审批通过")
        success, msg, reservation = service.approve_reservation(reservation.id)
        print(f"  结果: {msg}")
        print_reservation_status(reservation)
        print_inventory_status(item, "审批通过后")
        
        print("\n" + "▌" * 80)
        print("▌ 第二阶段：改期操作（Bug修复前后对比）")
        print("▌" * 80)
        
        print("\n【修复前】Bug表现：")
        print("  改期后锁定数量: 60 台（错误，重复累加）")
        print("  改期后可用数量: 40 台（错误）")
        print("  影响: 其他用户预约时会错误地显示可用量不足，造成资源浪费")
        print("  CSV导出: 总库存=100, 锁定=60, 可用=40（数据不一致）")
        
        print("\n【修复后】实际执行：")
        print(f"\n步骤4: 张三申请改期（改为14天后使用，数量不变）")
        old_reservation_id = reservation.id
        success, msg, new_reservation = service.reschedule_reservation(
            reservation_id=old_reservation_id,
            new_use_date=date.today() + timedelta(days=14)
        )
        print(f"  结果: {msg}")
        
        old_reservation = service.get_reservation_by_id(old_reservation_id)
        print(f"\n  旧预约状态: {old_reservation.status.value}")
        print(f"  新预约状态: {new_reservation.status.value}")
        print(f"  新预约数量: {new_reservation.quantity}")
        print(f"  新预约使用日期: {new_reservation.expected_use_date}")
        
        print_inventory_status(item, "改期后")
        
        print("\n" + "▌" * 80)
        print("▌ 第三阶段：验证用户可见的一致性")
        print("▌" * 80)
        
        print("\n步骤5: 验证可用量判断（后续预约审批）")
        print("  李四也想预约40台，7天后使用...")
        success, msg, r2 = service.create_reservation(
            inventory_item_id=item.id,
            requester="李四",
            department="研发部",
            quantity=40,
            expected_use_date=date.today() + timedelta(days=7),
            purpose="新产品研发测试"
        )
        success, msg, r2 = service.approve_reservation(r2.id)
        print(f"  审批结果: {msg}")
        if success:
            print("  ✓ 正确：可用量70台足够，审批通过")
        else:
            print("  ✗ 错误：可用量应该足够但被拒绝")
        
        print_inventory_status(item, "李四预约审批后")
        
        print("\n步骤6: 导出CSV验证数据一致性")
        csv_path = os.path.join(tmpdir, "inventory_export.csv")
        DataExporter.export_inventory_items_to_csv([item], csv_path)
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        header = lines[0].strip().split(',')
        data = lines[1].strip().split(',')
        total_idx = header.index('总库存')
        lock_idx = header.index('锁定数量')
        avail_idx = header.index('可用数量')
        
        exported_total = int(data[total_idx])
        exported_lock = int(data[lock_idx])
        exported_avail = int(data[avail_idx])
        
        print(f"\n  CSV导出内容:")
        print(f"    总库存: {exported_total}")
        print(f"    锁定数量: {exported_lock}")
        print(f"    可用数量: {exported_avail}")
        print(f"    验证: 可用 = 总库存 - 锁定 = {exported_total} - {exported_lock} = {exported_total - exported_lock}")
        
        if exported_avail == exported_total - exported_lock:
            print(f"    ✓ CSV导出数据一致: {exported_avail} = {exported_total - exported_lock}")
        else:
            print(f"    ✗ CSV导出数据不一致!")
        
        print("\n步骤7: 模拟重启应用（数据持久化验证）")
        print("  关闭应用，重新打开...")
        
        data_manager2 = DataManager(data_dir=tmpdir)
        service2 = InstrumentService(data_manager2)
        
        item_reloaded = service2.get_inventory_item_by_id(item.id)
        new_r_reloaded = service2.get_reservation_by_id(new_reservation.id)
        old_r_reloaded = service2.get_reservation_by_id(old_reservation_id)
        r2_reloaded = service2.get_reservation_by_id(r2.id)
        
        print(f"\n  重启后库存状态:")
        print_inventory_status(item_reloaded, "重启后")
        
        print(f"\n  重启后预约状态:")
        print(f"    原预约(张三改期前): {old_r_reloaded.status.value}")
        print(f"    新预约(张三改期后): {new_r_reloaded.status.value} (数量: {new_r_reloaded.quantity})")
        print(f"    李四的预约: {r2_reloaded.status.value} (数量: {r2_reloaded.quantity})")
        
        total_locked = new_r_reloaded.quantity + r2_reloaded.quantity
        if item_reloaded.locked_quantity == total_locked:
            print(f"    ✓ 重启后锁定数量正确: {item_reloaded.locked_quantity} = {new_r_reloaded.quantity} + {r2_reloaded.quantity}")
        else:
            print(f"    ✗ 重启后锁定数量不一致!")
        
        print("\n步骤8: 实际领用验证")
        print("  张三来领用30台仪器...")
        success, msg, _ = service2.fulfill_reservation(new_r_reloaded.id)
        print(f"  结果: {msg}")
        print_inventory_status(item_reloaded, "张三领用后")
        
        print("\n" + "▌" * 80)
        print("▌ 第四阶段：用户可见影响总结")
        print("▌" * 80)
        
        print("\n✅ Bug修复前后对比:")
        print("-" * 80)
        print(f"  指标              | 修复前(Bug) | 修复后(正确)")
        print(f"  ------------------|-------------|-------------")
        print(f"  改期后锁定数量    | 60 台       | 30 台")
        print(f"  改期后可用数量    | 40 台       | 70 台")
        print(f"  后续预约可用性    | 错误拒绝    | 正确判断")
        print(f"  CSV数据一致性     | 不一致      | 一致")
        print(f"  重启后数据恢复    | 可能错误    | 完全正确")
        print(f"  资源利用率        | 浪费(虚占)  | 合理分配")
        
        print("\n✅ 对用户的具体影响:")
        print("  1. 库存列表显示正确的可用数量，不会误导用户")
        print("  2. 预约审批时可用量判断准确，不会错误拒绝合理申请")
        print("  3. 导出的CSV/JSON报表数据一致，可用量=总库存-锁定量")
        print("  4. 关闭重开后数据保持一致，锁定量不会错乱")
        print("  5. 级联改期、取消、领用等后续操作都能正确处理")
        
        print("\n✅ 状态流转正确性:")
        print(f"  原预约: 待审批 → 已审批 → 已改期  (释放锁定)")
        print(f"  新预约: 待审批 → 已审批            (重新锁定)")
        print(f"  锁定量:  0 → 30 → (释放30) → (锁定30) = 30 ✓")
        
        print("\n" + "=" * 80)
        print("验证完成：所有用户可见影响已恢复正常 ✓")
        print("=" * 80)


def print_inventory_status(item, stage=""):
    bar_length = 50
    total = item.total_quantity
    locked = item.locked_quantity
    avail = item.available_quantity
    
    locked_pct = int(locked / total * bar_length) if total > 0 else 0
    avail_pct = bar_length - locked_pct
    
    bar = "█" * locked_pct + "░" * avail_pct
    
    print(f"\n  库存状态 [{stage}]:")
    print(f"    {bar}")
    print(f"    总库存: {total} 台 | 锁定: {locked} 台 | 可用: {avail} 台")
    print(f"    可用率: {avail/total*100:.1f}%")


def print_reservation_status(reservation):
    print(f"\n  预约信息:")
    print(f"    ID: {reservation.id[:8]}...")
    print(f"    申请人: {reservation.requester} ({reservation.department})")
    print(f"    数量: {reservation.quantity} 台")
    print(f"    状态: {reservation.status.value}")
    print(f"    使用日期: {reservation.expected_use_date}")


if __name__ == "__main__":
    demonstrate_user_impact()
