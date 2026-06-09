import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
from typing import Optional, Callable

from ..models import (
    Instrument, InstrumentStatus, InstrumentCategory,
    User, UserRole,
)
from ..services import InstrumentService


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
        super().__init__(parent, "导出数据", "450x300")

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
