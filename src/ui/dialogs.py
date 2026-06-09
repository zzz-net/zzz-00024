import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
from typing import Optional, Callable
import os

from ..models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    User, UserRole,
    InventoryCheck, InventoryCheckStatus,
    InventoryCheckConflict, ConflictType, ConflictResolution,
    CalibrationSchedule, CalibrationScheduleStatus,
    CalibrationScheduleItem, CalibrationScheduleItemStatus,
    CalibrationScheduleConflict, CalibrationConflictType,
    CalibrationConflictResolution,
)
from ..services import InstrumentService
from ..storage import DataExporter


class BaseDialog(tk.Toplevel):
    def __init__(self, parent, title: str, size: str = "500x400"):
        super().__init__(parent)
        self.title(title)
        self.geometry(size)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None
        
        self.main_frame = ttk.Frame(self, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_content()
        self._create_buttons()
        
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _create_content(self):
        pass

    def _create_buttons(self):
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btn_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT)

    def _on_ok(self):
        self.result = True
        self.destroy()

    def _on_cancel(self):
        self.result = False
        self.destroy()

    def show(self):
        self.wait_window()
        return self.result


class InstrumentDialog(BaseDialog):
    def __init__(self, parent, instrument: Optional[Instrument] = None):
        self.instrument = instrument
        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.serial_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.manager_var = tk.StringVar()
        self.cal_date_var = tk.StringVar()
        self.description_var = tk.StringVar()
        
        if instrument:
            self.name_var.set(instrument.name)
            self.category_var.set(instrument.category.value)
            self.model_var.set(instrument.model)
            self.serial_var.set(instrument.serial_number)
            self.location_var.set(instrument.location)
            self.manager_var.set(instrument.manager)
            if instrument.calibration_due_date:
                self.cal_date_var.set(instrument.calibration_due_date.isoformat())
            self.description_var.set(instrument.description)
        
        title = "编辑仪器" if instrument else "新增仪器"
        super().__init__(parent, title, "550x500")

    def _create_content(self):
        grid = ttk.Frame(self.main_frame)
        grid.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        
        ttk.Label(grid, text="仪器名称:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.name_var, width=40).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="仪器类别:").grid(row=row, column=0, sticky=tk.W, pady=5)
        category_combo = ttk.Combobox(grid, textvariable=self.category_var, 
                                    values=[c.value for c in InstrumentCategory], 
                                    state="readonly", width=37)
        category_combo.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="型号:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.model_var, width=40).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="序列号:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.serial_var, width=40).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="存放位置:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.location_var, width=40).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="负责人:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.manager_var, width=40).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="校准到期日:").grid(row=row, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(grid)
        date_frame.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        ttk.Entry(date_frame, textvariable=self.cal_date_var, width=20).pack(side=tk.LEFT)
        ttk.Label(date_frame, text="(格式: YYYY-MM-DD)").pack(side=tk.LEFT, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="描述:").grid(row=row, column=0, sticky=tk.NW, pady=5)
        desc_text = tk.Text(grid, height=4, width=40)
        desc_text.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        if self.description_var.get():
            desc_text.insert("1.0", self.description_var.get())
        self.desc_text = desc_text
        row += 1
        
        grid.columnconfigure(1, weight=1)

    def _on_ok(self):
        if not self.name_var.get().strip():
            messagebox.showerror("错误", "请输入仪器名称", parent=self)
            return
        
        if not self.category_var.get():
            messagebox.showerror("错误", "请选择仪器类别", parent=self)
            return
        
        cal_date = None
        if self.cal_date_var.get().strip():
            try:
                cal_date = date.fromisoformat(self.cal_date_var.get().strip())
            except ValueError:
                messagebox.showerror("错误", "日期格式不正确，请使用YYYY-MM-DD格式", parent=self)
                return
        
        self.result = {
            'name': self.name_var.get().strip(),
            'category': InstrumentCategory(self.category_var.get()),
            'model': self.model_var.get().strip(),
            'serial_number': self.serial_var.get().strip(),
            'location': self.location_var.get().strip(),
            'manager': self.manager_var.get().strip(),
            'calibration_due_date': cal_date,
            'description': self.desc_text.get("1.0", tk.END).strip(),
        }
        super()._on_ok()


class BorrowDialog(BaseDialog):
    def __init__(self, parent, instrument: Instrument):
        self.instrument = instrument
        self.borrower_var = tk.StringVar()
        self.dept_var = tk.StringVar()
        self.borrow_date_var = tk.StringVar(value=date.today().isoformat())
        self.return_date_var = tk.StringVar(value=(date.today() + timedelta(days=7)).isoformat())
        self.purpose_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        super().__init__(parent, f"借出仪器: {instrument.name}", "500x450")

    def _create_content(self):
        info_frame = ttk.LabelFrame(self.main_frame, text="仪器信息", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(info_frame, text=f"仪器名称: {self.instrument.name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"型号: {self.instrument.model}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"序列号: {self.instrument.serial_number}").pack(anchor=tk.W)
        
        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        ttk.Label(form_frame, text="借用人:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.borrower_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="所属部门:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.dept_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="借用日期:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.borrow_date_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="预计归还日期:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.return_date_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="用途:").grid(row=row, column=0, sticky=tk.NW, pady=5)
        ttk.Entry(form_frame, textvariable=self.purpose_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="备注:").grid(row=row, column=0, sticky=tk.NW, pady=5)
        notes_text = tk.Text(form_frame, height=3, width=35)
        notes_text.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.notes_text = notes_text
        row += 1
        
        form_frame.columnconfigure(1, weight=1)

    def _on_ok(self):
        if not self.borrower_var.get().strip():
            messagebox.showerror("错误", "请输入借用人", parent=self)
            return
        
        if not self.dept_var.get().strip():
            messagebox.showerror("错误", "请输入所属部门", parent=self)
            return
        
        try:
            borrow_date = date.fromisoformat(self.borrow_date_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "借用日期格式不正确", parent=self)
            return
        
        try:
            return_date = date.fromisoformat(self.return_date_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "预计归还日期格式不正确", parent=self)
            return
        
        self.result = {
            'borrower': self.borrower_var.get().strip(),
            'borrower_department': self.dept_var.get().strip(),
            'borrow_date': borrow_date,
            'expected_return_date': return_date,
            'purpose': self.purpose_var.get().strip(),
            'notes': self.notes_text.get("1.0", tk.END).strip(),
        }
        super()._on_ok()


class ReturnDialog(BaseDialog):
    def __init__(self, parent, instrument: Instrument, borrow_record):
        self.instrument = instrument
        self.borrow_record = borrow_record
        self.return_date_var = tk.StringVar(value=date.today().isoformat())
        self.notes_var = tk.StringVar()
        super().__init__(parent, f"归还仪器: {instrument.name}", "500x350")

    def _create_content(self):
        info_frame = ttk.LabelFrame(self.main_frame, text="借用信息", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(info_frame, text=f"仪器名称: {self.instrument.name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"借用人: {self.borrow_record.borrower}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"部门: {self.borrow_record.borrower_department}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"借用日期: {self.borrow_record.borrow_date.isoformat()}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"预计归还: {self.borrow_record.expected_return_date.isoformat()}").pack(anchor=tk.W)
        
        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        ttk.Label(form_frame, text="实际归还日期:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.return_date_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="归还备注:").grid(row=row, column=0, sticky=tk.NW, pady=5)
        notes_text = tk.Text(form_frame, height=3, width=35)
        notes_text.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.notes_text = notes_text
        row += 1
        
        form_frame.columnconfigure(1, weight=1)

    def _on_ok(self):
        try:
            return_date = date.fromisoformat(self.return_date_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "归还日期格式不正确", parent=self)
            return
        
        self.result = {
            'return_date': return_date,
            'notes': self.notes_text.get("1.0", tk.END).strip(),
        }
        super()._on_ok()


class CalibrationDialog(BaseDialog):
    def __init__(self, parent, instrument: Instrument):
        self.instrument = instrument
        self.cal_date_var = tk.StringVar(value=date.today().isoformat())
        self.next_cal_date_var = tk.StringVar(value=(date.today() + timedelta(days=365)).isoformat())
        self.cert_var = tk.StringVar()
        self.agency_var = tk.StringVar()
        self.result_var = tk.StringVar(value="合格")
        self.notes_var = tk.StringVar()
        super().__init__(parent, f"校准录入: {instrument.name}", "500x450")

    def _create_content(self):
        info_frame = ttk.LabelFrame(self.main_frame, text="仪器信息", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(info_frame, text=f"仪器名称: {self.instrument.name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"型号: {self.instrument.model}").pack(anchor=tk.W)
        current_cal = self.instrument.calibration_due_date.isoformat() if self.instrument.calibration_due_date else "无"
        ttk.Label(info_frame, text=f"当前校准到期日: {current_cal}").pack(anchor=tk.W)
        
        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        ttk.Label(form_frame, text="校准日期:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.cal_date_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="下次校准日期:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.next_cal_date_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="证书编号:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.cert_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="校准机构:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=self.agency_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="校准结果:").grid(row=row, column=0, sticky=tk.W, pady=5)
        result_combo = ttk.Combobox(form_frame, textvariable=self.result_var,
                                     values=["合格", "不合格", "限制使用"],
                                     state="readonly", width=33)
        result_combo.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="备注:").grid(row=row, column=0, sticky=tk.NW, pady=5)
        notes_text = tk.Text(form_frame, height=3, width=35)
        notes_text.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.notes_text = notes_text
        row += 1
        
        form_frame.columnconfigure(1, weight=1)

    def _on_ok(self):
        try:
            cal_date = date.fromisoformat(self.cal_date_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "校准日期格式不正确", parent=self)
            return
        
        try:
            next_cal_date = date.fromisoformat(self.next_cal_date_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "下次校准日期格式不正确", parent=self)
            return
        
        if not self.cert_var.get().strip():
            messagebox.showerror("错误", "请输入证书编号", parent=self)
            return
        
        if not self.agency_var.get().strip():
            messagebox.showerror("错误", "请输入校准机构", parent=self)
            return
        
        self.result = {
            'calibration_date': cal_date,
            'next_calibration_date': next_cal_date,
            'certificate_number': self.cert_var.get().strip(),
            'calibration_agency': self.agency_var.get().strip(),
            'result': self.result_var.get().strip(),
            'notes': self.notes_text.get("1.0", tk.END).strip(),
        }
        super()._on_ok()


class HistoryDialog(BaseDialog):
    def __init__(self, parent, instrument: Instrument, service: InstrumentService):
        self.instrument = instrument
        self.service = service
        super().__init__(parent, f"操作历史: {instrument.name}", "700x500")

    def _create_content(self):
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        op_frame = ttk.Frame(notebook, padding="10")
        notebook.add(op_frame, text="操作历史")
        
        columns = ("时间", "操作类型", "操作人", "详情")
        self.op_tree = ttk.Treeview(op_frame, columns=columns, show="headings", height=15)
        self.op_tree.heading("时间", text="时间")
        self.op_tree.heading("操作类型", text="操作类型")
        self.op_tree.heading("操作人", text="操作人")
        self.op_tree.heading("详情", text="详情")
        self.op_tree.column("时间", width=150, anchor=tk.W)
        self.op_tree.column("操作类型", width=100, anchor=tk.W)
        self.op_tree.column("操作人", width=100, anchor=tk.W)
        self.op_tree.column("详情", width=300, anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(op_frame, orient=tk.VERTICAL, command=self.op_tree.yview)
        self.op_tree.configure(yscrollcommand=scrollbar.set)
        
        self.op_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        histories = self.service.get_operation_histories(self.instrument.id)
        for h in histories:
            self.op_tree.insert("", tk.END, values=(
                h.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                h.operation_type.value,
                h.operator,
                h.details,
            ))
        
        borrow_frame = ttk.Frame(notebook, padding="10")
        notebook.add(borrow_frame, text="借用记录")
        
        b_columns = ("借用日期", "借用人", "部门", "预计归还", "实际归还", "状态", "用途")
        self.borrow_tree = ttk.Treeview(borrow_frame, columns=b_columns, show="headings", height=15)
        for col in b_columns:
            self.borrow_tree.heading(col, text=col)
            self.borrow_tree.column(col, width=100, anchor=tk.W)
        self.borrow_tree.column("用途", width=150)
        
        b_scrollbar = ttk.Scrollbar(borrow_frame, orient=tk.VERTICAL, command=self.borrow_tree.yview)
        self.borrow_tree.configure(yscrollcommand=b_scrollbar.set)
        
        self.borrow_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        b_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        borrows = self.service.get_borrow_records(self.instrument.id)
        for b in borrows:
            actual_return = b.actual_return_date.isoformat() if b.actual_return_date else "-"
            self.borrow_tree.insert("", tk.END, values=(
                b.borrow_date.isoformat(),
                b.borrower,
                b.borrower_department,
                b.expected_return_date.isoformat(),
                actual_return,
                b.status.value,
                b.purpose,
            ))
        
        cal_frame = ttk.Frame(notebook, padding="10")
        notebook.add(cal_frame, text="校准记录")
        
        c_columns = ("校准日期", "下次校准", "证书编号", "机构", "结果", "备注")
        self.cal_tree = ttk.Treeview(cal_frame, columns=c_columns, show="headings", height=15)
        for col in c_columns:
            self.cal_tree.heading(col, text=col)
            self.cal_tree.column(col, width=110, anchor=tk.W)
        self.cal_tree.column("备注", width=150)
        
        c_scrollbar = ttk.Scrollbar(cal_frame, orient=tk.VERTICAL, command=self.cal_tree.yview)
        self.cal_tree.configure(yscrollcommand=c_scrollbar.set)
        
        self.cal_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        c_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        calibrations = self.service.get_calibration_records(self.instrument.id)
        for c in calibrations:
            self.cal_tree.insert("", tk.END, values=(
                c.calibration_date.isoformat(),
                c.next_calibration_date.isoformat(),
                c.certificate_number,
                c.calibration_agency,
                c.result,
                c.notes,
            ))

    def _create_buttons(self):
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="关闭", command=self._on_cancel).pack(side=tk.RIGHT)


class UserDialog(BaseDialog):
    def __init__(self, parent, current_user: User):
        self.current_user = current_user
        self.username_var = tk.StringVar(value=current_user.username)
        self.display_name_var = tk.StringVar(value=current_user.display_name)
        self.role_var = tk.StringVar(value=current_user.role.value)
        super().__init__(parent, "切换用户", "400x300")

    def _create_content(self):
        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        ttk.Label(form_frame, text="用户名:").grid(row=row, column=0, sticky=tk.W, pady=10)
        ttk.Entry(form_frame, textvariable=self.username_var, width=30).grid(row=row, column=1, sticky=tk.EW, pady=10, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="显示名称:").grid(row=row, column=0, sticky=tk.W, pady=10)
        ttk.Entry(form_frame, textvariable=self.display_name_var, width=30).grid(row=row, column=1, sticky=tk.EW, pady=10, padx=(10, 0))
        row += 1
        
        ttk.Label(form_frame, text="用户角色:").grid(row=row, column=0, sticky=tk.W, pady=10)
        role_combo = ttk.Combobox(form_frame, textvariable=self.role_var,
                                  values=[r.value for r in UserRole],
                                  state="readonly", width=28)
        role_combo.grid(row=row, column=1, sticky=tk.EW, pady=10, padx=(10, 0))
        
        form_frame.columnconfigure(1, weight=1)

    def _on_ok(self):
        if not self.username_var.get().strip():
            messagebox.showerror("错误", "请输入用户名", parent=self)
            return
        
        self.result = User(
            username=self.username_var.get().strip(),
            role=UserRole(self.role_var.get()),
            display_name=self.display_name_var.get().strip() or self.username_var.get().strip(),
        )
        super()._on_ok()


class SettingsDialog(BaseDialog):
    def __init__(self, parent, settings: dict):
        self.settings = settings
        self.export_dir_var = tk.StringVar(value=settings.get('export_dir', ''))
        super().__init__(parent, "系统设置", "500x200")

    def _create_content(self):
        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(form_frame, text="导出目录:").grid(row=0, column=0, sticky=tk.W, pady=10)
        ttk.Entry(form_frame, textvariable=self.export_dir_var, width=45).grid(row=0, column=1, sticky=tk.EW, pady=10, padx=(10, 0))
        
        form_frame.columnconfigure(1, weight=1)

    def _on_ok(self):
        if not self.export_dir_var.get().strip():
            messagebox.showerror("错误", "请输入导出目录", parent=self)
            return
        
        self.result = {
            'export_dir': self.export_dir_var.get().strip(),
        }
        super()._on_ok()


class ExportDialog(BaseDialog):
    def __init__(self, parent, export_dir: str):
        self.export_dir = export_dir
        self.export_type_var = tk.StringVar(value="instruments")
        self.format_var = tk.StringVar(value="csv")
        super().__init__(parent, "导出数据", "450x420")

    def _create_content(self):
        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        ttk.Label(form_frame, text="导出内容:").grid(row=row, column=0, sticky=tk.W, pady=10)
        type_frame = ttk.Frame(form_frame)
        type_frame.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        ttk.Radiobutton(type_frame, text="仪器列表", variable=self.export_type_var, value="instruments").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="借用记录", variable=self.export_type_var, value="borrows").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="校准记录", variable=self.export_type_var, value="calibrations").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="操作历史", variable=self.export_type_var, value="histories").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="盘点汇总", variable=self.export_type_var, value="checks_summary").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="校准排程汇总", variable=self.export_type_var, value="calibration_schedules_summary").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="校准排程明细", variable=self.export_type_var, value="calibration_schedule_items").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="冲突明细", variable=self.export_type_var, value="calibration_schedule_conflicts").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="逾期清单", variable=self.export_type_var, value="overdue_calibration_items").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="全部数据", variable=self.export_type_var, value="all").pack(anchor=tk.W)
        row += 1
        
        ttk.Label(form_frame, text="导出格式:").grid(row=row, column=0, sticky=tk.W, pady=10)
        format_frame = ttk.Frame(form_frame)
        format_frame.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        ttk.Radiobutton(format_frame, text="CSV", variable=self.format_var, value="csv").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(format_frame, text="JSON", variable=self.format_var, value="json").pack(side=tk.LEFT)
        row += 1
        
        ttk.Label(form_frame, text="导出目录:").grid(row=row, column=0, sticky=tk.W, pady=10)
        ttk.Label(form_frame, text=self.export_dir, wraplength=250).grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        
        form_frame.columnconfigure(1, weight=1)

    def _on_ok(self):
        self.result = {
            'export_type': self.export_type_var.get(),
            'format': self.format_var.get(),
        }
        super()._on_ok()


class InventoryCheckDialog(BaseDialog):
    def __init__(self, parent, service: InstrumentService):
        self.service = service
        self.name_var = tk.StringVar(value=f"月度盘点-{date.today().strftime('%Y%m')}")
        self.checker_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        self.filepath_var = tk.StringVar()
        self.check_items = []
        self.check_record: Optional[InventoryCheck] = None
        self.conflicts: list[InventoryCheckConflict] = []
        self.current_conflict_index = 0
        super().__init__(parent, "批量盘点", "800x600")

    def _create_content(self):
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        self.import_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.import_frame, text="1. 导入数据")
        
        self.conflict_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.conflict_frame, text="2. 处理冲突")
        notebook.tab(self.conflict_frame, state=tk.DISABLED)
        
        self.summary_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.summary_frame, text="3. 完成")
        notebook.tab(self.summary_frame, state=tk.DISABLED)
        
        self.notebook = notebook
        self._create_import_page()
        self._create_conflict_page()
        self._create_summary_page()

    def _create_import_page(self):
        grid = ttk.Frame(self.import_frame)
        grid.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        ttk.Label(grid, text="盘点名称:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.name_var, width=50).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="盘点人:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.checker_var, width=30).grid(row=row, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="备注:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.notes_var, width=50).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1
        
        ttk.Label(grid, text="盘点文件:").grid(row=row, column=0, sticky=tk.W, pady=5)
        file_frame = ttk.Frame(grid)
        file_frame.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        ttk.Entry(file_frame, textvariable=self.filepath_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="浏览...", command=self._on_browse_file).pack(side=tk.LEFT, padx=(10, 0))
        row += 1
        
        ttk.Separator(grid, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1
        
        ttk.Label(grid, text="文件格式说明:", font=('bold', 10)).grid(row=row, column=0, columnspan=2, sticky=tk.W)
        row += 1
        
        help_text = "必填字段：序列号(serial_number)、实际位置(actual_location)、盘点人(checker)、盘点时间(check_time)\n可选字段：备注(remarks)\n支持格式：CSV、JSON"
        help_label = ttk.Label(grid, text=help_text, foreground="gray", justify=tk.LEFT)
        help_label.grid(row=row, column=0, columnspan=2, sticky=tk.W)
        row += 1
        
        self.import_status_var = tk.StringVar(value="")
        ttk.Label(grid, textvariable=self.import_status_var, foreground="blue").grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        ttk.Button(grid, text="导入并检测", command=self._on_import).grid(row=row+1, column=1, sticky=tk.E)
        
        grid.columnconfigure(1, weight=1)

    def _create_conflict_page(self):
        self.conflict_tree = ttk.Treeview(
            self.conflict_frame,
            columns=("type", "serial", "name", "expected", "actual", "resolution"),
            show="headings"
        )
        headings = [
            ("type", "冲突类型", 120),
            ("serial", "序列号", 120),
            ("name", "仪器名称", 150),
            ("expected", "系统值", 150),
            ("actual", "盘点值", 150),
            ("resolution", "处理状态", 100),
        ]
        for col, text, width in headings:
            self.conflict_tree.heading(col, text=text)
            self.conflict_tree.column(col, width=width, anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(self.conflict_frame, orient=tk.VERTICAL, command=self.conflict_tree.yview)
        self.conflict_tree.configure(yscrollcommand=scrollbar.set)
        
        self.conflict_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        btn_frame = ttk.Frame(self.conflict_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="处理选中", command=self._on_resolve_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="全部确认", command=self._on_resolve_all_confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="全部忽略", command=self._on_resolve_all_ignore).pack(side=tk.LEFT, padx=5)
        
        self.conflict_stats_var = tk.StringVar(value="")
        ttk.Label(btn_frame, textvariable=self.conflict_stats_var).pack(side=tk.RIGHT)
        
        self.conflict_tree.bind("<Double-1>", lambda e: self._on_resolve_selected())

    def _create_summary_page(self):
        self.summary_text = tk.Text(self.summary_frame, wrap=tk.WORD, height=20)
        self.summary_text.pack(fill=tk.BOTH, expand=True)

    def _on_browse_file(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="选择盘点文件",
            filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json"), ("所有文件", "*.*")],
            parent=self
        )
        if filepath:
            self.filepath_var.set(filepath)

    def _on_import(self):
        if not self.name_var.get().strip():
            messagebox.showerror("错误", "请输入盘点名称", parent=self)
            return
        
        if not self.checker_var.get().strip():
            messagebox.showerror("错误", "请输入盘点人", parent=self)
            return
        
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showerror("错误", "请选择盘点文件", parent=self)
            return
        
        success, msg, items = self.service.parse_inventory_check_file(filepath)
        if not success:
            messagebox.showerror("导入失败", msg, parent=self)
            return
        
        self.import_status_var.set(msg)
        self.check_items = items
        
        success, msg, check = self.service.create_inventory_check(
            name=self.name_var.get().strip(),
            checker=self.checker_var.get().strip(),
            notes=self.notes_var.get().strip()
        )
        if not success:
            messagebox.showerror("创建失败", msg, parent=self)
            return
        
        self.check_record = check
        
        success, msg, conflicts = self.service.detect_conflicts(check.id, items)
        if not success:
            messagebox.showerror("检测失败", msg, parent=self)
            return
        
        self.conflicts = conflicts
        
        self._refresh_conflict_tree()
        
        self.notebook.tab(self.conflict_frame, state=tk.NORMAL)
        self.notebook.select(self.conflict_frame)

    def _refresh_conflict_tree(self):
        for item in self.conflict_tree.get_children():
            self.conflict_tree.delete(item)
        
        for conflict in self.conflicts:
            self.conflict_tree.insert("", tk.END, iid=conflict.id, values=(
                conflict.conflict_type.value,
                conflict.serial_number,
                conflict.instrument_name,
                conflict.expected_value,
                conflict.actual_value,
                conflict.resolution.value,
            ), tags=(conflict.resolution.value,))
        
        self.conflict_tree.tag_configure("待处理", foreground="red")
        self.conflict_tree.tag_configure("确认更新", foreground="green")
        self.conflict_tree.tag_configure("忽略", foreground="gray")
        self.conflict_tree.tag_configure("强制更新", foreground="blue")
        
        pending = sum(1 for c in self.conflicts if c.resolution == ConflictResolution.PENDING)
        self.conflict_stats_var.set(f"共 {len(self.conflicts)} 条冲突，待处理 {pending} 条")

    def _on_resolve_selected(self):
        selection = self.conflict_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择要处理的冲突", parent=self)
            return
        
        conflict_id = selection[0]
        conflict = next((c for c in self.conflicts if c.id == conflict_id), None)
        if not conflict:
            return
        
        dialog = ConflictResolveDialog(self, conflict)
        if dialog.show() and dialog.result:
            resolution = dialog.result['resolution']
            notes = dialog.result.get('notes', '')
            
            success, msg, _ = self.service.resolve_conflict(
                conflict_id=conflict_id,
                resolution=resolution,
                notes=notes
            )
            if success:
                conflict.resolution = resolution
                conflict.resolved_by = self.service.get_current_user().display_name
                conflict.resolved_at = datetime.now()
                conflict.notes = notes
                self._refresh_conflict_tree()
                self._check_all_resolved()
            else:
                messagebox.showerror("处理失败", msg, parent=self)

    def _on_resolve_all_confirm(self):
        if not messagebox.askyesno("确认", "确定要确认所有待处理的冲突吗？", parent=self):
            return
        
        success, msg, count = self.service.resolve_all_conflicts(
            self.check_record.id,
            ConflictResolution.CONFIRM
        )
        if success:
            for conflict in self.conflicts:
                if conflict.resolution == ConflictResolution.PENDING:
                    conflict.resolution = ConflictResolution.CONFIRM
                    conflict.resolved_by = self.service.get_current_user().display_name
                    conflict.resolved_at = datetime.now()
            self._refresh_conflict_tree()
            messagebox.showinfo("成功", msg, parent=self)
            self._check_all_resolved()
        else:
            messagebox.showerror("处理失败", msg, parent=self)

    def _on_resolve_all_ignore(self):
        if not messagebox.askyesno("确认", "确定要忽略所有待处理的冲突吗？", parent=self):
            return
        
        success, msg, count = self.service.resolve_all_conflicts(
            self.check_record.id,
            ConflictResolution.IGNORE
        )
        if success:
            for conflict in self.conflicts:
                if conflict.resolution == ConflictResolution.PENDING:
                    conflict.resolution = ConflictResolution.IGNORE
                    conflict.resolved_by = self.service.get_current_user().display_name
                    conflict.resolved_at = datetime.now()
            self._refresh_conflict_tree()
            messagebox.showinfo("成功", msg, parent=self)
            self._check_all_resolved()
        else:
            messagebox.showerror("处理失败", msg, parent=self)

    def _check_all_resolved(self):
        pending = sum(1 for c in self.conflicts if c.resolution == ConflictResolution.PENDING)
        if pending == 0:
            self.service.mark_check_completed(self.check_record.id)
            self._show_summary()
            self.notebook.tab(self.summary_frame, state=tk.NORMAL)
            self.notebook.select(self.summary_frame)

    def _show_summary(self):
        check = self.service.get_inventory_check_by_id(self.check_record.id)
        conflicts = self.service.get_inventory_check_conflicts(self.check_record.id)
        
        summary = f"盘点完成！\n\n"
        summary += f"盘点名称: {check.name}\n"
        summary += f"盘点人: {check.checker}\n"
        summary += f"盘点日期: {check.check_date}\n"
        summary += f"总条目数: {check.total_items}\n"
        summary += f"匹配数量: {check.matched_count}\n"
        summary += f"冲突数量: {check.conflict_count}\n\n"
        summary += "冲突明细:\n"
        summary += "-" * 50 + "\n"
        
        type_counts = {}
        res_counts = {}
        for c in conflicts:
            type_counts[c.conflict_type.value] = type_counts.get(c.conflict_type.value, 0) + 1
            res_counts[c.resolution.value] = res_counts.get(c.resolution.value, 0) + 1
        
        summary += "按类型统计:\n"
        for typ, cnt in type_counts.items():
            summary += f"  {typ}: {cnt} 条\n"
        
        summary += "\n按处理结果统计:\n"
        for res, cnt in res_counts.items():
            summary += f"  {res}: {cnt} 条\n"
        
        if check.can_undo:
            summary += f"\n本次盘点更新了 {len(check.undo_snapshot.get('updates', [])) if check.undo_snapshot else 0} 条位置，可在主界面点击\"撤销盘点\"撤回。"
        
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, summary)
        self.summary_text.config(state=tk.DISABLED)

    def _on_ok(self):
        if self.check_record and self.check_record.status == InventoryCheckStatus.COMPLETED:
            self.result = True
        super()._on_ok()


class ConflictResolveDialog(BaseDialog):
    def __init__(self, parent, conflict: InventoryCheckConflict):
        self.conflict = conflict
        self.resolution_var = tk.StringVar(value=ConflictResolution.CONFIRM.value)
        self.notes_var = tk.StringVar()
        super().__init__(parent, "处理冲突", "500x400")

    def _create_content(self):
        info_frame = ttk.LabelFrame(self.main_frame, text="冲突信息", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        grid = ttk.Frame(info_frame)
        grid.pack(fill=tk.X)
        
        ttk.Label(grid, text="冲突类型:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(grid, text=self.conflict.conflict_type.value, foreground="red", font=('bold', 10)).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(grid, text="序列号:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.serial_number).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(grid, text="仪器名称:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.instrument_name or "未知").grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(grid, text="系统记录:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.expected_value, foreground="blue").grid(row=3, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(grid, text="盘点记录:").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.actual_value, foreground="darkgreen").grid(row=4, column=1, sticky=tk.W, pady=5)
        
        if self.conflict.notes:
            ttk.Label(grid, text="备注:").grid(row=5, column=0, sticky=tk.W, pady=5)
            ttk.Label(grid, text=self.conflict.notes, wraplength=300).grid(row=5, column=1, sticky=tk.W, pady=5)
        
        resolve_frame = ttk.LabelFrame(self.main_frame, text="处理方式", padding="10")
        resolve_frame.pack(fill=tk.X, pady=(0, 10))
        
        resolutions = [ConflictResolution.CONFIRM.value, ConflictResolution.IGNORE.value, ConflictResolution.UPDATE.value]
        for i, res in enumerate(resolutions):
            ttk.Radiobutton(resolve_frame, text=res, variable=self.resolution_var, value=res).pack(anchor=tk.W, pady=2)
        
        notes_frame = ttk.LabelFrame(self.main_frame, text="处理备注", padding="10")
        notes_frame.pack(fill=tk.X)
        ttk.Entry(notes_frame, textvariable=self.notes_var, width=50).pack(fill=tk.X)

    def _on_ok(self):
        self.result = {
            'resolution': ConflictResolution(self.resolution_var.get()),
            'notes': self.notes_var.get().strip()
        }
        super()._on_ok()


class InventoryCheckHistoryDialog(BaseDialog):
    def __init__(self, parent, service: InstrumentService):
        self.service = service
        super().__init__(parent, "盘点历史", "900x500")

    def _create_content(self):
        columns = ("name", "checker", "date", "total", "matched", "conflicts", "status", "can_undo", "created")
        self.tree = ttk.Treeview(self.main_frame, columns=columns, show="headings")
        
        headings = [
            ("name", "盘点名称", 180),
            ("checker", "盘点人", 100),
            ("date", "盘点日期", 100),
            ("total", "总条目", 80),
            ("matched", "匹配数", 80),
            ("conflicts", "冲突数", 80),
            ("status", "状态", 100),
            ("can_undo", "可撤销", 80),
            ("created", "创建时间", 150),
        ]
        for col, text, width in headings:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="查看冲突明细", command=self._on_view_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="导出当前盘点", command=self._on_export_current).pack(side=tk.LEFT, padx=5)
        
        self._load_history()
        self.tree.bind("<Double-1>", lambda e: self._on_view_conflicts())

    def _load_history(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        checks = self.service.get_inventory_checks()
        for check in checks:
            self.tree.insert("", tk.END, iid=check.id, values=(
                check.name,
                check.checker,
                check.check_date.isoformat(),
                check.total_items,
                check.matched_count,
                check.conflict_count,
                check.status.value,
                "是" if check.can_undo else "否",
                check.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ))

    def _on_view_conflicts(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择盘点记录", parent=self)
            return
        
        check_id = selection[0]
        check = self.service.get_inventory_check_by_id(check_id)
        conflicts = self.service.get_inventory_check_conflicts(check_id)
        
        dialog = InventoryCheckDetailDialog(self, check, conflicts)
        dialog.show()

    def _on_export_current(self):
        from tkinter import filedialog
        from ..storage import DataExporter
        
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择盘点记录", parent=self)
            return
        
        check_id = selection[0]
        check = self.service.get_inventory_check_by_id(check_id)
        conflicts = self.service.get_inventory_check_conflicts(check_id)
        
        filepath = filedialog.asksaveasfilename(
            title="导出盘点记录",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")],
            initialfile=f"inventory_check_{check.name}_{date.today().strftime('%Y%m%d')}",
            parent=self
        )
        if not filepath:
            return
        
        try:
            ext = os.path.splitext(filepath)[1].lower()
            if ext == '.csv':
                DataExporter.export_inventory_check_to_csv(check, conflicts, filepath)
            else:
                DataExporter.export_inventory_check_to_json(check, conflicts, filepath)
            
            messagebox.showinfo("导出成功", f"盘点记录已导出到:\n{filepath}", parent=self)
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self)


class InventoryCheckDetailDialog(BaseDialog):
    def __init__(self, parent, check: InventoryCheck, conflicts: list):
        self.check = check
        self.conflicts = conflicts
        super().__init__(parent, f"盘点明细 - {check.name}", "900x500")

    def _create_content(self):
        info_frame = ttk.LabelFrame(self.main_frame, text="盘点概览", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        grid = ttk.Frame(info_frame)
        grid.pack(fill=tk.X)
        
        info = [
            ("盘点名称", self.check.name),
            ("盘点人", self.check.checker),
            ("盘点日期", self.check.check_date.isoformat()),
            ("总条目", str(self.check.total_items)),
            ("匹配数", str(self.check.matched_count)),
            ("冲突数", str(self.check.conflict_count)),
            ("状态", self.check.status.value),
            ("可撤销", "是" if self.check.can_undo else "否"),
        ]
        for i, (label, value) in enumerate(info):
            ttk.Label(grid, text=f"{label}:").grid(row=i//2, column=(i%2)*2, sticky=tk.W, padx=(0, 5), pady=3)
            ttk.Label(grid, text=value, font=('bold', 10)).grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, pady=3)
        
        columns = ("type", "serial", "name", "expected", "actual", "resolution", "resolved_by", "resolved_at")
        tree = ttk.Treeview(self.main_frame, columns=columns, show="headings")
        
        headings = [
            ("type", "冲突类型", 120),
            ("serial", "序列号", 120),
            ("name", "仪器名称", 150),
            ("expected", "系统值", 120),
            ("actual", "盘点值", 120),
            ("resolution", "处理结论", 100),
            ("resolved_by", "处理人", 100),
            ("resolved_at", "处理时间", 150),
        ]
        for col, text, width in headings:
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))
        
        for c in self.conflicts:
            tree.insert("", tk.END, values=(
                c.conflict_type.value,
                c.serial_number,
                c.instrument_name,
                c.expected_value,
                c.actual_value,
                c.resolution.value,
                c.resolved_by or "",
                c.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if c.resolved_at else "",
            ), tags=(c.resolution.value,))
        
        tree.tag_configure("待处理", foreground="red")
        tree.tag_configure("确认更新", foreground="green")
        tree.tag_configure("忽略", foreground="gray")
        tree.tag_configure("强制更新", foreground="blue")


class CalibrationScheduleConflictResolveDialog(BaseDialog):
    def __init__(self, parent, conflict: CalibrationScheduleConflict,
                 is_admin: bool = True):
        self.conflict = conflict
        self.is_admin = is_admin
        self.resolution_var = tk.StringVar(value=CalibrationConflictResolution.CONFIRM.value)
        self.notes_var = tk.StringVar()
        super().__init__(parent, "处理校准冲突", "550x450")

    def _create_content(self):
        info_frame = ttk.LabelFrame(self.main_frame, text="冲突信息", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        grid = ttk.Frame(info_frame)
        grid.pack(fill=tk.X)

        ttk.Label(grid, text="冲突类型:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(grid, text=self.conflict.conflict_type.value, foreground="red", font=('bold', 10)).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(grid, text="序列号:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.serial_number).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(grid, text="仪器名称:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.instrument_name or "未知").grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Label(grid, text="系统记录:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.expected_value, foreground="blue").grid(row=3, column=1, sticky=tk.W, pady=5)

        ttk.Label(grid, text="导入记录:").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Label(grid, text=self.conflict.actual_value, foreground="darkgreen").grid(row=4, column=1, sticky=tk.W, pady=5)

        if self.conflict.notes:
            ttk.Label(grid, text="备注:").grid(row=5, column=0, sticky=tk.W, pady=5)
            ttk.Label(grid, text=self.conflict.notes, wraplength=300).grid(row=5, column=1, sticky=tk.W, pady=5)

        if self.is_admin:
            resolve_frame = ttk.LabelFrame(self.main_frame, text="处理方式", padding="10")
            resolve_frame.pack(fill=tk.X, pady=(0, 10))

            resolutions = [
                CalibrationConflictResolution.CONFIRM.value,
                CalibrationConflictResolution.IGNORE.value,
            ]
            for i, res in enumerate(resolutions):
                ttk.Radiobutton(resolve_frame, text=res, variable=self.resolution_var, value=res).pack(anchor=tk.W, pady=2)

            notes_frame = ttk.LabelFrame(self.main_frame, text="处理备注", padding="10")
            notes_frame.pack(fill=tk.X)
            ttk.Entry(notes_frame, textvariable=self.notes_var, width=50).pack(fill=tk.X)
        else:
            ttk.Label(self.main_frame, text="普通用户仅可查看，无法处理冲突",
                      foreground="red", font=('bold', 10)).pack(pady=10)

    def _on_ok(self):
        if not self.is_admin:
            self.result = False
            super()._on_cancel()
            return

        self.result = {
            'resolution': CalibrationConflictResolution(self.resolution_var.get()),
            'notes': self.notes_var.get().strip()
        }
        super()._on_ok()


class CalibrationScheduleCompleteDialog(BaseDialog):
    def __init__(self, parent, item: CalibrationScheduleItem,
                 is_admin: bool = True):
        self.item = item
        self.is_admin = is_admin
        self.cal_date_var = tk.StringVar(value=date.today().isoformat())
        self.next_cal_date_var = tk.StringVar(value=(date.today() + timedelta(days=365)).isoformat())
        self.cert_var = tk.StringVar(value=item.certificate_number)
        self.agency_var = tk.StringVar(value=item.calibration_agency)
        self.result_var = tk.StringVar(value="合格")
        self.notes_var = tk.StringVar()
        super().__init__(parent, f"完成校准: {item.instrument_name}", "500x450")

    def _create_content(self):
        info_frame = ttk.LabelFrame(self.main_frame, text="仪器信息", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(info_frame, text=f"仪器名称: {self.item.instrument_name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"型号: {self.item.serial_number}").pack(anchor=tk.W)
        current_cal = self.item.planned_date.isoformat()
        ttk.Label(info_frame, text=f"计划校准日期: {current_cal}").pack(anchor=tk.W)

        if self.is_admin:
            form_frame = ttk.Frame(self.main_frame)
            form_frame.pack(fill=tk.BOTH, expand=True)

            row = 0
            ttk.Label(form_frame, text="校准日期:").grid(row=row, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form_frame, textvariable=self.cal_date_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            row += 1

            ttk.Label(form_frame, text="下次校准日期:").grid(row=row, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form_frame, textvariable=self.next_cal_date_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            row += 1

            ttk.Label(form_frame, text="证书编号:").grid(row=row, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form_frame, textvariable=self.cert_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            row += 1

            ttk.Label(form_frame, text="校准机构:").grid(row=row, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form_frame, textvariable=self.agency_var, width=35).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            row += 1

            ttk.Label(form_frame, text="校准结果:").grid(row=row, column=0, sticky=tk.W, pady=5)
            result_combo = ttk.Combobox(form_frame, textvariable=self.result_var,
                                         values=["合格", "不合格", "限制使用"],
                                         state="readonly", width=33)
            result_combo.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            row += 1

            ttk.Label(form_frame, text="备注:").grid(row=row, column=0, sticky=tk.NW, pady=5)
            notes_text = tk.Text(form_frame, height=3, width=35)
            notes_text.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            self.notes_text = notes_text
            row += 1

            form_frame.columnconfigure(1, weight=1)
        else:
            ttk.Label(self.main_frame, text="普通用户仅可查看，无法完成校准",
                      foreground="red", font=('bold', 10)).pack(pady=10)

    def _on_ok(self):
        if not self.is_admin:
            self.result = False
            super()._on_cancel()
            return

        try:
            cal_date = date.fromisoformat(self.cal_date_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "校准日期格式不正确", parent=self)
            return

        try:
            next_cal_date = date.fromisoformat(self.next_cal_date_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "下次校准日期格式不正确", parent=self)
            return

        if not self.cert_var.get().strip():
            messagebox.showerror("错误", "请输入证书编号", parent=self)
            return

        if not self.agency_var.get().strip():
            messagebox.showerror("错误", "请输入校准机构", parent=self)
            return

        self.result = {
            'calibration_date': cal_date,
            'next_calibration_date': next_cal_date,
            'certificate_number': self.cert_var.get().strip(),
            'calibration_agency': self.agency_var.get().strip(),
            'result': self.result_var.get().strip(),
            'notes': self.notes_text.get("1.0", tk.END).strip(),
        }
        super()._on_ok()


class CalibrationScheduleDialog(BaseDialog):
    def __init__(self, parent, service: InstrumentService):
        self.service = service
        self.user = service.get_current_user()
        self.is_admin = self.user.can_calibrate()
        self.name_var = tk.StringVar(value=f"校准排程-{date.today().strftime('%Y%m')}")
        self.notes_var = tk.StringVar()
        self.filepath_var = tk.StringVar()
        self.import_items = []
        self.schedule: Optional[CalibrationSchedule] = None
        self.conflicts: list[CalibrationScheduleConflict] = []
        self.items: list[CalibrationScheduleItem] = []
        super().__init__(parent, "校准排程管理", "900x650")

    def _create_content(self):
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.import_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.import_frame, text="1. 导入排程")

        self.items_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.items_frame, text="2. 校准计划")
        notebook.tab(self.items_frame, state=tk.DISABLED)

        self.conflict_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.conflict_frame, text="3. 冲突处理")
        notebook.tab(self.conflict_frame, state=tk.DISABLED)

        self.complete_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.complete_frame, text="4. 完成校准")
        notebook.tab(self.complete_frame, state=tk.DISABLED)

        self.notebook = notebook
        self._create_import_page()
        self._create_items_page()
        self._create_conflict_page()
        self._create_complete_page()

    def _create_import_page(self):
        grid = ttk.Frame(self.import_frame)
        grid.pack(fill=tk.BOTH, expand=True)

        row = 0
        ttk.Label(grid, text="排程名称:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.name_var, width=50).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1

        ttk.Label(grid, text="备注:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(grid, textvariable=self.notes_var, width=50).grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        row += 1

        ttk.Label(grid, text="排程文件:").grid(row=row, column=0, sticky=tk.W, pady=5)
        file_frame = ttk.Frame(grid)
        file_frame.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        ttk.Entry(file_frame, textvariable=self.filepath_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="浏览...", command=self._on_browse_file).pack(side=tk.LEFT, padx=(10, 0))
        row += 1

        ttk.Separator(grid, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        ttk.Label(grid, text="文件格式说明:", font=('bold', 10)).grid(row=row, column=0, columnspan=2, sticky=tk.W)
        row += 1

        help_text = "必填字段：序列号(serial_number)、计划日期(planned_date)\n可选字段：校准机构(calibration_agency)、证书编号(certificate_number)、备注(notes)\n支持格式：CSV、JSON"
        help_label = ttk.Label(grid, text=help_text, foreground="gray", justify=tk.LEFT)
        help_label.grid(row=row, column=0, columnspan=2, sticky=tk.W)
        row += 1

        self.import_status_var = tk.StringVar(value="")
        ttk.Label(grid, textvariable=self.import_status_var, foreground="blue").grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10)
        row += 1

        if self.is_admin:
            ttk.Button(grid, text="导入并检测冲突", command=self._on_import).grid(row=row, column=1, sticky=tk.E)
        else:
            ttk.Label(grid, text="普通用户仅可查看历史排程",
                      foreground="red", font=('bold', 10)).grid(row=row, column=0, columnspan=2, sticky=tk.W)

        grid.columnconfigure(1, weight=1)

    def _create_items_page(self):
        columns = ("name", "serial", "planned_date", "agency", "cert", "status", "processed_by", "processed_at")
        self.items_tree = ttk.Treeview(self.items_frame, columns=columns, show="headings")

        headings = [
            ("name", "仪器名称", 180),
            ("serial", "序列号", 120),
            ("planned_date", "计划日期", 100),
            ("agency", "校准机构", 150),
            ("cert", "证书编号", 120),
            ("status", "状态", 100),
            ("processed_by", "处理人", 100),
            ("processed_at", "处理时间", 150),
        ]
        for col, text, width in headings:
            self.items_tree.heading(col, text=text)
            self.items_tree.column(col, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(self.items_frame, orient=tk.VERTICAL, command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=scrollbar.set)

        self.items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(self.items_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        if self.is_admin:
            self.complete_item_btn = ttk.Button(btn_frame, text="完成校准", command=self._on_complete_item, state=tk.DISABLED)
            self.complete_item_btn.pack(side=tk.LEFT, padx=5)

        self.items_stats_var = tk.StringVar(value="")
        ttk.Label(btn_frame, textvariable=self.items_stats_var).pack(side=tk.RIGHT)

        self.items_tree.bind("<Double-1>", lambda e: self._on_complete_item())
        self.items_tree.bind("<<TreeviewSelect>>", self._on_item_select)

    def _create_conflict_page(self):
        self.conflict_tree = ttk.Treeview(
            self.conflict_frame,
            columns=("type", "serial", "name", "expected", "actual", "resolution", "resolved_by", "resolved_at"),
            show="headings"
        )
        headings = [
            ("type", "冲突类型", 120),
            ("serial", "序列号", 120),
            ("name", "仪器名称", 150),
            ("expected", "系统值", 150),
            ("actual", "导入值", 150),
            ("resolution", "处理状态", 100),
            ("resolved_by", "处理人", 100),
            ("resolved_at", "处理时间", 150),
        ]
        for col, text, width in headings:
            self.conflict_tree.heading(col, text=text)
            self.conflict_tree.column(col, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(self.conflict_frame, orient=tk.VERTICAL, command=self.conflict_tree.yview)
        self.conflict_tree.configure(yscrollcommand=scrollbar.set)

        self.conflict_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(self.conflict_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        if self.is_admin:
            ttk.Button(btn_frame, text="处理选中", command=self._on_resolve_selected).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="全部确认", command=self._on_resolve_all_confirm).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="全部忽略", command=self._on_resolve_all_ignore).pack(side=tk.LEFT, padx=5)

        self.conflict_stats_var = tk.StringVar(value="")
        ttk.Label(btn_frame, textvariable=self.conflict_stats_var).pack(side=tk.RIGHT)

        self.conflict_tree.bind("<Double-1>", lambda e: self._on_resolve_selected())

    def _create_complete_page(self):
        self.complete_summary_text = tk.Text(self.complete_frame, wrap=tk.WORD, height=20)
        self.complete_summary_text.pack(fill=tk.BOTH, expand=True)

    def _on_browse_file(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="选择校准排程文件",
            filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json"), ("所有文件", "*.*")],
            parent=self
        )
        if filepath:
            self.filepath_var.set(filepath)

    def _on_import(self):
        if not self.is_admin:
            messagebox.showinfo("提示", "您没有导入权限", parent=self)
            return

        if not self.name_var.get().strip():
            messagebox.showerror("错误", "请输入排程名称", parent=self)
            return

        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showerror("错误", "请选择排程文件", parent=self)
            return

        success, msg, items = self.service.parse_calibration_schedule_file(filepath)
        if not success:
            messagebox.showerror("导入失败", msg, parent=self)
            return

        self.import_status_var.set(msg)
        self.import_items = items

        success, msg, schedule = self.service.create_calibration_schedule(
            name=self.name_var.get().strip(),
            notes=self.notes_var.get().strip()
        )
        if not success:
            messagebox.showerror("创建失败", msg, parent=self)
            return

        self.schedule = schedule

        success, msg, conflicts = self.service.detect_calibration_conflicts(schedule.id, items)
        if not success:
            messagebox.showerror("检测失败", msg, parent=self)
            return

        self.conflicts = conflicts
        self.items = self.service.get_calibration_schedule_items(schedule.id)

        self._refresh_items_tree()
        self._refresh_conflict_tree()

        self.notebook.tab(self.items_frame, state=tk.NORMAL)
        self.notebook.tab(self.conflict_frame, state=tk.NORMAL)
        self.notebook.tab(self.complete_frame, state=tk.NORMAL)
        self.notebook.select(self.items_frame)

    def _refresh_items_tree(self):
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)

        items = self.service.get_calibration_schedule_items(self.schedule.id) if self.schedule else self.items
        for item in items:
            self.items_tree.insert("", tk.END, iid=item.id, values=(
                item.instrument_name,
                item.serial_number,
                item.planned_date.isoformat(),
                item.calibration_agency,
                item.certificate_number,
                item.status.value,
                item.processed_by or "",
                item.processed_at.strftime("%Y-%m-%d %H:%M:%S") if item.processed_at else "",
            ), tags=(item.status.value,))

        self.items_tree.tag_configure("待校准", foreground="darkorange")
        self.items_tree.tag_configure("校准中", foreground="blue")
        self.items_tree.tag_configure("已完成", foreground="green")
        self.items_tree.tag_configure("已逾期", foreground="red")
        self.items_tree.tag_configure("已取消", foreground="gray")

        if self.schedule:
            schedule = self.service.get_calibration_schedule_by_id(self.schedule.id)
            if schedule:
                items_list = self.service.get_calibration_schedule_items(schedule.id)
                schedule.refresh_status(items_list)
                self.items_stats_var.set(
                    f"共 {len(items_list)} 条计划，"
                    f"待校准 {sum(1 for i in items_list if i.status == CalibrationScheduleItemStatus.SCHEDULED)} 条，"
                    f"已逾期 {sum(1 for i in items_list if i.status == CalibrationScheduleItemStatus.OVERDUE)} 条，"
                    f"已完成 {schedule.completed_count} 条"
                )

    def _refresh_conflict_tree(self):
        for item in self.conflict_tree.get_children():
            self.conflict_tree.delete(item)

        conflicts = self.service.get_calibration_schedule_conflicts(self.schedule.id) if self.schedule else self.conflicts
        for conflict in conflicts:
            self.conflict_tree.insert("", tk.END, iid=conflict.id, values=(
                conflict.conflict_type.value,
                conflict.serial_number,
                conflict.instrument_name or "未知",
                conflict.expected_value,
                conflict.actual_value,
                conflict.resolution.value,
                conflict.resolved_by or "",
                conflict.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if conflict.resolved_at else "",
            ), tags=(conflict.resolution.value,))

        self.conflict_tree.tag_configure("待处理", foreground="red")
        self.conflict_tree.tag_configure("确认导入", foreground="green")
        self.conflict_tree.tag_configure("忽略跳过", foreground="gray")
        self.conflict_tree.tag_configure("强制更新", foreground="blue")

        pending = sum(1 for c in conflicts if c.resolution == CalibrationConflictResolution.PENDING)
        self.conflict_stats_var.set(f"共 {len(conflicts)} 条冲突，待处理 {pending} 条")

    def _on_item_select(self, event):
        if not self.is_admin:
            return
        selection = self.items_tree.selection()
        if selection:
            item_id = selection[0]
            item = next((i for i in self.items if i.id == item_id), None)
            if item and item.status != CalibrationScheduleItemStatus.COMPLETED:
                self.complete_item_btn.config(state=tk.NORMAL)
            else:
                self.complete_item_btn.config(state=tk.DISABLED)
        else:
            self.complete_item_btn.config(state=tk.DISABLED)

    def _on_complete_item(self):
        if not self.is_admin:
            return
        selection = self.items_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择要完成校准的排程项", parent=self)
            return

        item_id = selection[0]
        item = self.service.get_calibration_schedule_item_by_id(item_id)
        if not item:
            return

        if item.status == CalibrationScheduleItemStatus.COMPLETED:
            messagebox.showinfo("提示", "该排程项已完成校准", parent=self)
            return

        dialog = CalibrationScheduleCompleteDialog(self, item, self.is_admin)
        if dialog.show() and dialog.result:
            data = dialog.result
            success, message, updated_item = self.service.complete_calibration_schedule_item(
                item_id=item.id,
                calibration_date=data['calibration_date'],
                next_calibration_date=data['next_calibration_date'],
                certificate_number=data['certificate_number'],
                calibration_agency=data['calibration_agency'],
                result=data['result'],
                notes=data['notes'],
            )
            if success:
                self._refresh_items_tree()
                self._show_complete_summary()
                messagebox.showinfo("成功", message, parent=self)
            else:
                messagebox.showerror("校准失败", message, parent=self)

    def _on_resolve_selected(self):
        if not self.is_admin:
            return
        selection = self.conflict_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择要处理的冲突", parent=self)
            return

        conflict_id = selection[0]
        conflict = self.service.get_calibration_schedule_conflict_by_id(conflict_id)
        if not conflict:
            return

        dialog = CalibrationScheduleConflictResolveDialog(self, conflict, self.is_admin)
        if dialog.show() and dialog.result:
            resolution = dialog.result['resolution']
            notes = dialog.result.get('notes', '')

            success, msg, _ = self.service.resolve_calibration_conflict(
                conflict_id=conflict_id,
                resolution=resolution,
                notes=notes
            )
            if success:
                conflict.resolution = resolution
                conflict.resolved_by = self.user.display_name
                conflict.resolved_at = datetime.now()
                conflict.notes = notes
                self._refresh_conflict_tree()
                self._refresh_items_tree()
                self._check_all_resolved()
            else:
                messagebox.showerror("处理失败", msg, parent=self)

    def _on_resolve_all_confirm(self):
        if not self.is_admin:
            return
        if not messagebox.askyesno("确认", "确定要确认所有待处理的冲突吗？", parent=self):
            return

        success, msg, count = self.service.resolve_all_calibration_conflicts(
            self.schedule.id,
            CalibrationConflictResolution.CONFIRM
        )
        if success:
            for conflict in self.conflicts:
                if conflict.resolution == CalibrationConflictResolution.PENDING:
                    conflict.resolution = CalibrationConflictResolution.CONFIRM
                    conflict.resolved_by = self.user.display_name
                    conflict.resolved_at = datetime.now()
            self._refresh_conflict_tree()
            self._refresh_items_tree()
            messagebox.showinfo("成功", msg, parent=self)
            self._check_all_resolved()
        else:
            messagebox.showerror("处理失败", msg, parent=self)

    def _on_resolve_all_ignore(self):
        if not self.is_admin:
            return
        if not messagebox.askyesno("确认", "确定要忽略所有待处理的冲突吗？", parent=self):
            return

        success, msg, count = self.service.resolve_all_calibration_conflicts(
            self.schedule.id,
            CalibrationConflictResolution.IGNORE
        )
        if success:
            for conflict in self.conflicts:
                if conflict.resolution == CalibrationConflictResolution.PENDING:
                    conflict.resolution = CalibrationConflictResolution.IGNORE
                    conflict.resolved_by = self.user.display_name
                    conflict.resolved_at = datetime.now()
            self._refresh_conflict_tree()
            self._refresh_items_tree()
            messagebox.showinfo("成功", msg, parent=self)
            self._check_all_resolved()
        else:
            messagebox.showerror("处理失败", msg, parent=self)

    def _check_all_resolved(self):
        conflicts = self.service.get_calibration_schedule_conflicts(self.schedule.id)
        pending = sum(1 for c in conflicts if c.resolution == CalibrationConflictResolution.PENDING)
        if pending == 0:
            self._show_complete_summary()

    def _show_complete_summary(self):
        schedule = self.service.get_calibration_schedule_by_id(self.schedule.id)
        items = self.service.get_calibration_schedule_items(self.schedule.id)
        conflicts = self.service.get_calibration_schedule_conflicts(self.schedule.id)

        summary = f"校准排程处理完成！\n\n"
        summary += f"排程名称: {schedule.name}\n"
        summary += f"创建人: {schedule.creator}\n"
        summary += f"计划日期: {schedule.plan_date}\n"
        summary += f"总条目数: {schedule.total_items}\n"
        summary += f"已完成数: {schedule.completed_count}\n"
        summary += f"冲突数量: {schedule.conflict_count}\n\n"

        type_counts = {}
        res_counts = {}
        status_counts = {}
        for c in conflicts:
            type_counts[c.conflict_type.value] = type_counts.get(c.conflict_type.value, 0) + 1
            res_counts[c.resolution.value] = res_counts.get(c.resolution.value, 0) + 1
        for i in items:
            status_counts[i.status.value] = status_counts.get(i.status.value, 0) + 1

        summary += "按冲突类型统计:\n"
        for typ, cnt in type_counts.items():
            summary += f"  {typ}: {cnt} 条\n"

        summary += "\n按处理结果统计:\n"
        for res, cnt in res_counts.items():
            summary += f"  {res}: {cnt} 条\n"

        summary += "\n按计划状态统计:\n"
        for status, cnt in status_counts.items():
            summary += f"  {status}: {cnt} 条\n"

        if schedule.can_undo:
            summary += f"\n本次排程完成了 {len(schedule.undo_snapshot.get('items', [])) if schedule.undo_snapshot else 0} 条校准，可在主界面点击\"撤销校准\"撤回。"

        self.complete_summary_text.delete(1.0, tk.END)
        self.complete_summary_text.insert(1.0, summary)
        self.complete_summary_text.config(state=tk.DISABLED)

    def _on_ok(self):
        self.result = True
        super()._on_ok()


class CalibrationScheduleHistoryDialog(BaseDialog):
    def __init__(self, parent, service: InstrumentService):
        self.service = service
        self.user = service.get_current_user()
        self.is_admin = self.user.can_calibrate()
        super().__init__(parent, "校准排程历史", "950x550")

    def _create_content(self):
        columns = ("name", "creator", "date", "total", "completed", "conflicts", "status", "can_undo", "created")
        self.tree = ttk.Treeview(self.main_frame, columns=columns, show="headings")

        headings = [
            ("name", "排程名称", 180),
            ("creator", "创建人", 100),
            ("date", "计划日期", 100),
            ("total", "总条目", 80),
            ("completed", "已完成", 80),
            ("conflicts", "冲突数", 80),
            ("status", "状态", 100),
            ("can_undo", "可撤销", 80),
            ("created", "创建时间", 150),
        ]
        for col, text, width in headings:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="查看明细", command=self._on_view_detail).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="导出当前排程", command=self._on_export_current).pack(side=tk.LEFT, padx=5)

        self._load_history()
        self.tree.bind("<Double-1>", lambda e: self._on_view_detail())

    def _load_history(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        schedules = self.service.get_calibration_schedules()
        for schedule in schedules:
            self.tree.insert("", tk.END, iid=schedule.id, values=(
                schedule.name,
                schedule.creator,
                schedule.plan_date.isoformat(),
                schedule.total_items,
                schedule.completed_count,
                schedule.conflict_count,
                schedule.status.value,
                "是" if schedule.can_undo else "否",
                schedule.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ))

    def _on_view_detail(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择排程记录", parent=self)
            return

        schedule_id = selection[0]
        schedule = self.service.get_calibration_schedule_by_id(schedule_id)
        items = self.service.get_calibration_schedule_items(schedule_id)
        conflicts = self.service.get_calibration_schedule_conflicts(schedule_id)

        dialog = CalibrationScheduleDetailDialog(self, schedule, items, conflicts, self.is_admin)
        dialog.show()

    def _on_export_current(self):
        from tkinter import filedialog

        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择排程记录", parent=self)
            return

        schedule_id = selection[0]
        schedule = self.service.get_calibration_schedule_by_id(schedule_id)
        items = self.service.get_calibration_schedule_items(schedule_id)
        conflicts = self.service.get_calibration_schedule_conflicts(schedule_id)

        filepath = filedialog.asksaveasfilename(
            title="导出校准排程",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")],
            initialfile=f"calibration_schedule_{schedule.name}_{date.today().strftime('%Y%m%d')}",
            parent=self
        )
        if not filepath:
            return

        try:
            ext = os.path.splitext(filepath)[1].lower()
            if ext == '.csv':
                DataExporter.export_calibration_schedule_full_to_csv(schedule, items, conflicts, filepath)
            else:
                data = {
                    'summary': schedule.to_dict(),
                    'items': [i.to_dict() for i in items],
                    'conflicts': [c.to_dict() for c in conflicts],
                }
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=DataExporter._default_serializer)

            messagebox.showinfo("导出成功", f"校准排程已导出到:\n{filepath}", parent=self)
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self)


class CalibrationScheduleDetailDialog(BaseDialog):
    def __init__(self, parent, schedule: CalibrationSchedule,
                 items: list, conflicts: list, is_admin: bool = True):
        self.schedule = schedule
        self.items = items
        self.conflicts = conflicts
        self.is_admin = is_admin
        super().__init__(parent, f"排程明细 - {schedule.name}", "950x600")

    def _create_content(self):
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        info_frame = ttk.Frame(notebook, padding="10")
        notebook.add(info_frame, text="排程概览")

        items_frame = ttk.Frame(notebook, padding="10")
        notebook.add(items_frame, text="校准计划")

        conflicts_frame = ttk.Frame(notebook, padding="10")
        notebook.add(conflicts_frame, text="冲突明细")

        self._create_info_page(info_frame)
        self._create_items_page(items_frame)
        self._create_conflicts_page(conflicts_frame)

    def _create_info_page(self, parent):
        info_frame = ttk.LabelFrame(parent, text="排程概览", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        grid = ttk.Frame(info_frame)
        grid.pack(fill=tk.X)

        info = [
            ("排程名称", self.schedule.name),
            ("创建人", self.schedule.creator),
            ("计划日期", self.schedule.plan_date.isoformat()),
            ("总条目", str(self.schedule.total_items)),
            ("已完成", str(self.schedule.completed_count)),
            ("冲突数", str(self.schedule.conflict_count)),
            ("状态", self.schedule.status.value),
            ("可撤销", "是" if self.schedule.can_undo else "否"),
        ]
        for i, (label, value) in enumerate(info):
            ttk.Label(grid, text=f"{label}:").grid(row=i//2, column=(i%2)*2, sticky=tk.W, padx=(0, 5), pady=3)
            ttk.Label(grid, text=value, font=('bold', 10)).grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, pady=3)

        if not self.is_admin:
            ttk.Label(parent, text="普通用户仅可查看，无法进行操作",
                      foreground="red", font=('bold', 10)).pack(pady=10)

    def _create_items_page(self, parent):
        columns = ("name", "serial", "planned_date", "agency", "cert", "status", "result", "processed_by")
        tree = ttk.Treeview(parent, columns=columns, show="headings")

        headings = [
            ("name", "仪器名称", 180),
            ("serial", "序列号", 120),
            ("planned_date", "计划日期", 100),
            ("agency", "校准机构", 150),
            ("cert", "证书编号", 120),
            ("status", "状态", 100),
            ("result", "结果", 100),
            ("processed_by", "处理人", 100),
        ]
        for col, text, width in headings:
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))

        for item in self.items:
            tree.insert("", tk.END, values=(
                item.instrument_name,
                item.serial_number,
                item.planned_date.isoformat(),
                item.calibration_agency,
                item.certificate_number,
                item.status.value,
                item.result or "-",
                item.processed_by or "",
            ), tags=(item.status.value,))

        tree.tag_configure("待校准", foreground="darkorange")
        tree.tag_configure("校准中", foreground="blue")
        tree.tag_configure("已完成", foreground="green")
        tree.tag_configure("已逾期", foreground="red")
        tree.tag_configure("已取消", foreground="gray")

    def _create_conflicts_page(self, parent):
        columns = ("type", "serial", "name", "expected", "actual", "resolution", "resolved_by", "resolved_at")
        tree = ttk.Treeview(parent, columns=columns, show="headings")

        headings = [
            ("type", "冲突类型", 120),
            ("serial", "序列号", 120),
            ("name", "仪器名称", 150),
            ("expected", "系统值", 120),
            ("actual", "导入值", 120),
            ("resolution", "处理结论", 100),
            ("resolved_by", "处理人", 100),
            ("resolved_at", "处理时间", 150),
        ]
        for col, text, width in headings:
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))

        for c in self.conflicts:
            tree.insert("", tk.END, values=(
                c.conflict_type.value,
                c.serial_number,
                c.instrument_name or "未知",
                c.expected_value,
                c.actual_value,
                c.resolution.value,
                c.resolved_by or "",
                c.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if c.resolved_at else "",
            ), tags=(c.resolution.value,))

        tree.tag_configure("待处理", foreground="red")
        tree.tag_configure("确认导入", foreground="green")
        tree.tag_configure("忽略跳过", foreground="gray")
        tree.tag_configure("强制更新", foreground="blue")
