import tkinter as tk
from tkinter import ttk , messagebox
from datetime import datetime
import sys

if sys.platform == 'win32':
    font_family = '微软雅黑'
elif sys.platform == 'darwin':
    font_family = 'PingFang SC'
else:
    font_family = 'Noto Sans CJK SC'

def center_window(reference, child):
    """将 child 窗口居中显示在 reference 部件的顶层窗口上"""
    child.update_idletasks()
    ref = reference.winfo_toplevel()  # 获取顶层窗口（主窗口）
    x = ref.winfo_rootx() + (ref.winfo_width() - child.winfo_width()) // 2
    y = ref.winfo_rooty() + (ref.winfo_height() - child.winfo_height()) // 2
    child.geometry(f"+{x}+{y}")

# ==================== 计时器窗口 ====================
class TimerWindow:
    def __init__(self, parent, db, event_id):
        self.parent = parent
        self.db = db
        self.event_id = event_id
        self.manager = TimerManager()  # 获取单例
        self.event = self.db.get_event(event_id)
        if not self.event:
            messagebox.showerror("错误", "事件不存在")
            return
        if self.event['completed']:
            messagebox.showinfo("提示", "该事件已完成，无法启动计时器")
            return

        # 检查是否已有该事件的计时任务
        self.task = self.manager.get_task(event_id)
        if self.task and self.task.window:
            # 如果窗口已存在，激活它
            self.task.window.lift()
            return
        elif not self.task:
            # 创建新任务（默认正向计时，初始0）
            self.task = self.manager.add_task(event_id, 'stopwatch', 0)
        self.task.window = self

        # 创建窗口
        self.window = tk.Toplevel(parent)
        center_window(parent, self.window)  # 注意：这里 parent 就是传入的父部件
        self.window.title("计时器")
        self.window.geometry("400x300")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # 界面变量
        self.mode = tk.StringVar(value=self.task.mode)
        self.hours = tk.IntVar(value=0)
        self.minutes = tk.IntVar(value=0)
        self.seconds = tk.IntVar(value=0)
        if self.task.seconds > 0 and self.task.mode == 'countdown':
            self.hours.set(self.task.seconds // 3600)
            self.minutes.set((self.task.seconds % 3600) // 60)
            self.seconds.set(self.task.seconds % 60)

        self.create_widgets()
        self.update_display()

    def create_widgets(self):
        # 标题
        ttk.Label(self.window, text=self.event['title'], font=("font_family", 12, "bold")).pack(pady=10)

        # 模式选择
        mode_frame = ttk.Frame(self.window)
        mode_frame.pack(pady=5)
        ttk.Radiobutton(mode_frame, text="计时", variable=self.mode, value="stopwatch",
                        command=self.on_mode_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="倒计时", variable=self.mode, value="countdown",
                        command=self.on_mode_change).pack(side=tk.LEFT, padx=5)

        # 倒计时设置区域
        self.settings_frame = ttk.Frame(self.window)
        self.settings_frame.pack(pady=5)
        self.create_countdown_settings()

        # 时间显示
        self.time_label = ttk.Label(self.window, text="00:00:00", font=("font_family", 24))
        self.time_label.pack(pady=20)

        # 控制按钮
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=10)

        self.start_pause_btn = ttk.Button(btn_frame, text="开始", width=8, command=self.toggle_start_pause)
        self.start_pause_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="完成", width=8, command=self.complete).pack(side=tk.LEFT, padx=5)

        # 根据当前任务状态更新按钮文字
        if self.task.running:
            self.start_pause_btn.config(text="暂停")

    def create_countdown_settings(self):
        for widget in self.settings_frame.winfo_children():
            widget.destroy()
        if self.mode.get() == "countdown":
            ttk.Label(self.settings_frame, text="时:").grid(row=0, column=0, padx=2)
            ttk.Spinbox(self.settings_frame, from_=0, to=23, textvariable=self.hours, width=3).grid(row=0, column=1, padx=2)
            ttk.Label(self.settings_frame, text="分:").grid(row=0, column=2, padx=2)
            ttk.Spinbox(self.settings_frame, from_=0, to=59, textvariable=self.minutes, width=3).grid(row=0, column=3, padx=2)
            ttk.Label(self.settings_frame, text="秒:").grid(row=0, column=4, padx=2)
            ttk.Spinbox(self.settings_frame, from_=0, to=59, textvariable=self.seconds, width=3).grid(row=0, column=5, padx=2)

    def on_mode_change(self):
        """切换模式时重置任务"""
        self.task.running = False
        self.task.mode = self.mode.get()
        self.task.seconds = 0
        self.start_pause_btn.config(text="开始")
        self.create_countdown_settings()
        self.update_display()

    def toggle_start_pause(self):
        if not self.task.running:
            # 开始
            if self.mode.get() == 'countdown' and self.task.seconds == 0:
                total = self.hours.get()*3600 + self.minutes.get()*60 + self.seconds.get()
                if total <= 0:
                    messagebox.showwarning("警告", "请设置有效时间")
                    return
                self.task.seconds = total
            self.task.mode = self.mode.get()
            self.task.running = True
            self.start_pause_btn.config(text="暂停")
        else:
            # 暂停
            self.task.running = False
            self.start_pause_btn.config(text="开始")

    def update_display(self):
        hours = self.task.seconds // 3600
        minutes = (self.task.seconds % 3600) // 60
        seconds = self.task.seconds % 60
        self.time_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        # 每秒更新（通过 manager 的循环驱动，但窗口也需要定期刷新）
        self.window.after(500, self.update_display)  # 每0.5秒刷新一次界面

    def complete(self):
        self.manager.complete_task(self.event_id)
        self.window.destroy()

    def on_close(self):
        self.task.window = None
        self.window.destroy()


class TimerTask:
    """单个计时任务"""
    def __init__(self, event_id, mode='stopwatch', initial_seconds=0):
        self.event_id = event_id
        self.mode = mode          # 'stopwatch' 或 'countdown'
        self.seconds = initial_seconds
        self.running = False
        self.window = None        # 关联的计时器窗口

class TimerManager:
    """全局计时管理器（单例）"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tasks = {}
            cls._instance.callbacks = []      # 界面更新回调（用于计时器视图）
            cls._instance.after_id = None
            cls._instance.refresh_daily_callback = None  # 刷新今日视图的回调
        return cls._instance

    def add_task(self, event_id, mode, initial_seconds):
        if event_id in self.tasks:
            return self.tasks[event_id]
        task = TimerTask(event_id, mode, initial_seconds)
        self.tasks[event_id] = task
        self._start_updates()
        return task

    def remove_task(self, event_id):
        if event_id in self.tasks:
            del self.tasks[event_id]
            if not self.tasks:
                self._stop_updates()

    def get_task(self, event_id):
        return self.tasks.get(event_id)

    def _start_updates(self):
        if self.after_id is None:
            self._update()

    def _stop_updates(self):
        if self.after_id:
            import tkinter as tk
            try:
                tk._default_root.after_cancel(self.after_id)
            except:
                pass
            self.after_id = None

    def _update(self):
        import tkinter as tk
        for task in list(self.tasks.values()):
            if task.running:
                if task.mode == 'stopwatch':
                    task.seconds += 1
                else:  # countdown
                    task.seconds -= 1
                    if task.seconds <= 0:
                        task.seconds = 0
                        self._complete_task(task.event_id, auto=True)
                        continue
        # 通知计时器视图刷新
        for cb in self.callbacks:
            try:
                cb()
            except:
                pass
        # 继续下一次更新
        root = tk._default_root
        if root and self.tasks:
            self.after_id = root.after(1000, self._update)
        else:
            self.after_id = None

    def _complete_task(self, event_id, auto=False):
        from database import Database
        db = Database()
        event = db.get_event(event_id)
        if event and not event['completed']:
            update_data = {'completed': 1}
            if not event.get('end_time'):
                from datetime import datetime
                update_data['end_time'] = datetime.now().strftime("%H:%M")
            db.update_event(event_id, update_data)
        self.remove_task(event_id)
        # 刷新今日视图
        if self.refresh_daily_callback:
            self.refresh_daily_callback()

    def complete_task(self, event_id):
        """手动完成计时（供界面调用）"""
        self._complete_task(event_id, auto=False)

    def register_callback(self, callback):
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def unregister_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

class TimerView:
    def __init__(self, parent, db, app_callback):
        self.parent = parent
        self.db = db
        self.app_callback = app_callback  # 用于打开计时窗口
        self.manager = TimerManager()
        self.manager.register_callback(self.refresh_list)

        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.frame, text="正在进行的计时任务", font=("font_family", 12)).pack(pady=5)

        columns = ("title", "time", "status")
        self.tree = ttk.Treeview(self.frame, columns=columns, show="headings", height=10)
        self.tree.heading("title", text="事件")
        self.tree.heading("time", text="时间")
        self.tree.heading("status", text="状态")
        self.tree.column("title", width=250)
        self.tree.column("time", width=100)
        self.tree.column("status", width=80)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree.bind("<Double-1>", self.on_item_double_click)

        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="暂停/继续", command=self.toggle_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="完成", command=self.complete_selected).pack(side=tk.LEFT, padx=2)

        self.refresh_list()

    def refresh_list(self):
        # 记录当前选中的事件ID（如果有）
        selected = self.tree.selection()
        selected_id = None
        if selected:
            selected_id = int(selected[0])  # 假设 iid 是整数形式的事件ID

        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 重新插入所有任务
        for event_id, task in self.manager.tasks.items():
            event = self.db.get_event(event_id)
            if not event:
                continue
            hours = task.seconds // 3600
            minutes = (task.seconds % 3600) // 60
            seconds = task.seconds % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            status = "运行中" if task.running else "暂停"
            self.tree.insert("", tk.END, iid=event_id, values=(event['title'], time_str, status))

        # 恢复选中（如果之前的选中项仍然存在）
        if selected_id and str(selected_id) in self.tree.get_children():
            self.tree.selection_set(str(selected_id))
            self.tree.focus(str(selected_id))  # 可选：将焦点移到该项
            self.tree.see(str(selected_id))  # 可选：滚动到可见区域

    def toggle_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        event_id = int(selected[0])
        task = self.manager.get_task(event_id)
        if task:
            task.running = not task.running
            self.refresh_list()

    def complete_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        event_id = int(selected[0])
        self.manager.complete_task(event_id)
        self.refresh_list()

    def on_item_double_click(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        event_id = int(selected[0])
        self.app_callback(event_id)  # 调用主应用的方法打开计时窗口