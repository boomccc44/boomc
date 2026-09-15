import os
import sqlite3
import csv
import flet as ft

def main(page: ft.Page):
    page.title = "小学生体测成绩管理系统"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.window_width = 440
    page.window_height = 750

    # 适配移动端与桌面端的数据库及文件路径
    if page.platform in [ft.PagePlatform.ANDROID, ft.PagePlatform.IOS]:
        db_dir = page.get_app_storage_dir()
        default_search_dir = "/storage/emulated/0/Download"
    else:
        db_dir = "."
        default_search_dir = "."
        
    os.makedirs(db_dir, exist_ok=True)
    DB_FILE = os.path.join(db_dir, "pe_database.db")

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

    init_db()
    
    title = ft.Text("🏫 体测成绩管理系统", size=22, weight=ft.FontWeight.BOLD)
    class_dropdown = ft.Dropdown(label="请先导入班级学生名单", width=300, options=[])
    status_text = ft.Text("", size=12, color=ft.Colors.RED)

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
    path_input = ft.TextField(label="CSV文件名 (如: students.csv)", width=195)

    def scan_download_folder(e):
        try:
            target_dir = default_search_dir
            if os.path.exists(target_dir):
                files = [f for f in os.listdir(target_dir) if f.endswith('.csv')]
                if files:
                    path_input.value = os.path.join(target_dir, files[0])
                    status_text.value = f"已自动匹配到: {files[0]}"
                else:
                    status_text.value = "在 Download 目录未找到 CSV 文件"
            else:
                path_input.value = "students.csv"
                status_text.value = "请将 CSV 文件放入手机 Download 目录"
            page.update()
        except Exception as ex:
            status_text.value = f"查找文件出错: {str(ex)}"
            page.update()

    scan_btn = ft.OutlinedButton("自动查找", width=80, on_click=scan_download_folder)
    path_row = ft.Row([path_input, scan_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=5)

    def confirm_import(e):
        g_text = grade_input.value.strip()
        c_text = class_input.value.strip()
        file_path = path_input.value.strip()
        
        if not g_text or not c_text:
            status_text.value = "错误：年级和班级名称不能为空！"
            page.update()
            return
            
        if not file_path:
            status_text.value = "错误：请输入文件名或点击自动查找！"
            page.update()
            return
            
        if not os.path.dirname(file_path):
            potential_path = os.path.join(default_search_dir, file_path)
            if os.path.exists(potential_path):
                file_path = potential_path
        
        if not os.path.exists(file_path):
            status_text.value = f"错误：找不到文件，请确认已放入 Download 目录"
            page.update()
            return
        
        try:
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
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not all(col in reader.fieldnames for col in ["学号", "姓名"]):
                    status_text.value = "错误：CSV 表格必须包含【学号】和【姓名】表头"
                    conn.close()
                    page.update()
                    return
                
                for row in reader:
                    s_no = str(row["学号"]).strip()
                    s_name = str(row["姓名"]).strip()
                    if s_no and s_name:
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

    import_btn = ft.ElevatedButton("📥 确认导入 CSV 名单", width=280, on_click=confirm_import)

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
                        page.update()
                    except ValueError:
                        page.update()
                return save_score

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

    def get_class_score_data(class_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, student_no, name FROM students WHERE class_id=? ORDER BY CAST(student_no AS INTEGER)", (class_id,))
        students = cursor.fetchall()
        if not students:
            conn.close()
            return None, None
        
        cursor.execute("SELECT id, item_name, unit FROM items ORDER BY id")
        items = cursor.fetchall()
        
        cursor.execute("SELECT student_id, item_id, score FROM scores")
        scores = cursor.fetchall()
        conn.close()
        
        scores_map = {(s[0], s[1]): s[2] for s in scores}
        
        headers = ["学号", "姓名"] + [f"{item[1]} ({item[2]})" for item in items]
        
        rows_data = []
        for s in students:
            s_id, s_no, s_name = s[0], s[1], s[2]
            row = [s_no, s_name]
            for item in items:
                item_id = item[0]
                val = scores_map.get((s_id, item_id), "")
                row.append(val if val is not None else "")
            rows_data.append(row)
            
        return headers, rows_data

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
        
        headers, rows_data = get_class_score_data(class_dropdown.value)
        if not headers or not rows_data:
            status_text.value = "该班级暂无学生数据！"
            page.update()
            return
            
        columns = [ft.DataColumn(ft.Text(h, weight=ft.FontWeight.BOLD)) for h in headers]
        rows = []
        for rd in rows_data:
            cells = [ft.DataCell(ft.Text(str(val))) for val in rd]
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
            
        headers, rows_data = get_class_score_data(class_dropdown.value)
        if not headers or not rows_data:
            status_text.value = "该班级暂无数据可导出！"
            page.update()
            return
            
        try:
            # 查询当前班级名称，用于拼出一个清晰的文件名
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT grade, class_name FROM classes WHERE id=?", (class_dropdown.value,))
            c_info = cursor.fetchone()
            conn.close()
            
            class_tag = f"{c_info[0]}{c_info[1]}" if c_info else "class"
            filename = f"体测成绩_{class_tag}.csv"
            
            # 根据平台决定直接写入的默认目录
            if page.platform in [ft.PagePlatform.ANDROID, ft.PagePlatform.IOS]:
                export_dir = default_search_dir
            else:
                export_dir = os.getcwd() # 电脑端直接保存在当前脚本/程序运行目录下
                
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, filename)
            
            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows_data)
                
            status_text.value = f"✅ 导出成功！文件已保存在:\n{file_path}"
            page.update()
        except Exception as ex:
            status_text.value = f"导出失败: {str(ex)}"
            page.update()

    start_btn = ft.ElevatedButton("📝 开始记录成绩", width=280)
    
    action_row = ft.Row([
        ft.ElevatedButton("📊 查看成绩", width=135, on_click=view_scores),
        ft.ElevatedButton("📤 导出 CSV", width=135, on_click=export_excel)
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
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

if __name__ == "__main__":
    ft.app(target=main)