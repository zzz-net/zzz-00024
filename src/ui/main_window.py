import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date, datetime
import os
from typing import Optional

from ..models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    User, UserRole,
)
from ..services import InstrumentService
from ..storage import DataManager, DataExporter
from .dialogs import (
    InstrumentDialog,
    BorrowDialog,
    ReturnDialog,
    CalibrationDialog,
    HistoryDialog,
    UserDialog,
    SettingsDialog,
    ExportDialog,
    InventoryCheckDialog,
    ConflictResolveDialog,
    InventoryCheckHistoryDialog,
    InventoryCheckDetailDialog,
    CalibrationScheduleDialog,
    CalibrationScheduleHistoryDialog,
    CalibrationScheduleDetailDialog,
    ReservationDialog,
    MaintenanceOrderDialog,
    MaintenanceOrderListDialog,
    MaintenanceOrderDetailDialog,
)


class MainWindow(ttk.Frame):
    def __init__(self, parent: tk.Tk, data_manager: DataManager):
        super().__init__(parent, padding="10")
        self.parent = parent
        self.data_manager = data_manager
        self.service = InstrumentService(data_manager)
        self.selected_instrument: Optional[Instrument] = None
        
        settings = self.service.get_settings()
        self.status_filter_var = tk.StringVar(value=settings.get('last_filters', {}).get('status', ''))
        self.category_filter_var = tk.StringVar(value=settings.get('last_filters', {}).get('category', ''))
        self.search_var = tk.StringVar(value=settings.get('last_filters', {}).get('search', ''))
        
        self._create_toolbar()
        self._create_filters()
        self._create_instrument_list()
        self._create_statusbar()
        self._create_styles()
        
        self.refresh_instruments()
        self._update_user_display()

    def _create_styles(self):
        style = ttk.Style()
        style.configure("Status.TLabel", foreground="gray")
        style.configure("Available.TLabel", foreground="green")
        style.configure("Borrowed.TLabel", foreground="blue")
        style.configure("Maintenance.TLabel", foreground="orange")
        style.configure("Due.TLabel", foreground="darkorange")
        style.configure("Expired.TLabel", foreground="red")
        style.configure("Frozen.TLabel", foreground="purple")

    def _create_toolbar(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        left_frame = ttk.Frame(toolbar)
        left_frame.pack(side=tk.LEFT)
        
        ttk.Button(left_frame, text="新增仪器", command=self._on_add_instrument).pack(side=tk.LEFT, padx=(0, 5))
        self.edit_btn = ttk.Button(left_frame, text="编辑仪器", command=self._on_edit_instrument, state=tk.DISABLED)
        self.edit_btn.pack(side=tk.LEFT, padx=5)
        self.delete_btn = ttk.Button(left_frame, text="删除仪器", command=self._on_delete_instrument, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(left_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Button(left_frame, text="批量盘点", command=self._on_inventory_check).pack(side=tk.LEFT, padx=5)
        self.undo_check_btn = ttk.Button(left_frame, text="撤销盘点", command=self._on_undo_check, state=tk.DISABLED)
        self.undo_check_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="盘点历史", command=self._on_check_history).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(left_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Button(left_frame, text="校准排程", command=self._on_calibration_schedule).pack(side=tk.LEFT, padx=5)
        self.undo_calibration_btn = ttk.Button(left_frame, text="撤销校准", command=self._on_undo_calibration, state=tk.DISABLED)
        self.undo_calibration_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="排程历史", command=self._on_calibration_schedule_history).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(left_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Button(left_frame, text="预约管理", command=self._on_reservation_management).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(left_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.maintenance_btn = ttk.Button(left_frame, text="发起维修", command=self._on_create_maintenance, state=tk.DISABLED)
        self.maintenance_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="维修管理", command=self._on_maintenance_management).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(left_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.borrow_btn = ttk.Button(left_frame, text="借出", command=self._on_borrow, state=tk.DISABLED)
        self.borrow_btn.pack(side=tk.LEFT, padx=5)
        self.return_btn = ttk.Button(left_frame, text="归还", command=self._on_return, state=tk.DISABLED)
        self.return_btn.pack(side=tk.LEFT, padx=5)
        self.calibrate_btn = ttk.Button(left_frame, text="校准录入", command=self._on_calibrate, state=tk.DISABLED)
        self.calibrate_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(left_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.freeze_btn = ttk.Button(left_frame, text="冻结", command=self._on_freeze, state=tk.DISABLED)
        self.freeze_btn.pack(side=tk.LEFT, padx=5)
        self.unfreeze_btn = ttk.Button(left_frame, text="解冻", command=self._on_unfreeze, state=tk.DISABLED)
        self.unfreeze_btn.pack(side=tk.LEFT, padx=5)
        self.history_btn = ttk.Button(left_frame, text="查看历史", command=self._on_history, state=tk.DISABLED)
        self.history_btn.pack(side=tk.LEFT, padx=5)
        
        right_frame = ttk.Frame(toolbar)
        right_frame.pack(side=tk.RIGHT)
        
        ttk.Button(right_frame, text="导出", command=self._on_export).pack(side=tk.LEFT, padx=5)
        ttk.Button(right_frame, text="设置", command=self._on_settings).pack(side=tk.LEFT, padx=5)
        self.user_btn = ttk.Button(right_frame, text="用户", command=self._on_user)
        self.user_btn.pack(side=tk.LEFT, padx=5)

    def _create_filters(self):
        filter_frame = ttk.LabelFrame(self, text="筛选条件", padding="10")
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        grid = ttk.Frame(filter_frame)
        grid.pack(fill=tk.X)
        
        ttk.Label(grid, text="状态:").grid(row=0, column=0, sticky=tk.W)
        status_values = [""] + [s.value for s in InstrumentStatus]
        status_combo = ttk.Combobox(grid, textvariable=self.status_filter_var, 
                                     values=status_values, state="readonly", width=15)
        status_combo.grid(row=0, column=1, padx=(5, 20))
        status_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_instruments())
        
        ttk.Label(grid, text="类别:").grid(row=0, column=2, sticky=tk.W)
        category_values = [""] + [c.value for c in InstrumentCategory]
        category_combo = ttk.Combobox(grid, textvariable=self.category_filter_var,
                                       values=category_values, state="readonly", width=15)
        category_combo.grid(row=0, column=3, padx=(5, 20))
        category_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_instruments())
        
        ttk.Label(grid, text="搜索:").grid(row=0, column=4, sticky=tk.W)
        search_entry = ttk.Entry(grid, textvariable=self.search_var, width=30)
        search_entry.grid(row=0, column=5, padx=(5, 10))
        search_entry.bind("<KeyRelease>", lambda e: self.refresh_instruments())
        
        ttk.Button(grid, text="重置", command=self._on_reset_filters).grid(row=0, column=6)

    def _create_instrument_list(self):
        list_frame = ttk.LabelFrame(self, text="仪器列表", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("name", "category", "model", "serial_number", "location", 
                   "manager", "calibration_due", "status", "borrower")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        headings = [
            ("name", "仪器名称", 150),
            ("category", "类别", 100),
            ("model", "型号", 150),
            ("serial_number", "序列号", 120),
            ("location", "存放位置", 120),
            ("manager", "负责人", 80),
            ("calibration_due", "校准到期日", 100),
            ("status", "状态", 100),
            ("borrower", "当前借用人", 100),
        ]
        
        for col, text, width in headings:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select_instrument)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _create_statusbar(self):
        self.statusbar = ttk.Frame(self)
        self.statusbar.pack(fill=tk.X, pady=(10, 0))
        
        self.count_label = ttk.Label(self.statusbar, text="", style="Status.TLabel")
        self.count_label.pack(side=tk.LEFT)
        
        self.user_label = ttk.Label(self.statusbar, text="", style="Status.TLabel")
        self.user_label.pack(side=tk.RIGHT)

    def _update_user_display(self):
        user = self.service.get_current_user()
        self.user_label.config(text=f"当前用户: {user.display_name} ({user.role.value})")

    def _save_filters(self):
        settings = self.service.get_settings()
        settings['last_filters'] = {
            'status': self.status_filter_var.get(),
            'category': self.category_filter_var.get(),
            'search': self.search_var.get(),
        }
        self.service.update_settings(settings)

    def refresh_instruments(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        status_filter = self.status_filter_var.get() or None
        category_filter = self.category_filter_var.get() or None
        search_text = self.search_var.get() or None
        
        instruments = self.service.get_instruments(
            status_filter=status_filter,
            category_filter=category_filter,
            search_text=search_text,
        )
        
        user = self.service.get_current_user()
        
        for instr in instruments:
            cal_due = instr.calibration_due_date.isoformat() if instr.calibration_due_date else "-"
            
            borrower = ""
            if instr.status == InstrumentStatus.BORROWED:
                active_record = self.service.get_active_borrow_record(instr.id)
                if active_record:
                    borrower = active_record.borrower
            
            status_tag = self._get_status_tag(instr.status)
            
            self.tree.insert("", tk.END, iid=instr.id, values=(
                instr.name,
                instr.category.value,
                instr.model,
                instr.serial_number,
                instr.location,
                instr.manager,
                cal_due,
                instr.status.value,
                borrower,
            ), tags=(status_tag,))
        
        self.tree.tag_configure("Available", foreground="green")
        self.tree.tag_configure("Borrowed", foreground="blue")
        self.tree.tag_configure("Maintenance", foreground="orange")
        self.tree.tag_configure("CalibrationDue", foreground="darkorange")
        self.tree.tag_configure("CalibrationExpired", foreground="red")
        self.tree.tag_configure("Frozen", foreground="purple")
        
        self.count_label.config(text=f"共 {len(instruments)} 台仪器")
        self._save_filters()
        self._update_button_states()

    def _get_status_tag(self, status: InstrumentStatus) -> str:
        mapping = {
            InstrumentStatus.AVAILABLE: "Available",
            InstrumentStatus.BORROWED: "Borrowed",
            InstrumentStatus.MAINTENANCE: "Maintenance",
            InstrumentStatus.CALIBRATION_DUE: "CalibrationDue",
            InstrumentStatus.CALIBRATION_EXPIRED: "CalibrationExpired",
            InstrumentStatus.FROZEN: "Frozen",
        }
        return mapping.get(status, "Available")

    def _on_select_instrument(self, event):
        selection = self.tree.selection()
        if selection:
            instr_id = selection[0]
            self.selected_instrument = self.service.get_instrument_by_id(instr_id)
        else:
            self.selected_instrument = None
        self._update_button_states()

    def _on_double_click(self, event):
        if self.selected_instrument:
            self._on_history()

    def _update_button_states(self):
        has_selection = self.selected_instrument is not None
        instr = self.selected_instrument
        user = self.service.get_current_user()
        
        self.edit_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        self.delete_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        self.history_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        
        can_undo, _ = self.service.can_undo_last_check()
        self.undo_check_btn.config(state=tk.NORMAL if can_undo else tk.DISABLED)
        
        can_undo_cal, _ = self.service.can_undo_last_calibration_schedule()
        self.undo_calibration_btn.config(state=tk.NORMAL if can_undo_cal and user.can_calibrate() else tk.DISABLED)
        
        if has_selection and instr:
            has_active_maint = self.service.has_active_maintenance(instr.id)
            can_borrow, _ = instr.can_borrow()
            self.borrow_btn.config(state=tk.NORMAL if can_borrow and not has_active_maint else tk.DISABLED)
            
            active_record = self.service.get_active_borrow_record(instr.id)
            self.return_btn.config(state=tk.NORMAL if active_record else tk.DISABLED)
            
            self.calibrate_btn.config(state=tk.NORMAL if user.can_calibrate() and not has_active_maint else tk.DISABLED)
            self.freeze_btn.config(state=tk.NORMAL if user.can_freeze() and 
                                   instr.status not in [InstrumentStatus.FROZEN, InstrumentStatus.BORROWED]
                                   and not has_active_maint else tk.DISABLED)
            self.unfreeze_btn.config(state=tk.NORMAL if user.can_unfreeze_maintenance() and 
                                     instr.status == InstrumentStatus.FROZEN else tk.DISABLED)
            
            can_create_maint = (instr.status not in [InstrumentStatus.BORROWED] 
                               and not has_active_maint)
            self.maintenance_btn.config(state=tk.NORMAL if can_create_maint else tk.DISABLED)
        else:
            self.borrow_btn.config(state=tk.DISABLED)
            self.return_btn.config(state=tk.DISABLED)
            self.calibrate_btn.config(state=tk.DISABLED)
            self.freeze_btn.config(state=tk.DISABLED)
            self.unfreeze_btn.config(state=tk.DISABLED)

    def _on_reset_filters(self):
        self.status_filter_var.set("")
        self.category_filter_var.set("")
        self.search_var.set("")
        self.refresh_instruments()

    def _on_add_instrument(self):
        dialog = InstrumentDialog(self.parent)
        if dialog.show() and dialog.result:
            data = dialog.result
            self.service.create_instrument(
                name=data['name'],
                category=data['category'],
                model=data['model'],
                serial_number=data['serial_number'],
                location=data['location'],
                manager=data['manager'],
                calibration_due_date=data['calibration_due_date'],
                description=data['description'],
            )
            self.refresh_instruments()
            messagebox.showinfo("成功", "仪器添加成功", parent=self.parent)

    def _on_edit_instrument(self):
        if not self.selected_instrument:
            return
        
        dialog = InstrumentDialog(self.parent, self.selected_instrument)
        if dialog.show() and dialog.result:
            data = dialog.result
            self.service.update_instrument(self.selected_instrument, **data)
            self.refresh_instruments()
            messagebox.showinfo("成功", "仪器信息更新成功", parent=self.parent)

    def _on_delete_instrument(self):
        if not self.selected_instrument:
            return
        
        if not messagebox.askyesno("确认删除", f"确定要删除仪器 '{self.selected_instrument.name}' 吗？\n"
                                   f"相关的借用记录和操作历史也将保留。", parent=self.parent):
            return
        
        self.service.delete_instrument(self.selected_instrument.id)
        self.selected_instrument = None
        self.refresh_instruments()
        messagebox.showinfo("成功", "仪器删除成功", parent=self.parent)

    def _on_borrow(self):
        if not self.selected_instrument:
            return
        
        can_borrow, reason = self.selected_instrument.can_borrow()
        if not can_borrow:
            messagebox.showerror("借出失败", reason, parent=self.parent)
            return
        
        dialog = BorrowDialog(self.parent, self.selected_instrument)
        if dialog.show() and dialog.result:
            data = dialog.result
            success, message, record = self.service.borrow_instrument(
                instrument_id=self.selected_instrument.id,
                borrower=data['borrower'],
                borrower_department=data['borrower_department'],
                borrow_date=data['borrow_date'],
                expected_return_date=data['expected_return_date'],
                purpose=data['purpose'],
                notes=data['notes'],
            )
            if success:
                self.refresh_instruments()
                messagebox.showinfo("成功", message, parent=self.parent)
            else:
                messagebox.showerror("借出失败", message, parent=self.parent)

    def _on_return(self):
        if not self.selected_instrument:
            return
        
        active_record = self.service.get_active_borrow_record(self.selected_instrument.id)
        if not active_record:
            messagebox.showerror("错误", "该仪器没有未归还的借用记录", parent=self.parent)
            return
        
        can_return, reason = active_record.can_return()
        if not can_return:
            messagebox.showerror("归还失败", reason, parent=self.parent)
            return
        
        dialog = ReturnDialog(self.parent, self.selected_instrument, active_record)
        if dialog.show() and dialog.result:
            data = dialog.result
            success, message, record = self.service.return_instrument(
                borrow_record_id=active_record.id,
                return_date=data['return_date'],
                notes=data['notes'],
            )
            if success:
                self.refresh_instruments()
                messagebox.showinfo("成功", message, parent=self.parent)
            else:
                messagebox.showerror("归还失败", message, parent=self.parent)

    def _on_calibrate(self):
        if not self.selected_instrument:
            return
        
        user = self.service.get_current_user()
        if not user.can_calibrate():
            messagebox.showerror("权限不足", "您没有校准仪器的权限", parent=self.parent)
            return
        
        dialog = CalibrationDialog(self.parent, self.selected_instrument)
        if dialog.show() and dialog.result:
            data = dialog.result
            success, message, record = self.service.calibrate_instrument(
                instrument_id=self.selected_instrument.id,
                calibration_date=data['calibration_date'],
                next_calibration_date=data['next_calibration_date'],
                certificate_number=data['certificate_number'],
                calibration_agency=data['calibration_agency'],
                result=data['result'],
                notes=data['notes'],
            )
            if success:
                self.refresh_instruments()
                messagebox.showinfo("成功", message, parent=self.parent)
            else:
                messagebox.showerror("校准录入失败", message, parent=self.parent)

    def _on_freeze(self):
        if not self.selected_instrument:
            return
        
        reason = simpledialog.askstring("冻结原因", "请输入冻结原因:", parent=self.parent)
        if reason is None:
            return
        
        success, message = self.service.freeze_instrument(
            instrument_id=self.selected_instrument.id,
            reason=reason,
        )
        if success:
            self.refresh_instruments()
            messagebox.showinfo("成功", message, parent=self.parent)
        else:
            messagebox.showerror("冻结失败", message, parent=self.parent)

    def _on_unfreeze(self):
        if not self.selected_instrument:
            return
        
        reason = simpledialog.askstring("解冻原因", "请输入解冻原因:", parent=self.parent)
        if reason is None:
            return
        
        success, message = self.service.unfreeze_instrument(
            instrument_id=self.selected_instrument.id,
            reason=reason,
        )
        if success:
            self.refresh_instruments()
            messagebox.showinfo("成功", message, parent=self.parent)
        else:
            messagebox.showerror("解冻失败", message, parent=self.parent)

    def _on_history(self):
        if not self.selected_instrument:
            return
        
        dialog = HistoryDialog(self.parent, self.selected_instrument, self.service)
        dialog.show()

    def _on_user(self):
        current_user = self.service.get_current_user()
        dialog = UserDialog(self.parent, current_user)
        if dialog.show() and dialog.result:
            self.service.set_current_user(dialog.result)
            self._update_user_display()
            self._update_button_states()

    def _on_settings(self):
        settings = self.service.get_settings()
        dialog = SettingsDialog(self.parent, settings)
        if dialog.show() and dialog.result:
            self.service.update_settings(dialog.result)

    def _on_inventory_check(self):
        from .dialogs import InventoryCheckDialog
        dialog = InventoryCheckDialog(self.parent, self.service)
        if dialog.show():
            self.refresh_instruments()
            self._update_button_states()
            messagebox.showinfo("成功", "盘点完成", parent=self.parent)

    def _on_undo_check(self):
        can_undo, check = self.service.can_undo_last_check()
        if not can_undo or not check:
            messagebox.showinfo("提示", "没有可撤销的盘点记录", parent=self.parent)
            return
        
        confirm = messagebox.askyesno(
            "确认撤销",
            f"确定要撤销盘点 \"{check.name}\" 的位置更新吗？\n"
            f"这将恢复 {len(check.undo_snapshot.get('updates', [])) if check.undo_snapshot else 0} 条仪器位置。",
            parent=self.parent
        )
        if not confirm:
            return
        
        success, message, _ = self.service.undo_last_inventory_check()
        if success:
            self.refresh_instruments()
            self._update_button_states()
            messagebox.showinfo("成功", message, parent=self.parent)
        else:
            messagebox.showerror("撤销失败", message, parent=self.parent)

    def _on_check_history(self):
        from .dialogs import InventoryCheckHistoryDialog
        dialog = InventoryCheckHistoryDialog(self.parent, self.service)
        dialog.show()

    def _on_export(self):
        settings = self.service.get_settings()
        export_dir = settings.get('export_dir', '')
        
        dialog = ExportDialog(self.parent, export_dir)
        if dialog.show() and dialog.result:
            data = dialog.result
            export_type = data['export_type']
            format_type = data['format']
            
            try:
                if export_type == "all":
                    filename = DataExporter.generate_export_filename("all_data", format_type, export_dir)
                    instruments = self.service.get_instruments()
                    borrows = self.service.get_borrow_records()
                    calibrations = self.service.get_calibration_records()
                    histories = self.service.get_operation_histories()
                    
                    if format_type == "json":
                        filepath = DataExporter.export_all_to_json(
                            instruments, borrows, calibrations, histories, filename
                        )
                    else:
                        messagebox.showerror("错误", "全部数据导出仅支持JSON格式", parent=self.parent)
                        return
                else:
                    prefix_map = {
                        "instruments": "instruments",
                        "borrows": "borrow_records",
                        "calibrations": "calibration_records",
                        "histories": "operation_histories",
                        "checks_summary": "inventory_checks_summary",
                        "calibration_schedules_summary": "calibration_schedules_summary",
                        "calibration_schedule_items": "calibration_schedule_items",
                        "calibration_schedule_conflicts": "calibration_schedule_conflicts",
                        "overdue_calibration_items": "overdue_calibration_items",
                    }
                    prefix = prefix_map.get(export_type, "export")
                    filename = DataExporter.generate_export_filename(prefix, format_type, export_dir)
                    
                    instruments = self.service.get_instruments()
                    
                    if export_type == "instruments":
                        if format_type == "csv":
                            filepath = DataExporter.export_instruments_to_csv(instruments, filename)
                        else:
                            filepath = DataExporter.export_instruments_to_json(instruments, filename)
                    elif export_type == "borrows":
                        records = self.service.get_borrow_records()
                        if format_type == "csv":
                            filepath = DataExporter.export_borrow_records_to_csv(records, filename, instruments)
                        else:
                            filepath = DataExporter.export_borrow_records_to_json(records, filename)
                    elif export_type == "calibrations":
                        records = self.service.get_calibration_records()
                        if format_type == "csv":
                            filepath = DataExporter.export_calibration_records_to_csv(records, filename, instruments)
                        else:
                            filepath = DataExporter.export_calibration_records_to_json(records, filename)
                    elif export_type == "histories":
                        records = self.service.get_operation_histories()
                        if format_type == "csv":
                            filepath = DataExporter.export_operation_histories_to_csv(records, filename, instruments)
                        else:
                            filepath = DataExporter.export_operation_histories_to_json(records, filename)
                    elif export_type == "checks_summary":
                        records = self.service.get_inventory_checks()
                        if format_type == "csv":
                            filepath = DataExporter.export_inventory_checks_summary_to_csv(records, filename)
                        else:
                            filepath = DataExporter.export_inventory_checks_summary_to_json(records, filename)
                    elif export_type == "calibration_schedules_summary":
                        records = self.service.get_calibration_schedules()
                        if format_type == "csv":
                            filepath = DataExporter.export_calibration_schedules_summary_to_csv(records, filename)
                        else:
                            filepath = DataExporter.export_calibration_schedules_summary_to_json(records, filename)
                    elif export_type == "calibration_schedule_items":
                        records = self.service.get_calibration_schedule_items()
                        if format_type == "csv":
                            filepath = DataExporter.export_calibration_schedule_items_to_csv(records, filename, instruments)
                        else:
                            filepath = DataExporter.export_calibration_schedule_items_to_json(records, filename)
                    elif export_type == "calibration_schedule_conflicts":
                        records = self.service.get_calibration_schedule_conflicts()
                        if format_type == "csv":
                            filepath = DataExporter.export_calibration_schedule_conflicts_to_csv(records, filename)
                        else:
                            filepath = DataExporter.export_calibration_schedule_conflicts_to_json(records, filename)
                    elif export_type == "overdue_calibration_items":
                        records = service.get_overdue_calibration_items()
                        if format_type == "csv":
                            filepath = DataExporter.export_overdue_calibration_items_to_csv(records, filename)
                        else:
                            filepath = DataExporter.export_overdue_calibration_items_to_json(records, filename)
                
                messagebox.showinfo("导出成功", f"数据已导出到:\n{filepath}", parent=self.parent)
                if hasattr(os, 'startfile'):
                    try:
                        os.startfile(os.path.dirname(filepath))
                    except Exception:
                        pass
            except Exception as e:
                messagebox.showerror("导出失败", f"导出时发生错误: {str(e)}", parent=self.parent)

    def _on_calibration_schedule(self):
        from .dialogs import CalibrationScheduleDialog
        user = self.service.get_current_user()
        is_admin = user.can_calibrate()
        dialog = CalibrationScheduleDialog(self.parent, self.service, is_admin=is_admin)
        if dialog.show():
            self.refresh_instruments()
            self._update_button_states()
            messagebox.showinfo("成功", "校准排程处理完成", parent=self.parent)

    def _on_undo_calibration(self):
        can_undo, item = self.service.can_undo_last_calibration_schedule()
        if not can_undo or not item:
            messagebox.showinfo("提示", "没有可撤销的校准处理", parent=self.parent)
            return
        
        user = self.service.get_current_user()
        if not user.can_calibrate():
            messagebox.showerror("权限不足", "您没有撤销校准的权限", parent=self.parent)
            return
        
        confirm = messagebox.askyesno(
            "确认撤销",
            f"确定要撤销仪器 \"{item.instrument_name}\" 的校准处理吗？\n"
            f"校准日期: {item.actual_calibration_date.isoformat() if item.actual_calibration_date else 'N/A'}",
            parent=self.parent
        )
        if not confirm:
            return
        
        success, message, _ = self.service.undo_last_calibration_completion()
        if success:
            self.refresh_instruments()
            self._update_button_states()
            messagebox.showinfo("成功", message, parent=self.parent)
        else:
            messagebox.showerror("撤销失败", message, parent=self.parent)

    def _on_calibration_schedule_history(self):
        from .dialogs import CalibrationScheduleHistoryDialog
        user = self.service.get_current_user()
        is_admin = user.can_calibrate()
        dialog = CalibrationScheduleHistoryDialog(self.parent, self.service, is_admin=is_admin)
        dialog.show()

    def _on_reservation_management(self):
        from .dialogs import ReservationDialog
        user = self.service.get_current_user()
        is_admin = user.can_manage_reservations()
        dialog = ReservationDialog(self.parent, self.service, user=user, is_admin=is_admin)
        dialog.show()

    def _on_create_maintenance(self):
        if not self.selected_instrument:
            return
        
        dialog = MaintenanceOrderDialog(self.parent, self.selected_instrument)
        if dialog.show() and dialog.result:
            data = dialog.result
            success, message, order = self.service.create_maintenance_order(
                instrument_id=self.selected_instrument.id,
                fault_description=data['fault_description'],
                priority=data['priority'],
                expected_completion_date=data.get('expected_completion_date'),
                assignee=data.get('assignee'),
            )
            if success:
                self.refresh_instruments()
                self._update_button_states()
                messagebox.showinfo("成功", message, parent=self.parent)
            else:
                messagebox.showerror("创建失败", message, parent=self.parent)

    def _on_maintenance_management(self):
        user = self.service.get_current_user()
        is_admin = user.role.value in ["维修人员", "管理员"]
        dialog = MaintenanceOrderListDialog(self.parent, self.service, user=user, is_admin=is_admin)
        if dialog.show():
            self.refresh_instruments()
            self._update_button_states()
