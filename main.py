import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.main_window import MainWindow
from src.storage.data_manager import DataManager
from src.services.sample_data import create_sample_data


def main():
    data_manager = DataManager()
    
    if not data_manager.has_data():
        if messagebox.askyesno("初始化数据", "检测到首次运行，是否加载样例数据？"):
            create_sample_data(data_manager)
    
    root = tk.Tk()
    root.title("实验室仪器管理系统")
    root.geometry("1200x700")
    root.minsize(1000, 600)
    
    try:
        style = ttk.Style()
        if sys.platform == "win32":
            style.theme_use('vista')
        elif sys.platform == "darwin":
            style.theme_use('aqua')
        else:
            style.theme_use('clam')
    except Exception:
        pass
    
    app = MainWindow(root, data_manager)
    app.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()


if __name__ == "__main__":
    main()
