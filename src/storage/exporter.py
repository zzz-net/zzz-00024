import csv
import json
import os
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from ..models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    BorrowRecord, BorrowStatus,
    OperationHistory, OperationType,
    CalibrationRecord,
    InventoryItem,
    Reservation, ReservationStatus,
    InventoryCheck, InventoryCheckStatus,
    InventoryCheckConflict, ConflictType, ConflictResolution,
    CalibrationSchedule, CalibrationScheduleStatus,
    CalibrationScheduleItem, CalibrationScheduleItemStatus,
    CalibrationScheduleConflict, CalibrationConflictType,
    CalibrationConflictResolution,
)


class DataExporter:
    @staticmethod
    def _ensure_dir(dir_path: str) -> None:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

    @staticmethod
    def _default_serializer(obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, (InstrumentStatus, InstrumentCategory, BorrowStatus, OperationType, ReservationStatus)):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def export_instruments_to_json(instruments: List[Instrument], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = [instr.to_dict() for instr in instruments]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_instruments_to_csv(instruments: List[Instrument], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        headers = [
            'ID', '仪器名称', '类别', '型号', '序列号', '存放位置',
            '负责人', '校准到期日', '状态', '描述', '创建时间', '更新时间'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for instr in instruments:
                writer.writerow([
                    instr.id,
                    instr.name,
                    instr.category.value,
                    instr.model,
                    instr.serial_number,
                    instr.location,
                    instr.manager,
                    instr.calibration_due_date.isoformat() if instr.calibration_due_date else '',
                    instr.status.value,
                    instr.description,
                    instr.created_at.isoformat(),
                    instr.updated_at.isoformat(),
                ])
        
        return filepath

    @staticmethod
    def export_borrow_records_to_json(records: List[BorrowRecord], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = [record.to_dict() for record in records]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_borrow_records_to_csv(records: List[BorrowRecord], filepath: str, 
                                      instruments: Optional[List[Instrument]] = None) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        instr_map = {i.id: i.name for i in instruments} if instruments else {}
        
        headers = [
            'ID', '仪器ID', '仪器名称', '借用人', '所属部门', '借用日期',
            '预计归还日期', '实际归还日期', '用途', '备注', '状态', '创建时间'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for record in records:
                writer.writerow([
                    record.id,
                    record.instrument_id,
                    instr_map.get(record.instrument_id, ''),
                    record.borrower,
                    record.borrower_department,
                    record.borrow_date.isoformat(),
                    record.expected_return_date.isoformat(),
                    record.actual_return_date.isoformat() if record.actual_return_date else '',
                    record.purpose,
                    record.notes,
                    record.status.value,
                    record.created_at.isoformat(),
                ])
        
        return filepath

    @staticmethod
    def export_calibration_records_to_json(records: List[CalibrationRecord], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = [record.to_dict() for record in records]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_calibration_records_to_csv(records: List[CalibrationRecord], filepath: str,
                                           instruments: Optional[List[Instrument]] = None) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        instr_map = {i.id: i.name for i in instruments} if instruments else {}
        
        headers = [
            'ID', '仪器ID', '仪器名称', '校准日期', '下次校准日期',
            '证书编号', '校准机构', '结果', '备注', '创建时间'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for record in records:
                writer.writerow([
                    record.id,
                    record.instrument_id,
                    instr_map.get(record.instrument_id, ''),
                    record.calibration_date.isoformat(),
                    record.next_calibration_date.isoformat(),
                    record.certificate_number,
                    record.calibration_agency,
                    record.result,
                    record.notes,
                    record.created_at.isoformat(),
                ])
        
        return filepath

    @staticmethod
    def export_operation_histories_to_json(histories: List[OperationHistory], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = [h.to_dict() for h in histories]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_operation_histories_to_csv(histories: List[OperationHistory], filepath: str,
                                           instruments: Optional[List[Instrument]] = None) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        instr_map = {i.id: i.name for i in instruments} if instruments else {}
        
        headers = [
            'ID', '仪器ID', '仪器名称', '操作类型', '操作人',
            '时间', '详情', '关联记录ID'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for history in histories:
                writer.writerow([
                    history.id,
                    history.instrument_id,
                    instr_map.get(history.instrument_id, ''),
                    history.operation_type.value,
                    history.operator,
                    history.timestamp.isoformat(),
                    history.details,
                    history.related_record_id or '',
                ])
        
        return filepath

    @staticmethod
    def export_all_to_json(instruments: List[Instrument], 
                            borrow_records: List[BorrowRecord],
                            calibration_records: List[CalibrationRecord],
                            operation_histories: List[OperationHistory],
                            filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = {
            'export_time': datetime.now().isoformat(),
            'instruments': [i.to_dict() for i in instruments],
            'borrow_records': [r.to_dict() for r in borrow_records],
            'calibration_records': [r.to_dict() for r in calibration_records],
            'operation_histories': [h.to_dict() for h in operation_histories],
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_inventory_items_to_json(items: List[InventoryItem], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = [item.to_dict() for item in items]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_inventory_items_to_csv(items: List[InventoryItem], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        headers = [
            'ID', '名称', '类别', '型号', '总库存', '锁定数量', '可用数量',
            '单位', '位置', '负责人', '描述', '创建时间', '更新时间'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for item in items:
                writer.writerow([
                    item.id,
                    item.name,
                    item.category,
                    item.model,
                    item.total_quantity,
                    item.locked_quantity,
                    item.available_quantity,
                    item.unit,
                    item.location,
                    item.manager,
                    item.description,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ])
        
        return filepath

    @staticmethod
    def export_reservations_to_json(reservations: List[Reservation], filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = [r.to_dict() for r in reservations]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_reservations_to_csv(reservations: List[Reservation], filepath: str,
                                    inventory_items: Optional[List[InventoryItem]] = None) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        item_map = {i.id: i.name for i in inventory_items} if inventory_items else {}
        
        headers = [
            'ID', '库存项ID', '库存项名称', '申请人', '部门', '数量',
            '预计使用日期', '用途', '状态', '审批人', '审批时间',
            '原预约ID', '备注', '创建时间', '更新时间'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for r in reservations:
                writer.writerow([
                    r.id,
                    r.inventory_item_id,
                    item_map.get(r.inventory_item_id, ''),
                    r.requester,
                    r.department,
                    r.quantity,
                    r.expected_use_date.isoformat(),
                    r.purpose,
                    r.status.value,
                    r.approver or '',
                    r.approved_at.isoformat() if r.approved_at else '',
                    r.original_reservation_id or '',
                    r.notes,
                    r.created_at.isoformat(),
                    r.updated_at.isoformat(),
                ])
        
        return filepath

    @staticmethod
    def export_inventory_check_to_json(check: InventoryCheck,
                                        conflicts: List[InventoryCheckConflict],
                                        filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = {
            'summary': check.to_dict(),
            'conflicts': [c.to_dict() for c in conflicts],
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_inventory_check_to_csv(check: InventoryCheck,
                                       conflicts: List[InventoryCheckConflict],
                                       filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            writer.writerow(['=== 盘点汇总 ==='])
            writer.writerow(['盘点名称', check.name])
            writer.writerow(['盘点人', check.checker])
            writer.writerow(['盘点日期', check.check_date.isoformat()])
            writer.writerow(['总条目数', check.total_items])
            writer.writerow(['匹配数量', check.matched_count])
            writer.writerow(['冲突数量', check.conflict_count])
            writer.writerow(['状态', check.status.value])
            writer.writerow(['可撤销', '是' if check.can_undo else '否'])
            writer.writerow(['创建时间', check.created_at.isoformat()])
            writer.writerow(['完成时间', check.completed_at.isoformat() if check.completed_at else ''])
            writer.writerow(['备注', check.notes])
            writer.writerow([])
            
            writer.writerow(['=== 冲突明细 ==='])
            writer.writerow([
                '冲突类型', '序列号', '仪器名称', '系统值', '盘点值',
                '处理结论', '处理人', '处理时间', '备注'
            ])
            
            for c in conflicts:
                writer.writerow([
                    c.conflict_type.value,
                    c.serial_number,
                    c.instrument_name,
                    c.expected_value,
                    c.actual_value,
                    c.resolution.value,
                    c.resolved_by or '',
                    c.resolved_at.isoformat() if c.resolved_at else '',
                    c.notes,
                ])
        
        return filepath

    @staticmethod
    def export_inventory_checks_summary_to_json(checks: List[InventoryCheck],
                                                 filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        data = [check.to_dict() for check in checks]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)
        
        return filepath

    @staticmethod
    def export_inventory_checks_summary_to_csv(checks: List[InventoryCheck],
                                                filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))
        
        headers = [
            '盘点名称', '盘点人', '盘点日期', '总条目数', '匹配数量',
            '冲突数量', '状态', '可撤销', '创建时间', '完成时间', '备注'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for check in checks:
                writer.writerow([
                    check.name,
                    check.checker,
                    check.check_date.isoformat(),
                    check.total_items,
                    check.matched_count,
                    check.conflict_count,
                    check.status.value,
                    '是' if check.can_undo else '否',
                    check.created_at.isoformat(),
                    check.completed_at.isoformat() if check.completed_at else '',
                    check.notes,
                ])
        
        return filepath

    @staticmethod
    def export_calibration_schedules_summary_to_json(schedules: List[CalibrationSchedule],
                                                      filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        data = [schedule.to_dict() for schedule in schedules]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)

        return filepath

    @staticmethod
    def export_calibration_schedules_summary_to_csv(schedules: List[CalibrationSchedule],
                                                     filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        headers = [
            '排程名称', '创建人', '计划日期', '总条目', '已完成', '冲突数',
            '状态', '可撤销', '创建时间', '完成时间', '备注'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for schedule in schedules:
                writer.writerow([
                    schedule.name,
                    schedule.creator,
                    schedule.plan_date.isoformat(),
                    schedule.total_items,
                    schedule.completed_count,
                    schedule.conflict_count,
                    schedule.status.value,
                    '是' if schedule.can_undo else '否',
                    schedule.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    schedule.completed_at.strftime('%Y-%m-%d %H:%M:%S') if schedule.completed_at else '',
                    schedule.notes,
                ])

        return filepath

    @staticmethod
    def export_calibration_schedule_items_to_json(items: List[CalibrationScheduleItem],
                                                   filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        data = [item.to_dict() for item in items]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)

        return filepath

    @staticmethod
    def export_calibration_schedule_items_to_csv(items: List[CalibrationScheduleItem],
                                                  filepath: str,
                                                  instruments: Optional[List[Instrument]] = None) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        instr_map = {i.id: i for i in instruments} if instruments else {}

        headers = [
            'ID', '排程ID', '仪器ID', '仪器名称', '序列号', '计划校准日期',
            '校准机构', '证书编号', '实际校准日期', '下次校准日期',
            '结果', '状态', '处理人', '处理时间', '备注'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for item in items:
                writer.writerow([
                    item.id,
                    item.schedule_id,
                    item.instrument_id,
                    item.instrument_name,
                    item.serial_number,
                    item.planned_date.isoformat(),
                    item.calibration_agency,
                    item.certificate_number,
                    item.actual_calibration_date.isoformat() if item.actual_calibration_date else '',
                    item.next_calibration_date.isoformat() if item.next_calibration_date else '',
                    item.result,
                    item.status.value,
                    item.processed_by or '',
                    item.processed_at.strftime('%Y-%m-%d %H:%M:%S') if item.processed_at else '',
                    item.notes,
                ])

        return filepath

    @staticmethod
    def export_calibration_schedule_conflicts_to_json(conflicts: List[CalibrationScheduleConflict],
                                                       filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        data = [conflict.to_dict() for conflict in conflicts]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)

        return filepath

    @staticmethod
    def export_calibration_schedule_conflicts_to_csv(conflicts: List[CalibrationScheduleConflict],
                                                      filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        headers = [
            '冲突类型', '序列号', '仪器名称', '系统值', '实际值',
            '处理结论', '处理人', '处理时间', '备注'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for c in conflicts:
                writer.writerow([
                    c.conflict_type.value,
                    c.serial_number,
                    c.instrument_name or '未知',
                    c.expected_value,
                    c.actual_value,
                    c.resolution.value,
                    c.resolved_by or '',
                    c.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if c.resolved_at else '',
                    c.notes,
                ])

        return filepath

    @staticmethod
    def export_overdue_calibration_items_to_json(items: List[CalibrationScheduleItem],
                                                  filepath: str) -> str:
        return DataExporter.export_calibration_schedule_items_to_json(items, filepath)

    @staticmethod
    def export_overdue_calibration_items_to_csv(items: List[CalibrationScheduleItem],
                                                 filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        headers = [
            '仪器名称', '序列号', '计划校准日期', '逾期天数',
            '校准机构', '状态', '备注'
        ]

        today = date.today()

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for item in items:
                overdue_days = (today - item.planned_date).days if item.planned_date < today else 0
                writer.writerow([
                    item.instrument_name,
                    item.serial_number,
                    item.planned_date.isoformat(),
                    overdue_days,
                    item.calibration_agency,
                    item.status.value,
                    item.notes,
                ])

        return filepath

    @staticmethod
    def export_calibration_schedule_full_to_csv(schedule: CalibrationSchedule,
                                                 items: List[CalibrationScheduleItem],
                                                 conflicts: List[CalibrationScheduleConflict],
                                                 filepath: str) -> str:
        DataExporter._ensure_dir(os.path.dirname(filepath))

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            writer.writerow(['=== 校准排程汇总 ==='])
            writer.writerow(['排程名称', schedule.name])
            writer.writerow(['创建人', schedule.creator])
            writer.writerow(['计划日期', schedule.plan_date.isoformat()])
            writer.writerow(['总条目数', schedule.total_items])
            writer.writerow(['已完成数', schedule.completed_count])
            writer.writerow(['冲突数量', schedule.conflict_count])
            writer.writerow(['状态', schedule.status.value])
            writer.writerow(['可撤销', '是' if schedule.can_undo else '否'])
            writer.writerow(['创建时间', schedule.created_at.strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['完成时间', schedule.completed_at.strftime('%Y-%m-%d %H:%M:%S') if schedule.completed_at else ''])
            writer.writerow(['备注', schedule.notes])
            writer.writerow([])

            writer.writerow(['=== 校准计划明细 ==='])
            writer.writerow([
                '仪器名称', '序列号', '计划日期', '校准机构', '证书编号',
                '实际校准日期', '下次校准日期', '结果', '状态', '处理人'
            ])
            for item in items:
                writer.writerow([
                    item.instrument_name,
                    item.serial_number,
                    item.planned_date.isoformat(),
                    item.calibration_agency,
                    item.certificate_number,
                    item.actual_calibration_date.isoformat() if item.actual_calibration_date else '',
                    item.next_calibration_date.isoformat() if item.next_calibration_date else '',
                    item.result,
                    item.status.value,
                    item.processed_by or '',
                ])
            writer.writerow([])

            writer.writerow(['=== 冲突明细 ==='])
            writer.writerow([
                '冲突类型', '序列号', '仪器名称', '系统值', '实际值',
                '处理结论', '处理人', '处理时间', '备注'
            ])
            for c in conflicts:
                writer.writerow([
                    c.conflict_type.value,
                    c.serial_number,
                    c.instrument_name or '未知',
                    c.expected_value,
                    c.actual_value,
                    c.resolution.value,
                    c.resolved_by or '',
                    c.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if c.resolved_at else '',
                    c.notes,
                ])

        return filepath

    @staticmethod
    def generate_export_filename(prefix: str, format_type: str, 
                                  export_dir: str) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}_{timestamp}.{format_type}"
        return os.path.join(export_dir, filename)
