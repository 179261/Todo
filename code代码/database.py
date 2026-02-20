import sqlite3
import calendar
from datetime import datetime, date

class Database:
    """待办事项管理器的数据库操作类"""

    def __init__(self, db_path='todo.db'):
        """
        初始化数据库连接，创建表结构
        :param db_path: 数据库文件路径，默认为 'todo.db'
        """
        self.db_path = db_path
        self.conn = None
        self.connect()
        self.create_tables()

    def connect(self):
        """建立数据库连接，设置行工厂为Row以支持列名访问"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def create_tables(self):
        """创建事件表 events 和进度表 progress（如果不存在）"""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT NOT NULL,   -- 开始日期，格式 YYYY-MM-DD
                    end_date TEXT,               -- 结束日期，为空表示单日事件
                    start_time TEXT,              -- 开始时间，格式 HH:MM，可为空
                    end_time TEXT,                -- 结束时间，可为空
                    completed INTEGER DEFAULT 0,  -- 0未完成，1已完成
                    is_recurring INTEGER DEFAULT 0,
                    recurring_rule TEXT           -- 重复规则，如 "daily", "weekly mon,wed,fri"
                )
            ''')

            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    date TEXT NOT NULL,            -- 日期，格式 YYYY-MM-DD
                    value REAL,                     -- 进度数值，如背单词数量
                    completed INTEGER DEFAULT 0,    -- 该日是否完成
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                    UNIQUE(event_id, date)          -- 确保每个事件每天只有一条进度记录
                )
            ''')

    # ---------- 事件操作 ----------
    def add_event(self, event_data):
        """
        添加新事件
        :param event_data: 字典，包含字段：title, description, start_date, end_date,
                           start_time, end_time, completed, is_recurring, recurring_rule
                           (其中 title, start_date 为必填，其余可选)
        :return: 新插入事件的 id
        """
        required = ('title', 'start_date')
        for key in required:
            if key not in event_data:
                raise ValueError(f"缺少必要字段: {key}")

        columns = []
        values = []
        for key, value in event_data.items():
            if value is not None:  # 忽略 None 值，使用数据库默认值
                columns.append(key)
                values.append(value)

        placeholders = ','.join(['?'] * len(columns))
        col_str = ','.join(columns)
        sql = f"INSERT INTO events ({col_str}) VALUES ({placeholders})"

        with self.conn:
            cursor = self.conn.execute(sql, values)
            return cursor.lastrowid

    def update_event(self, event_id, event_data):
        """
        更新事件
        :param event_id: 事件 ID
        :param event_data: 字典，包含要更新的字段（字段名与表列一致）
        :return: 受影响的行数
        """
        if not event_data:
            return 0

        set_clause = ','.join([f"{key}=?" for key in event_data])
        values = list(event_data.values()) + [event_id]
        sql = f"UPDATE events SET {set_clause} WHERE id=?"

        with self.conn:
            cursor = self.conn.execute(sql, values)
            return cursor.rowcount

    def delete_event(self, event_id):
        """
        删除事件（关联的进度记录因外键 ON DELETE CASCADE 自动删除）
        :param event_id: 事件 ID
        :return: 受影响的行数
        """
        with self.conn:
            cursor = self.conn.execute("DELETE FROM events WHERE id=?", (event_id,))
            return cursor.rowcount

    def get_event(self, event_id):
        """
        根据 ID 获取单个事件
        :param event_id: 事件 ID
        :return: 字典形式的事件数据，若不存在返回 None
        """
        cursor = self.conn.execute("SELECT * FROM events WHERE id=?", (event_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_events(self):
        """
        获取所有事件
        :return: 字典列表
        """
        cursor = self.conn.execute("SELECT * FROM events ORDER BY start_date")
        return [dict(row) for row in cursor.fetchall()]

    def get_events_by_date(self, date):
        """
        获取指定日期相关的所有事件
        :param date: 字符串，格式 YYYY-MM-DD
        :return: 字典列表，包括单日事件和多天项目中覆盖该日期的事件
        """
        cursor = self.conn.execute('''
            SELECT * FROM events
            WHERE (end_date IS NULL AND start_date = ?)   -- 单日事件
               OR (end_date IS NOT NULL AND start_date <= ? AND end_date >= ?)  -- 多天覆盖
            ORDER BY start_time, start_date
        ''', (date, date, date))
        return [dict(row) for row in cursor.fetchall()]

    # ---------- 进度操作 ----------
    def add_progress(self, progress_data):
        """
        添加进度记录
        :param progress_data: 字典，包含 event_id, date, value, completed
        :return: 新插入进度的 id
        """
        required = ('event_id', 'date')
        for key in required:
            if key not in progress_data:
                raise ValueError(f"缺少必要字段: {key}")

        columns = []
        values = []
        for key in ('event_id', 'date', 'value', 'completed'):
            if key in progress_data and progress_data[key] is not None:
                columns.append(key)
                values.append(progress_data[key])

        placeholders = ','.join(['?'] * len(columns))
        col_str = ','.join(columns)
        sql = f"INSERT INTO progress ({col_str}) VALUES ({placeholders})"

        with self.conn:
            cursor = self.conn.execute(sql, values)
            return cursor.lastrowid

    def update_progress(self, progress_id, progress_data):
        """
        更新进度记录
        :param progress_id: 进度 ID
        :param progress_data: 字典，包含要更新的字段
        :return: 受影响的行数
        """
        if not progress_data:
            return 0

        set_clause = ','.join([f"{key}=?" for key in progress_data])
        values = list(progress_data.values()) + [progress_id]
        sql = f"UPDATE progress SET {set_clause} WHERE id=?"

        with self.conn:
            cursor = self.conn.execute(sql, values)
            return cursor.rowcount

    def get_progress_for_event_and_date(self, event_id, date):
        """
        获取某事件在指定日期的进度
        :param event_id: 事件 ID
        :param date: 日期字符串 YYYY-MM-DD
        :return: 字典形式的进度数据，若不存在返回 None
        """
        cursor = self.conn.execute(
            "SELECT * FROM progress WHERE event_id=? AND date=?",
            (event_id, date)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


    def get_latest_progress_before_date(self, event_id, date):
        """获取指定事件在指定日期之前最近一次的手动提交进度记录（按日期降序）"""
        cursor = self.conn.execute('''
            SELECT * FROM progress 
            WHERE event_id = ? AND date < ? 
            ORDER BY date DESC LIMIT 1
        ''', (event_id, date))
        row = cursor.fetchone()
        return dict(row) if row else None


    def get_progress_for_date(self, date):
        """
        获取指定日期所有事件的进度（附带事件标题等信息）
        :param date: 日期字符串 YYYY-MM-DD
        :return: 字典列表，每条包含事件信息和进度信息
        """
        cursor = self.conn.execute('''
            SELECT e.id, e.title, e.description, e.start_time, e.end_time,
                   p.id as progress_id, p.value, p.completed as day_completed
            FROM events e
            LEFT JOIN progress p ON e.id = p.event_id AND p.date = ?
            WHERE (e.end_date IS NULL AND e.start_date = ?)
               OR (e.end_date IS NOT NULL AND e.start_date <= ? AND e.end_date >= ?)
            ORDER BY e.start_time, e.start_date
        ''', (date, date, date, date))
        return [dict(row) for row in cursor.fetchall()]

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时关闭连接"""
        self.close()




# ---------- 简单测试 ----------
if __name__ == '__main__':
    # 创建数据库实例，会在当前目录生成 todo.db
    db = Database()

    # 清空测试数据（谨慎使用，仅用于演示）
    # db.conn.execute("DELETE FROM events")
    # db.conn.commit()


    # 这里演示正确做法：
    db = Database()  # 重新连接
    # 清空数据（可选）
    db.conn.execute("DELETE FROM events")
    db.conn.commit()

    event1_id = db.add_event({
        'title': '写周报',
        'description': '完成项目周报并邮件发送',
        'start_date': '2026-02-18',
        'start_time': '14:00',
        'end_time': '15:00',
        'completed': 0
    })
    print(f"添加单日事件，ID: {event1_id}")

    event2_id = db.add_event({
        'title': '背单词',
        'description': '每天背诵30个单词',
        'start_date': '2026-02-18',
        'end_date': '2026-02-24',
        'start_time': '08:00',
        'end_time': '08:30',
        'completed': 0
    })
    print(f"添加多天项目，ID: {event2_id}")

    # 查询某天的事件
    events_on_18th = db.get_events_by_date('2026-02-18')
    print("\n2026-02-18 的事件：")
    for ev in events_on_18th:
        print(f"  {ev['title']} (ID: {ev['id']}) 开始日期: {ev['start_date']} 结束日期: {ev['end_date']}")

    # 为多天项目添加进度（第二天）
    progress_id = db.add_progress({
        'event_id': event2_id,
        'date': '2026-02-19',
        'value': 30,
        'completed': 1
    })
    print(f"\n添加进度记录，ID: {progress_id}")

    # 获取某天所有事件及进度
    progress_on_19th = db.get_progress_for_date('2026-02-19')
    print("\n2026-02-19 事件及进度：")
    for item in progress_on_19th:
        print(f"  {item['title']} - 进度值: {item.get('value')}, 完成: {item.get('day_completed')}")

    # 关闭数据库连接
    db.close()

