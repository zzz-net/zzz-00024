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
        if isinstance(obj, (InstrumentStatus, InstrumentCategory, BorrowStatus, OperationType)):
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
    def generate_export_filename(prefix: str, format_type: str, 
                                  export_dir: str) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}_{timestamp}.{format_type}"
        return os.path.join(export_dir, filename)
