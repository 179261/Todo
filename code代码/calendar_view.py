import tkinter as tk
from tkinter import ttk
import calendar
from datetime import datetime, timedelta,date

class CalendarView:
    """日历视图"""
    def __init__(self, parent, db, app_callback):
        self.parent = parent
        self.db = db
        self.app_callback = app_callback

        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
        self.selected_date = None

        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # 顶部导航
        nav_frame = ttk.Frame(self.frame)
        nav_frame.pack(fill=tk.X, padx=5, pady=5)

        prev_btn = ttk.Button(nav_frame, text="< 上个月", command=self.prev_month)
        prev_btn.pack(side=tk.LEFT, padx=2)

        self.month_label = ttk.Label(nav_frame, text="", font=("Arial", 12, "bold"))
        self.month_label.pack(side=tk.LEFT, expand=True)

        next_btn = ttk.Button(nav_frame, text="下个月 >", command=self.next_month)
        next_btn.pack(side=tk.RIGHT, padx=2)

        # 星期标题
        week_frame = ttk.Frame(self.frame)
        week_frame.pack(fill=tk.X, padx=5)
        week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i, day in enumerate(week_days):
            label = ttk.Label(week_frame, text=day, width=4, anchor="center", font=("Arial", 10, "bold"))
            label.grid(row=0, column=i, padx=1, pady=2, sticky="nsew")
            week_frame.columnconfigure(i, weight=1)

        # 日历网格容器
        self.calendar_frame = ttk.Frame(self.frame)
        self.calendar_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 下方：选中日期的事件列表
        list_frame = ttk.LabelFrame(self.frame, text="选中日期的事件")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("title", "time", "status")
        self.event_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=6)
        self.event_tree.heading("title", text="标题")
        self.event_tree.heading("time", text="时间")
        self.event_tree.heading("status", text="状态")
        self.event_tree.column("title", width=200)
        self.event_tree.column("time", width=120)
        self.event_tree.column("status", width=80)

        v_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.event_tree.yview)
        self.event_tree.configure(yscrollcommand=v_scroll.set)
        self.event_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.event_tree.bind("<Double-1>", self.on_event_double_click)

        self.draw_calendar()

    def prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.draw_calendar()

    def next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.draw_calendar()

    def get_event_dates_in_month(self, year, month):
        """返回指定月份内有事件的所有日期（包括多天项目覆盖的每一天）"""
        # 获取当月所有事件（单日 + 多天）
        all_events = self.db.get_all_events()
        event_dates = set()

        # 计算当月第一天和最后一天
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year+1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month+1, 1) - timedelta(days=1)

        for ev in all_events:
            start = datetime.strptime(ev['start_date'], "%Y-%m-%d").date()
            if ev['end_date']:
                end = datetime.strptime(ev['end_date'], "%Y-%m-%d").date()
            else:
                end = start

            # 如果事件区间与当月有交集
            if end >= first_day and start <= last_day:
                # 交集起始
                intersect_start = max(start, first_day)
                intersect_end = min(end, last_day)
                current = intersect_start
                while current <= intersect_end:
                    event_dates.add(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)

        return event_dates

    def draw_calendar(self):
        # 清除旧网格
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        self.month_label.config(text=f"{self.current_year}年{self.current_month:02d}月")

        cal = calendar.monthcalendar(self.current_year, self.current_month)
        event_dates = self.get_event_dates_in_month(self.current_year, self.current_month)

        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    label = ttk.Label(self.calendar_frame, text="", relief="solid", borderwidth=1)
                else:
                    date_str = f"{self.current_year:04d}-{self.current_month:02d}-{day:02d}"
                    has_event = date_str in event_dates
                    bg_color = "lightblue" if has_event else "white"
                    label = tk.Label(self.calendar_frame, text=str(day), relief="solid", borderwidth=1,
                                     bg=bg_color, font=("Arial", 10))
                    label.bind("<Button-1>", lambda e, d=date_str: self.on_date_click(d))
                    label.bind("<Double-Button-1>", lambda e, d=date_str: self.on_date_double_click(d))

                label.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
                self.calendar_frame.grid_rowconfigure(r, weight=1)
                self.calendar_frame.grid_columnconfigure(c, weight=1)

        # 清除下方事件列表
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)

    def on_date_click(self, date_str):
        self.selected_date = date_str
        events = self.db.get_events_by_date(date_str)
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
        for ev in events:
            time_str = ""
            if ev['start_time']:
                time_str = ev['start_time']
                if ev['end_time']:
                    time_str += f"-{ev['end_time']}"
            # 判断多天项目
            if ev['end_date'] and ev['end_date'] != ev['start_date']:
                progress = self.db.get_progress_for_event_and_date(ev['id'], date_str)
                if progress:
                    status = f"已提交 ({progress['value']}%)"
                else:
                    latest = self.db.get_latest_progress_before_date(ev['id'], date_str)
                    if latest:
                        status = f"自动延续 ({latest['value']}%)"
                    else:
                        status = "未提交"
            else:
                status = "已完成" if ev['completed'] else "未完成"
            self.event_tree.insert("", tk.END, iid=ev['id'], values=(ev['title'], time_str, status))

    def on_date_double_click(self, date_str):
        if self.app_callback:
            self.app_callback(date_str)

    def on_event_double_click(self, event):
        selected = self.event_tree.selection()
        if selected and self.selected_date:
            if self.app_callback:
                self.app_callback(self.selected_date)