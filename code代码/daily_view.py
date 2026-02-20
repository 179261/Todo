import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

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

class DailyView:
    """当日规划视图"""
    def __init__(self, parent, db, app):
        self.parent = parent
        self.db = db
        self.app = app
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.sort_column = None      # 当前排序列
        self.sort_reverse = False     # 排序方向

        # 创建主框架
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # 顶部：日期和按钮
        top_frame = ttk.Frame(self.frame)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        self.date_label = ttk.Label(top_frame, text=f"日期：{self.current_date}", font=("Arial", 12))
        self.date_label.pack(side=tk.LEFT, padx=5)

        add_btn = ttk.Button(top_frame, text="添加事项", command=self.add_event)
        add_btn.pack(side=tk.RIGHT, padx=5)

        quick_add_btn = ttk.Button(top_frame, text="快速添加", command=self.quick_add)
        quick_add_btn.pack(side=tk.RIGHT, padx=5)

        refresh_btn = ttk.Button(top_frame, text="刷新", command=self.refresh_to_today)
        refresh_btn.pack(side=tk.RIGHT, padx=5)

        # 中间：事项列表（Treeview + 滚动条）
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("title", "start_time", "end_time", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # 定义列并绑定点击排序
        self.tree.heading("title", text="标题", command=lambda: self.treeview_sort_column("title"))
        self.tree.heading("start_time", text="开始时间", command=lambda: self.treeview_sort_column("start_time"))
        self.tree.heading("end_time", text="结束时间")
        self.tree.heading("status", text="状态", command=lambda: self.treeview_sort_column("status"))

        self.tree.column("title", width=200)
        self.tree.column("start_time", width=100)
        self.tree.column("end_time", width=100)
        self.tree.column("status", width=80)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # 绑定双击事项（编辑）
        self.tree.bind("<Double-1>", lambda e: self.edit_event())

        # 底部：操作按钮
        bottom_frame = ttk.Frame(self.frame)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)

        complete_btn = ttk.Button(bottom_frame, text="标记完成", command=self.toggle_complete)
        complete_btn.pack(side=tk.LEFT, padx=2)

        timer_btn = ttk.Button(bottom_frame, text="计时", command=self.open_timer)
        timer_btn.pack(side=tk.LEFT, padx=2)

        edit_btn = ttk.Button(bottom_frame, text="编辑", command=self.edit_event)
        edit_btn.pack(side=tk.LEFT, padx=2)

        delete_btn = ttk.Button(bottom_frame, text="删除", command=self.delete_event)
        delete_btn.pack(side=tk.LEFT, padx=2)

        progress_btn = ttk.Button(bottom_frame, text="提交进度", command=self.submit_progress)
        progress_btn.pack(side=tk.LEFT, padx=2)

        # 初始加载事项
        self.load_events()

    def load_events(self):
        """从数据库加载当天事项，并根据当前排序重新填充"""
        events = self.db.get_events_by_date(self.current_date)
        if self.sort_column:
            events = self._sort_events(events, self.sort_column, self.sort_reverse)
        self._fill_tree(events)
        # 刷新日历
        if hasattr(self.app, 'refresh_calendar'):
            self.app.refresh_calendar()

    def _fill_tree(self, events):
        """根据事件列表填充Treeview"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for ev in events:
            is_multi_day = ev['end_date'] is not None and ev['end_date'] != ev['start_date']

            if is_multi_day:
                progress = self.db.get_progress_for_event_and_date(ev['id'], self.current_date)
                if progress:
                    status = f"已提交 ({progress['value']}%)"
                else:
                    latest = self.db.get_latest_progress_before_date(ev['id'], self.current_date)
                    if latest:
                        status = f"自动延续 ({latest['value']})"
                    else:
                        status = "未提交"
            else:
                status = "已完成" if ev['completed'] else "未完成"

            start = ev['start_time'] if ev['start_time'] else ""
            end = ev['end_time'] if ev['end_time'] else ""
            self.tree.insert("", tk.END, iid=ev['id'], values=(ev['title'], start, end, status))

    def _sort_events(self, events, col, reverse):
        """对事件列表进行排序"""
        if col == "title":
            # 按标题排序，实际是按添加顺序（id）
            events.sort(key=lambda x: x['id'], reverse=reverse)
        elif col == "start_time":
            def time_key(ev):
                t = ev.get('start_time')
                if not t:
                    return (1, None)  # 空值放最后
                try:
                    hour, minute = map(int, t.split(':'))
                    return (0, hour * 60 + minute)  # 有效时间按分钟数排序
                except:
                    return (1, None)  # 格式错误放最后
            events.sort(key=time_key, reverse=reverse)
        elif col == "status":
            def status_key(ev):
                # 对于多天项目，当天是否完成由进度决定
                if ev['end_date'] and ev['end_date'] != ev['start_date']:
                    progress = self.db.get_progress_for_event_and_date(ev['id'], self.current_date)
                    day_completed = 1 if progress else 0
                else:
                    day_completed = ev['completed']
                # 已完成（1）在前还是未完成（0）在前由 reverse 决定
                # 注意：reverse=True 表示降序，即已完成在前（1在前）
                return (day_completed, ev['id'])
            events.sort(key=status_key, reverse=reverse)
        return events

    def treeview_sort_column(self, col):
        """点击列标题时的排序处理"""
        if self.sort_column == col:
            # 同一列，切换方向
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            # 默认方向：状态列第一次点击时已完成在前（降序），其他列升序
            if col == "status":
                self.sort_reverse = True
            else:
                self.sort_reverse = False
        self.load_events()  # 重新加载并应用排序

    def refresh_to_today(self):
        """刷新到今天的日期"""
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.date_label.config(text=f"日期：{self.current_date}")
        self.load_events()


    def get_selected_event_id(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个事项")
            return None
        return int(selected[0])

    def add_event(self):
        self._event_dialog("添加事项", None)

    def edit_event(self):
        event_id = self.get_selected_event_id()
        if event_id is None:
            return
        event = self.db.get_event(event_id)
        if event:
            self._event_dialog("编辑事项", event)

    def delete_event(self):
        event_id = self.get_selected_event_id()
        if event_id is None:
            return
        if messagebox.askyesno("确认删除", "确定要删除该事项吗？"):
            self.db.delete_event(event_id)
            self.load_events()

    def toggle_complete(self):
        """切换完成状态（仅单日事项可用）"""
        event_id = self.get_selected_event_id()
        if event_id is None:
            return
        event = self.db.get_event(event_id)
        if not event:
            return

        # 检查是否为多天项目
        if event['end_date'] is not None and event['end_date'] != event['start_date']:
            messagebox.showinfo("提示", "多天项目请使用「提交进度」按钮记录每日完成情况")
            return

        new_status = 0 if event['completed'] else 1
        update_data = {'completed': new_status}
        if new_status == 1 and not event.get('end_time'):
            update_data['end_time'] = self._get_current_time_str()
        self.db.update_event(event_id, update_data)
        self.load_events()

    def submit_progress(self):
        """提交多天项目的当日进度"""
        event_id = self.get_selected_event_id()
        if event_id is None:
            return
        event = self.db.get_event(event_id)
        if not event:
            return

        # 检查是否为多天项目
        if event['end_date'] is None or event['end_date'] == event['start_date']:
            messagebox.showinfo("提示", "只有多天项目可以提交进度")
            return

        # 弹出进度输入对话框
        dialog = tk.Toplevel(self.parent)
        center_window(self.parent, dialog)  # 居中
        dialog.title("提交进度")
        dialog.geometry("350x250")
        dialog.transient(self.parent)
        dialog.grab_set()

        ttk.Label(dialog, text=f"事项：{event['title']}").pack(pady=5)
        ttk.Label(dialog, text=f"日期：{self.current_date}").pack(pady=5)

        ttk.Label(dialog, text="进度值：(0-100)%").pack()
        value_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=value_var, width=20).pack(pady=5)

        def save():
            value_str = value_var.get().strip()
            if not value_str:
                messagebox.showerror("错误", "进度值不能为空")
                return
            try:
                value = float(value_str)
            except ValueError:
                messagebox.showerror("错误", "请输入数字")
                return

            # 检查是否已有进度记录
            existing = self.db.get_progress_for_event_and_date(event_id, self.current_date)
            if existing:
                # 更新
                self.db.update_progress(existing['id'], {'value': value, 'completed': 1})
            else:
                # 新增
                self.db.add_progress({
                    'event_id': event_id,
                    'date': self.current_date,
                    'value': value,
                    'completed': 1
                })
            dialog.destroy()
            self.load_events()

        ttk.Button(dialog, text="保存", command=save).pack(pady=5)
        ttk.Button(dialog, text="取消", command=dialog.destroy).pack()

    def open_timer(self):
        event_id = self.get_selected_event_id()
        if event_id is None:
            return
        # 导入放在方法内避免循环导入
        from timer_view import TimerWindow
        TimerWindow(self.parent, self.db, event_id)

    def _get_current_time_str(self):
        return datetime.now().strftime("%H:%M")

    def set_date(self, date_str):
        self.current_date = date_str
        self.date_label.config(text=f"日期：{self.current_date}")
        self.load_events()

    def quick_add(self):
        """一键快速添加重复事项（如背单词）"""
        dialog = tk.Toplevel(self.parent)
        center_window(self.parent, dialog)
        dialog.title("快速添加重复事项")
        dialog.geometry("400x300")
        dialog.transient(self.parent)
        dialog.grab_set()

        ttk.Label(dialog, text="事项名称：").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        name_var = tk.StringVar(value="背单词")
        ttk.Entry(dialog, textvariable=name_var, width=25).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="每天数量：").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        count_var = tk.StringVar(value="1")
        ttk.Entry(dialog, textvariable=count_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(dialog, text="持续天数：").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        days_var = tk.StringVar(value="30")
        ttk.Entry(dialog, textvariable=days_var, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(dialog, text="开始日期：").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        start_date_var = tk.StringVar(value=self.current_date)
        ttk.Entry(dialog, textvariable=start_date_var, width=15).grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(dialog, text="开始时间：").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        time_var = tk.StringVar(value="08:00")
        ttk.Entry(dialog, textvariable=time_var, width=10).grid(row=4, column=1, padx=5, pady=5, sticky="w")

        def generate():
            try:
                name = name_var.get().strip()
                count = int(count_var.get())
                days = int(days_var.get())
                start_date = start_date_var.get().strip()
                start_time = time_var.get().strip()
                if not name or days <= 0:
                    raise ValueError
                # 解析开始日期
                try:
                    current = datetime.strptime(start_date, "%Y-%m-%d").date()
                except:
                    messagebox.showerror("错误", "日期格式应为 YYYY-MM-DD")
                    return
            except:
                messagebox.showerror("错误", "请填写有效数值")
                return

            # 批量生成事项
            created = 0
            for i in range(days):
                date_str = current.strftime("%Y-%m-%d")
                title = f"{name} 第{i+1}天"
                self.db.add_event({
                    'title': title,
                    'description': f"每天{count}个",
                    'start_date': date_str,
                    'end_date': None,  # 单日事项
                    'start_time': start_time,
                    'end_time': None,
                    'completed': 0,
                    'is_recurring': 0,
                    'recurring_rule': None
                })
                created += 1
                current += timedelta(days=1)

            messagebox.showinfo("成功", f"已生成 {created} 个事项")
            dialog.destroy()
            self.load_events()

        ttk.Button(dialog, text="生成", command=generate).grid(row=5, column=0, columnspan=2, pady=10)

    def _event_dialog(self, title, event=None):
        """通用事件添加/编辑对话框（增加开始时间控制）"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(title)
        dialog.geometry("550x400")
        center_window(self.parent, dialog)
        dialog.transient(self.parent)
        dialog.grab_set()

        # 变量
        title_var = tk.StringVar()
        desc_var = tk.StringVar()
        start_date_var = tk.StringVar(value=self.current_date)
        end_date_var = tk.StringVar()  # 可为空
        start_time_var = tk.StringVar()
        end_time_var = tk.StringVar()
        completed_var = tk.IntVar()
        # 新增：是否设置开始时间
        enable_start_time = tk.BooleanVar(value=True)

        if event:
            title_var.set(event['title'])
            desc_var.set(event['description'] or "")
            start_date_var.set(event['start_date'])
            end_date_var.set(event['end_date'] or "")
            start_time_var.set(event['start_time'] or "")
            end_time_var.set(event['end_time'] or "")
            completed_var.set(event['completed'])
            # 如果原事件没有开始时间，则取消勾选
            if not event.get('start_time'):
                enable_start_time.set(False)

        # 表单
        row = 0
        ttk.Label(dialog, text="标题*：").grid(row=row, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(dialog, textvariable=title_var, width=30).grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttk.Label(dialog, text="描述：").grid(row=row, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(dialog, textvariable=desc_var, width=30).grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttk.Label(dialog, text="开始日期 (YYYY-MM-DD)：").grid(row=row, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(dialog, textvariable=start_date_var, width=20).grid(row=row, column=1, padx=5, pady=5, sticky="w")

        row += 1
        ttk.Label(dialog, text="结束日期 (留空为单日)：").grid(row=row, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(dialog, textvariable=end_date_var, width=20).grid(row=row, column=1, padx=5, pady=5, sticky="w")

        row += 1
        # 开始时间控制行：标签 + (复选框+输入框)
        ttk.Label(dialog, text="开始时间：").grid(row=row, column=0, padx=5, pady=5, sticky="e")
        time_frame = ttk.Frame(dialog)
        time_frame.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(time_frame, text="启用", variable=enable_start_time,
                        command=lambda: toggle_start_time()).pack(side=tk.LEFT, padx=(0, 5))
        self.start_time_entry = ttk.Entry(time_frame, textvariable=start_time_var, width=17, state='normal')
        self.start_time_entry.pack(side=tk.LEFT)

        def toggle_start_time():
            if enable_start_time.get():
                self.start_time_entry.config(state='normal')
            else:
                self.start_time_entry.config(state='disabled')
                start_time_var.set("")

        toggle_start_time()  # 初始化状态

        row += 1
        ttk.Label(dialog, text="结束时间 (HH:MM)：").grid(row=row, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(dialog, textvariable=end_time_var, width=20).grid(row=row, column=1, padx=5, pady=5, sticky="w")

        row += 1
        # 如果有事件，显示完成状态复选框
        if event:
            ttk.Label(dialog, text="已完成：").grid(row=row, column=0, padx=5, pady=5, sticky="e")
            ttk.Checkbutton(dialog, variable=completed_var).grid(row=row, column=1, padx=5, pady=5, sticky="w")
            row += 1

        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)

        def save():
            title = title_var.get().strip()
            if not title:
                messagebox.showerror("错误", "标题不能为空")
                return

            start_date = start_date_var.get().strip()
            if not start_date:
                messagebox.showerror("错误", "开始日期不能为空")
                return
            # 验证开始日期格式
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("错误", "开始日期格式不正确，应为 YYYY-MM-DD")
                return

            end_date = end_date_var.get().strip() or None
            if end_date:
                try:
                    datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    messagebox.showerror("错误", "结束日期格式不正确，应为 YYYY-MM-DD")
                    return


            end_time = end_time_var.get().strip() or None

            # 处理开始时间
            if enable_start_time.get():
                start_time = start_time_var.get().strip()
                if not start_time:
                    # 判断是否为多天项目
                    is_multi_day = end_date is not None and end_date != start_date
                    if is_multi_day:
                        # 多天项目不自动填充开始时间
                        start_time = None
                    else:
                        # 单日项目自动填充当前时间
                        start_time = self._get_current_time_str()
            else:
                start_time = None

            data = {
                'title': title,
                'description': desc_var.get().strip() or None,
                'start_date': start_date,
                'end_date': end_date,
                'start_time': start_time,
                'end_time': end_time,
                'completed': completed_var.get() if event else 0,
                'is_recurring': 0,  # 暂时保留但未使用
                'recurring_rule': None
            }

            if event:
                self.db.update_event(event['id'], data)
                new_id = event['id']
            else:
                new_id = self.db.add_event(data)
                # 检查是否需要屏蔽提醒
                if start_time == self._get_current_time_str():
                    self.app.mark_event_as_notified(new_id)

            dialog.destroy()
            self.load_events()

        ttk.Button(btn_frame, text="保存", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

