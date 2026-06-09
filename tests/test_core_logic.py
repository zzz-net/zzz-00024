import sys
import os
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    User, UserRole,
)
from src.storage import DataManager
from src.services import InstrumentService, create_sample_data


def run_tests():
    print("=" * 60)
    print("实验室仪器管理系统 - 核心逻辑测试")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_manager = DataManager(data_dir=tmpdir)
        service = InstrumentService(data_manager)
        
        print("\n1. 测试样例数据加载...")
        create_sample_data(data_manager)
        instruments = service.get_instruments()
        print(f"   ✓ 成功加载 {len(instruments)} 台样例仪器")
        
        print("\n2. 测试各仪器初始状态:")
        for instr in instruments:
            print(f"   - {instr.name}: {instr.status.value}")
            if instr.calibration_due_date:
                status = "已过期" if instr.is_calibration_expired() else "正常"
                print(f"     校准到期日: {instr.calibration_due_date} ({status})")
        
        print("\n3. 测试【借出失败】场景 - 校准过期的仪器:")
        expired_instr = None
        for instr in instruments:
            if instr.status == InstrumentStatus.CALIBRATION_EXPIRED:
                expired_instr = instr
                break
        
        if expired_instr:
            print(f"   测试仪器: {expired_instr.name} (状态: {expired_instr.status.value})")
            can_borrow, reason = expired_instr.can_borrow()
            print(f"   能否借出: {can_borrow}")
            print(f"   拒绝原因: {reason}")
            assert not can_borrow, "校准过期的仪器应该不能借出"
            assert "校准已过期" in reason, "错误信息应包含'校准已过期'"
            print("   ✓ 正确拒绝借出校准过期的仪器")
        else:
            print("   ✗ 未找到校准过期的测试仪器")
        
        print("\n4. 测试【借出失败】场景 - 已借出的仪器:")
        borrowed_instr = None
        for instr in instruments:
            if instr.status == InstrumentStatus.BORROWED:
                borrowed_instr = instr
                break
        
        if borrowed_instr:
            print(f"   测试仪器: {borrowed_instr.name} (状态: {borrowed_instr.status.value})")
            can_borrow, reason = borrowed_instr.can_borrow()
            print(f"   能否借出: {can_borrow}")
            print(f"   拒绝原因: {reason}")
            assert not can_borrow, "已借出的仪器应该不能借出"
            print("   ✓ 正确拒绝借出已借出的仪器")
        else:
            print("   ✗ 未找到已借出的测试仪器")
        
        print("\n5. 测试【借出失败】场景 - 冻结的仪器:")
        frozen_instr = None
        for instr in instruments:
            if instr.status == InstrumentStatus.FROZEN:
                frozen_instr = instr
                break
        
        if frozen_instr:
            print(f"   测试仪器: {frozen_instr.name} (状态: {frozen_instr.status.value})")
            can_borrow, reason = frozen_instr.can_borrow()
            print(f"   能否借出: {can_borrow}")
            print(f"   拒绝原因: {reason}")
            assert not can_borrow, "冻结的仪器应该不能借出"
            print("   ✓ 正确拒绝借出冻结的仪器")
        else:
            print("   ✗ 未找到冻结的测试仪器")
        
        print("\n6. 测试【正常归还】场景:")
        if borrowed_instr:
            active_record = service.get_active_borrow_record(borrowed_instr.id)
            if active_record:
                print(f"   测试仪器: {borrowed_instr.name}")
                print(f"   当前借用人: {active_record.borrower}")
                print(f"   借用记录状态: {active_record.status.value}")
                
                can_return, reason = active_record.can_return()
                print(f"   能否归还: {can_return}")
                assert can_return, "借出中的记录应该可以归还"
                
                success, message, record = service.return_instrument(
                    borrow_record_id=active_record.id,
                    return_date=date.today(),
                    notes="测试归还"
                )
                print(f"   归还结果: {success} - {message}")
                assert success, "归还应该成功"
                
                updated_instr = service.get_instrument_by_id(borrowed_instr.id)
                print(f"   归还后仪器状态: {updated_instr.status.value}")
                assert updated_instr.status == InstrumentStatus.AVAILABLE, "归还后状态应为可用"
                
                print("   ✓ 正常归还测试通过")
            else:
                print("   ✗ 未找到活跃的借用记录")
        else:
            print("   ✗ 未找到已借出的测试仪器")
        
        print("\n7. 测试【重复归还】边界检查:")
        if borrowed_instr and active_record:
            can_return, reason = active_record.can_return()
            print(f"   测试已归还的记录再次归还")
            print(f"   能否归还: {can_return}")
            print(f"   拒绝原因: {reason}")
            assert not can_return, "已归还的记录不能再次归还"
            assert "不能重复归还" in reason, "错误信息应包含'不能重复归还'"
            
            success, message, record = service.return_instrument(
                borrow_record_id=active_record.id,
                return_date=date.today(),
                notes="测试重复归还"
            )
            print(f"   服务层归还结果: {success} - {message}")
            assert not success, "服务层也应该拒绝重复归还"
            print("   ✓ 正确拒绝重复归还")
        
        print("\n8. 测试【权限控制】- 普通用户不能解冻:")
        normal_user = User.create_normal_user("test_user", "测试用户")
        service.set_current_user(normal_user)
        print(f"   当前用户: {normal_user.display_name} ({normal_user.role.value})")
        print(f"   能否解冻维修冻结: {normal_user.can_unfreeze_maintenance()}")
        assert not normal_user.can_unfreeze_maintenance(), "普通用户不能解冻"
        
        if frozen_instr:
            success, message = service.unfreeze_instrument(frozen_instr.id, "测试解冻")
            print(f"   解冻结果: {success} - {message}")
            assert not success, "普通用户解冻应该失败"
            assert "权限" in message, "错误信息应包含'权限'"
            print("   ✓ 正确拒绝普通用户解冻")
        
        print("\n9. 测试【权限控制】- 维修人员可以解冻:")
        maintenance_user = User.create_maintenance_user("tech", "维修人员")
        service.set_current_user(maintenance_user)
        print(f"   当前用户: {maintenance_user.display_name} ({maintenance_user.role.value})")
        print(f"   能否解冻维修冻结: {maintenance_user.can_unfreeze_maintenance()}")
        assert maintenance_user.can_unfreeze_maintenance(), "维修人员可以解冻"
        
        if frozen_instr:
            success, message = service.unfreeze_instrument(frozen_instr.id, "测试解冻")
            print(f"   解冻结果: {success} - {message}")
            assert success, "维修人员解冻应该成功"
            
            updated_instr = service.get_instrument_by_id(frozen_instr.id)
            print(f"   解冻后仪器状态: {updated_instr.status.value}")
            print("   ✓ 维修人员成功解冻")
        
        print("\n10. 测试【校准录入并解冻】:")
        if expired_instr:
            print(f"   测试仪器: {expired_instr.name} (状态: {expired_instr.status.value})")
            print(f"   当前校准到期日: {expired_instr.calibration_due_date}")
            
            admin_user = User.create_admin_user("admin", "管理员")
            service.set_current_user(admin_user)
            
            new_cal_date = date.today()
            next_cal_date = new_cal_date + timedelta(days=365)
            
            success, message, cal_record = service.calibrate_instrument(
                instrument_id=expired_instr.id,
                calibration_date=new_cal_date,
                next_calibration_date=next_cal_date,
                certificate_number="TEST-CAL-2024-001",
                calibration_agency="测试计量院",
                result="合格",
                notes="测试校准"
            )
            print(f"   校准录入结果: {success} - {message}")
            assert success, "校准录入应该成功"
            
            updated_instr = service.get_instrument_by_id(expired_instr.id)
            print(f"   校准后状态: {updated_instr.status.value}")
            print(f"   新的校准到期日: {updated_instr.calibration_due_date}")
            assert updated_instr.status == InstrumentStatus.AVAILABLE, "校准后状态应为可用"
            assert updated_instr.calibration_due_date == next_cal_date, "校准到期日应更新"
            print("   ✓ 校准录入成功并更新状态")
        
        print("\n11. 测试【新增仪器】:")
        new_instr = service.create_instrument(
            name="测试仪器",
            category=InstrumentCategory.OTHER,
            model="TEST-001",
            serial_number="SN-TEST-001",
            location="测试实验室",
            manager="测试员",
            calibration_due_date=date.today() + timedelta(days=180),
            description="测试用仪器"
        )
        print(f"   新增仪器: {new_instr.name}")
        print(f"   仪器状态: {new_instr.status.value}")
        assert new_instr.status == InstrumentStatus.AVAILABLE, "新增仪器状态应为可用"
        print("   ✓ 新增仪器成功")
        
        print("\n12. 测试【操作历史记录】:")
        histories = service.get_operation_histories(new_instr.id)
        print(f"   操作历史数量: {len(histories)}")
        assert len(histories) >= 1, "应该至少有一条操作历史"
        print(f"   最新操作: {histories[0].operation_type.value} - {histories[0].details}")
        print("   ✓ 操作历史记录正常")
        
        print("\n" + "=" * 60)
        print("所有测试通过! ✓")
        print("=" * 60)
        
        print("\n" + "=" * 60)
        print("样例仪器说明 (用于演示):")
        print("=" * 60)
        print("\n可演示的场景:")
        print("  1. 借出失败: 选择'紫外可见分光光度计'(校准过期),点击'借出'")
        print("  2. 正常归还: 选择'数字示波器'(借出中),点击'归还'")
        print("  3. 校准解冻: 切换到维修人员,选择'万能材料试验机'(冻结)")
        print("     或'紫外可见分光光度计'(校准过期),点击'校准录入'")
        print("\n边界检查演示:")
        print("  - 普通用户无法解冻冻结仪器")
        print("  - 已归还的记录无法重复归还")
        print("  - 校准过期/冻结/借出中 的仪器无法借出")
        print("=" * 60)


if __name__ == "__main__":
    run_tests()
