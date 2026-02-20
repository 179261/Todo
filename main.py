import os
import warnings

# 1. 隐藏 pygame 欢迎信息
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# 忽略 pygame.pkgdata 模块中的 UserWarning（弃用警告）
warnings.filterwarnings("ignore", category=UserWarning, module="pygame.pkgdata")


import tkinter as tk
from tkinter import ttk , messagebox
import pystray
from PIL import Image
import threading
from datetime import datetime
import pygame
from database import Database  # 导入数据库类
from daily_view import DailyView      # 假设您已将 DailyView 分离
from calendar_view import CalendarView
from timer_view import TimerWindow,TimerView,TimerManager

import ctypes
import sys

# 在Windows上启用DPI感知
if sys.platform == 'win32':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 每个显示器独立DPI感知
    except AttributeError:
        ctypes.windll.user32.SetProcessDPIAware()       # 旧版本Windows



# ==================== 主应用 ====================
class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("待办事项管理器")
        self.root.geometry("800x600")

        # ---- 美化设置 ----
        self.apply_styling()

        # 初始化数据库
        self.db = Database()

        # 初始化计时管理器（单例）
        self.manager = TimerManager()

        # 创建主标签页
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 创建今日标签页
        self.create_tab_today()
        # 创建日历标签页
        self.create_tab_calendar()
        # 创建计时器标签页
        self.create_tab_timer()

        # 设置窗口关闭协议（隐藏到托盘）
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        # 创建系统托盘图标
        self.tray_icon = None
        self.create_tray_icon()

        # 设置计时管理器刷新今日视图的回调
        self.manager.refresh_daily_callback = self.daily_view.load_events

        # 添加提醒相关属性
        self.reminder_sound = r"C:\Windows\Media\Alarm01.wav"  # 您的声音文件路径，请根据实际位置修改
        self.notified_events_today = set()  # 记录今天已经提醒过的事件ID，避免重复弹窗
        self.last_check_date = datetime.now().strftime("%Y-%m-%d")  # 记录检查的日期，用于每日重置

        # 初始化 pygame 混音器
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"初始化音频失败: {e}")

        # 启动提醒检查（每30秒检查一次）
        self.start_reminder_check()

    def apply_styling(self):
        """应用ttk样式和字体"""
        style = ttk.Style()
        # 设置主题
        available = style.theme_names()

        if 'vista' in available:
            style.theme_use('vista')
        elif 'clam' in available:
            style.theme_use('clam')
        # 字体
        if sys.platform == 'win32':
            font_family = '微软雅黑'
        else:
            font_family = 'Helvetica'
        default_font = (font_family, 10)
        style.configure('.', font=default_font)
        # 自定义按钮
        #style.configure('TButton', padding=6, relief='flat')
        #style.map('TButton',
        #          background=[('active', '#e6e6e6')])
        # Treeview样式
        style.configure('Treeview', rowheight=25, font=default_font)
        style.configure('Treeview.Heading', font=(font_family, 10, 'bold'))
        style.map('Treeview',
                  background=[('selected', '#4a7a9c')],
                  foreground=[('selected', 'white')])


    def create_tab_today(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="今日")
        self.daily_view = DailyView(frame, self.db, self)  # 传入主应用实例

    def create_tab_calendar(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="日历")
        self.calendar_view = CalendarView(frame, self.db, self.set_daily_date)

    def create_tab_timer(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="计时器")
        # 传入 self.open_timer_for_event 作为回调，用于双击打开计时窗口
        self.timer_view = TimerView(frame, self.db, self.open_timer_for_event)

    def open_timer_for_event(self, event_id):
        """根据事件ID打开计时窗口"""
        TimerWindow(self.root, self.db, event_id)




    def create_tray_icon(self):
        """创建系统托盘图标"""
        # 生成一个简单的图标（如果没有图片文件）
        image = Image.open("resources/icon.png")

        menu = (
            pystray.MenuItem("显示窗口", self.show_window),
            pystray.MenuItem("退出", self.quit_app)
        )

        self.tray_icon = pystray.Icon("todo_manager", image, "待办事项管理器", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self):
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()

    def quit_app(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()

    def switch_to_tab(self, tab_index):
        self.notebook.select(tab_index)

    def set_daily_date(self, date_str):
        self.daily_view.set_date(date_str)
        self.switch_to_tab(0)



    def start_reminder_check(self):
        """启动定时检查提醒"""
        self.check_reminders()
        self.root.after(30000, self.start_reminder_check)

    def check_reminders(self):
        """检查是否有事件开始时间到达"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M")

        # 如果日期变更，清空已提醒集合
        if today != self.last_check_date:
            self.notified_events_today.clear()
            self.last_check_date = today

        # 获取今天的所有事件
        events = self.db.get_events_by_date(today)
        for ev in events:
            # 只检查未完成的事件，并且有开始时间
            if ev['completed'] == 0 and ev['start_time']:
                if ev['start_time'] == current_time:
                    event_id = ev['id']
                    if event_id not in self.notified_events_today:
                        self.notified_events_today.add(event_id)
                        self.show_reminder(ev['title'])

    def show_reminder(self, title):
        """显示提醒窗口并播放声音"""
        # 先停止当前可能正在播放的音乐（避免重叠）
        pygame.mixer.music.stop()

        # 播放声音（异步）
        if os.path.exists(self.reminder_sound):
            try:
                pygame.mixer.music.load(self.reminder_sound)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"播放声音失败: {e}")
        else:
            print(f"提醒声音文件不存在: {self.reminder_sound}")

        # 创建提醒窗口
        reminder = tk.Toplevel(self.root)
        reminder.title("事项提醒")
        reminder.geometry("300x150")
        reminder.transient(self.root)
        reminder.grab_set()

        # 居中显示
        reminder.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - reminder.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - reminder.winfo_height()) // 2
        reminder.geometry(f"+{x}+{y}")

        ttk.Label(reminder, text="⏰ 时间到！", font=("微软雅黑", 12, "bold")).pack(pady=10)
        ttk.Label(reminder, text=f"事项：{title}", wraplength=250).pack(pady=5)

        def close_reminder():
            """关闭窗口并停止音乐"""
            pygame.mixer.music.stop()
            reminder.destroy()

        # “知道了”按钮停止音乐并关闭窗口
        ttk.Button(reminder, text="知道了", command=close_reminder).pack(pady=10)

        # 同时处理窗口的“X”关闭按钮
        reminder.protocol("WM_DELETE_WINDOW", close_reminder)

    def mark_event_as_notified(self, event_id):
        """将事件ID加入已提醒集合，避免当天再次提醒"""
        self.notified_events_today.add(event_id)


if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()