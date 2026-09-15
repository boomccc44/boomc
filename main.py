import os
import sqlite3
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import flet as ft

DB_FILE = "pe_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS classes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        grade TEXT,
                        class_name TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS students (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        class_id INTEGER,
                        student_no TEXT,
                        name TEXT,
                        FOREIGN KEY(class_id) REFERENCES classes(id)
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_name TEXT,
                        unit TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS scores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id INTEGER,
                        item_id INTEGER,
                        score REAL,
                        FOREIGN KEY(student_id) REFERENCES students(id),
                        FOREIGN KEY(item_id) REFERENCES items(id)
                    )''')
    
    cursor.execute("SELECT COUNT(*) FROM items")
    if cursor.fetchone()[0] == 0:
        default_items = [
            ("身高", "cm"), ("体重", "kg"), ("肺活量", "ml"),
            ("50米跑", "秒"), ("坐位体前屈", "cm"), ("1分钟跳绳", "个"),
            ("1分钟仰卧起坐", "个"), ("立定跳远", "cm")
        ]
        cursor.executemany("INSERT INTO items (item_name, unit) VALUES (?, ?)", default_items)
        
    conn.commit()
    conn.close()

def main(page: ft.Page):
    page.title = "小学生体测成绩管理系统"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.window_width = 440
    page.window_height = 750
    
    init_db()
    
    title = ft.Text("🏫 体测成绩管理系统", size=22, weight=ft.FontWeight.BOLD)
    class_dropdown = ft.Dropdown(label="请先导入班级学生名单", width=300, options=[])
    status_text = ft.Text("", size=13, color="red")

    def load_classes_to_dropdown():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, grade, class_name FROM classes")
        classes = cursor.fetchall()
        conn.close()
        
        class_dropdown.options = []
        if classes:
            for c in classes:
                class_dropdown.options.append(ft.dropdown.Option(key=str(c[0]), text=f"{c[1]}{c[2]}"))
            class_dropdown.label = "选择已导入的班级"
        else:
            class_dropdown.label = "暂无班级，请先导入"
        page.update()

    load_classes_to_dropdown()

    grade_input = ft.TextField(label="年级 (例如: 三年级)", width=280)
    class_input = ft.TextField(label="班级 (例如: 一班)", width=280)
    path_input = ft.TextField(label="Excel文件路径", width=200, read_only=True)

    def select_file(e):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        root.destroy()
        if file_path:
            path_input.value = file_path
            page.update()

    browse_btn = ft.ElevatedButton("选择文件", width=75, on_click=select_file)
    path_row = ft.Row([path_input, browse_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=5)

    def confirm_import(e):
        g_text = grade_input.value.strip()
        c_text = class_input.value.strip()
        file_path = path_input.value.strip()
        
        if not g_text or not c_text:
            status_text.value = "错误：年级和班级名称不能为空！"
            page.update()
            return
            
        if not file_path or not os.path.exists(file_path):
            status_text.value = "错误：请先点击右侧按钮选择 Excel 文件！"
            page.update()
            return
        
        try:
            df = pd.read_excel(file_path)
            required_cols = ["学号", "姓名"]
            if not all(col in df.columns for col in required_cols):
                status_text.value = "错误：Excel 表格必须包含【学号】和【姓名】表头"
                page.update()
                return
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM classes WHERE grade=? AND class_name=?", (g_text, c_text))
            res = cursor.fetchone()
            if res:
                class_id = res[0]
            else:
                cursor.execute("INSERT INTO classes (grade, class_name) VALUES (?, ?)", (g_text, c_text))
                class_id = cursor.lastrowid
            
            imported_count = 0
            for _, row in df.iterrows():
                s_no = str(row["学号"]).strip()
                s_name = str(row["姓名"]).strip()
                cursor.execute("INSERT INTO students (class_id, student_no, name) VALUES (?, ?, ?)",
                               (class_id, s_no, s_name))
                imported_count += 1
                
            conn.commit()
            conn.close()
            
            load_classes_to_dropdown()
            status_text.value = f"成功为 {g_text}{c_text} 导入 {imported_count} 名学生！"
            grade_input.value = ""
            class_input.value = ""
            path_input.value = ""
            page.update()
            
        except Exception as ex:
            status_text.value = f"导入失败: {str(ex)}"
            page.update()

    import_btn = ft.ElevatedButton("📥 确认导入 Excel 名单", width=280, on_click=confirm_import)

    item_dropdown = ft.Dropdown(
        label="选择体测项目",
        width=280,
        value="1",
        options=[
            ft.dropdown.Option(key="1", text="身高 (cm)"),
            ft.dropdown.Option(key="2", text="体重 (kg)"),
            ft.dropdown.Option(key="3", text="肺活量 (ml)"),
            ft.dropdown.Option(key="4", text="50米跑 (秒)"),
            ft.dropdown.Option(key="5", text="坐位体前屈 (cm)"),
            ft.dropdown.Option(key="6", text="1分钟跳绳 (个)"),
            ft.dropdown.Option(key="7", text="1分钟仰卧起坐 (个)"),
            ft.dropdown.Option(key="8", text="立定跳远 (cm)"),
        ]
    )

    students_list_view = ft.ListView(expand=1, spacing=8, padding=5, width=320, height=380)

    def open_score_popup(e):
        project_dlg.open = False
        page.update()
        
        class_id = class_dropdown.value
        item_id = int(item_dropdown.value)
        
        students_list_view.controls.clear()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''SELECT s.id, s.student_no, s.name, sc.score 
                          FROM students s 
                          LEFT JOIN scores sc ON s.id = sc.student_id AND sc.item_id = ?
                          WHERE s.class_id = ? ORDER BY CAST(s.student_no AS INTEGER) ASC''', (item_id, class_id))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            status_text.value = "该班级暂无学生名单！"
            page.update()
            return

        for r in rows:
            student_id, s_no, s_name, current_score = r[0], r[1], r[2], r[3]
            score_val = str(current_score) if current_score is not None else ""
            
            score_input = ft.TextField(value=score_val, width=80, text_align=ft.TextAlign.CENTER)
            
            def make_save_handler(s_id, inp):
                def save_score(e):
                    try:
                        val = float(inp.value.strip()) if inp.value.strip() != "" else None
                        conn_db = sqlite3.connect(DB_FILE)
                        cur = conn_db.cursor()
                        cur.execute("SELECT id FROM scores WHERE student_id=? AND item_id=?", (s_id, item_id))
                        res = cur.fetchone()
                        if res:
                            if val is not None:
                                cur.execute("UPDATE scores SET score=? WHERE id=?", (val, res[0]))
                            else:
                                cur.execute("DELETE FROM scores WHERE id=?", (res[0],))
                        else:
                            if val is not None:
                                cur.execute("INSERT INTO scores (student_id, item_id, score) VALUES (?, ?, ?)", (s_id, item_id, val))
                        conn_db.commit()
                        conn_db.close()
                        inp.border_color = "green"
                        page.update()
                    except ValueError:
                        inp.border_color = "red"
                        page.update()
                return save_score

            # 用文字按钮替代 IconButton，彻底解决图标报错和红块问题
            save_btn = ft.ElevatedButton("保存", width=70, on_click=make_save_handler(student_id, score_input))
            
            row_item = ft.Row([
                ft.Text(f"{s_no}号 {s_name}", width=150, size=14, weight=ft.FontWeight.W_500),
                score_input,
                save_btn
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            
            students_list_view.controls.append(row_item)

        score_dlg.open = True
        page.update()

    project_dlg = ft.AlertDialog(
        title=ft.Text("请选择测试项目"),
        content=item_dropdown,
        actions=[
            ft.TextButton("取消", on_click=lambda _: setattr(project_dlg, "open", False) or page.update()),
            ft.ElevatedButton("确定，开始记录", on_click=open_score_popup),
        ],
    )
    page.overlay.append(project_dlg)

    score_dlg = ft.AlertDialog(
        title=ft.Text("📝 班级成绩录入 (按学号排序)"),
        content=ft.Container(content=students_list_view, height=400, width=340),
        actions=[
            ft.ElevatedButton("完成/关闭", on_click=lambda _: setattr(score_dlg, "open", False) or page.update()),
        ],
    )
    page.overlay.append(score_dlg)

    def get_class_score_dataframe(class_id):
        conn = sqlite3.connect(DB_FILE)
        students_df = pd.read_sql(f"SELECT id as student_id, student_no as 学号, name as 姓名 FROM students WHERE class_id={class_id} ORDER BY CAST(student_no AS INTEGER)", conn)
        if students_df.empty:
            conn.close()
            return None
        
        items_df = pd.read_sql("SELECT id, item_name, unit FROM items ORDER BY id", conn)
        scores_df = pd.read_sql("SELECT student_id, item_id, score FROM scores", conn)
        conn.close()
        
        pivot_scores = scores_df.pivot(index='student_id', columns='item_id', values='score')
        
        item_cols = {}
        for _, row in items_df.iterrows():
            item_cols[row['id']] = f"{row['item_name']} ({row['unit']})"
        pivot_scores = pivot_scores.rename(columns=item_cols)
        
        result_df = pd.merge(students_df, pivot_scores, left_on='student_id', right_index=True, how='left')
        result_df = result_df.drop(columns=['student_id'])
        return result_df

    view_table_container = ft.Column([], scroll=ft.ScrollMode.AUTO)
    
    view_dlg = ft.AlertDialog(
        title=ft.Text("📊 班级成绩总览"),
        content=ft.Container(content=view_table_container, width=380, height=420),
        actions=[
            ft.ElevatedButton("关闭", on_click=lambda _: setattr(view_dlg, "open", False) or page.update()),
        ],
    )
    page.overlay.append(view_dlg)

    def view_scores(e):
        if not class_dropdown.value:
            status_text.value = "请先选择要查看的班级！"
            page.update()
            return
        status_text.value = ""
        
        result_df = get_class_score_dataframe(class_dropdown.value)
        if result_df is None or result_df.empty:
            status_text.value = "该班级暂无学生数据！"
            page.update()
            return
            
        columns = [ft.DataColumn(ft.Text(col, weight=ft.FontWeight.BOLD)) for col in result_df.columns]
        rows = []
        for _, row in result_df.iterrows():
            cells = [ft.DataCell(ft.Text(str(val) if pd.notna(val) else "")) for val in row]
            rows.append(ft.DataRow(cells=cells))
            
        data_table = ft.DataTable(
            columns=columns,
            rows=rows,
        )
        
        view_table_container.controls = [
            ft.Row([data_table], scroll=ft.ScrollMode.AUTO)
        ]
        
        view_dlg.open = True
        page.update()

    def export_excel(e):
        if not class_dropdown.value:
            status_text.value = "请先选择要导出的班级！"
            page.update()
            return
        status_text.value = ""
        
        result_df = get_class_score_dataframe(class_dropdown.value)
        if result_df is None or result_df.empty:
            status_text.value = "该班级暂无数据可导出！"
            page.update()
            return
            
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="保存班级成绩"
        )
        root.destroy()
        
        if file_path:
            try:
                result_df.to_excel(file_path, index=False)
                status_text.value = f"成功导出至: {file_path}"
                page.update()
            except Exception as ex:
                status_text.value = f"导出失败: {str(ex)}"
                page.update()

    start_btn = ft.ElevatedButton("📝 开始记录成绩", width=280)
    
    action_row = ft.Row([
        ft.ElevatedButton("📊 查看成绩", width=135, on_click=view_scores),
        ft.ElevatedButton("📤 导出 Excel", width=135, on_click=export_excel)
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)

    def start_recording(e):
        if not class_dropdown.value:
            status_text.value = "请先选择要记录成绩的班级！"
            page.update()
            return
        status_text.value = ""
        project_dlg.open = True
        page.update()

    start_btn.on_click = start_recording

    page.add(
        ft.Column([
            title,
            ft.Container(height=10),
            grade_input,
            class_input,
            path_row,
            ft.Container(height=5),
            import_btn,
            ft.Divider(height=20),
            class_dropdown,
            ft.Container(height=5),
            start_btn,
            ft.Container(height=5),
            action_row,
            ft.Container(height=10),
            status_text
        ], alignment=ft.MainAxisAlignment.CENTER)
    )

ft.app(target=main)