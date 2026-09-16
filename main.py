import csv
import os
import sqlite3
import flet as ft


APP_NAME = "小学生体测成绩管理系统"
DB_FILENAME = "pe_database.db"


def main(page: ft.Page):
    page.title = APP_NAME
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO

    # 手机端不设置固定窗口尺寸，让 Android/HyperOS 根据屏幕自动布局。
    try:
        page.window.resizable = True
    except Exception:
        pass

    # SQLite 永久放在 App 私有安全目录；CSV 由 Android 系统文件选择器负责访问。
    try:
        app_dir = page.get_app_storage_dir()
    except Exception:
        app_dir = os.path.join(os.getcwd(), "app_data")
    os.makedirs(app_dir, exist_ok=True)
    db_file = os.path.join(app_dir, DB_FILENAME)

    def db_connect():
        conn = sqlite3.connect(db_file, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db():
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grade TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    UNIQUE(grade, class_name)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL,
                    student_no TEXT NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
                    UNIQUE(class_id, student_no)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    unit TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    score REAL,
                    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE,
                    UNIQUE(student_id, item_id)
                )
            """)

            cur.execute("SELECT COUNT(*) FROM items")
            if cur.fetchone()[0] == 0:
                cur.executemany(
                    "INSERT INTO items (item_name, unit) VALUES (?, ?)",
                    [
                        ("身高", "cm"),
                        ("体重", "kg"),
                        ("肺活量", "ml"),
                        ("50米跑", "秒"),
                        ("坐位体前屈", "cm"),
                        ("1分钟跳绳", "个"),
                        ("1分钟仰卧起坐", "个"),
                        ("立定跳远", "cm"),
                    ],
                )

    init_db()

    # ---------- 通用 UI ----------
    title = ft.Text(APP_NAME, size=22, weight=ft.FontWeight.BOLD)
    status_text = ft.Text("", size=12)

    grade_input = ft.TextField(
        label="年级（例如：三年级）",
        width=300,
    )
    class_input = ft.TextField(
        label="班级（例如：一班）",
        width=300,
    )
    path_input = ft.TextField(
        label="已选择 CSV 文件",
        read_only=True,
        expand=True,
    )

    class_dropdown = ft.Dropdown(
        label="请先导入班级学生名单",
        width=300,
        options=[],
    )

    item_dropdown = ft.Dropdown(
        label="选择体测项目",
        width=300,
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
        ],
    )

    def set_status(message, error=False):
        status_text.value = message
        status_text.color = ft.Colors.RED if error else ft.Colors.GREEN
        page.update()

    def load_classes_to_dropdown():
        with db_connect() as conn:
            rows = conn.execute(
                "SELECT id, grade, class_name FROM classes "
                "ORDER BY id"
            ).fetchall()

        class_dropdown.options = [
            ft.dropdown.Option(
                key=str(row[0]),
                text=f"{row[1]}{row[2]}",
            )
            for row in rows
        ]
        class_dropdown.label = (
            "选择已导入的班级" if rows else "暂无班级，请先导入"
        )
        page.update()

    load_classes_to_dropdown()

    # ---------- Android 文件选择器 ----------
    import_picker = ft.FilePicker()
    export_picker = ft.FilePicker()
    page.overlay.extend([import_picker, export_picker])

    pending_export = {"bytes": None, "filename": None}

    def on_import_result(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        selected = e.files[0]
        path_input.value = selected.path or selected.name
        path_input.data = selected.path
        set_status(f"已选择文件：{selected.name}")

    import_picker.on_result = on_import_result

    def choose_csv(e):
        import_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["csv"],
            dialog_title="选择学生名单 CSV 文件",
        )

    choose_file_btn = ft.OutlinedButton(
        "选择 CSV",
        width=95,
        on_click=choose_csv,
    )

    # ---------- 导入 CSV ----------
    def confirm_import(e):
        g_text = (grade_input.value or "").strip()
        c_text = (class_input.value or "").strip()
        file_path = getattr(path_input, "data", None) or ""

        if not g_text or not c_text:
            set_status("错误：年级和班级名称不能为空！", True)
            return

        if not file_path or not os.path.isfile(file_path):
            set_status("错误：请先点击“选择 CSV”选择学生名单。", True)
            return

        imported_count = 0
        updated_count = 0

        try:
            with db_connect() as conn:
                cur = conn.cursor()

                cur.execute(
                    "SELECT id FROM classes WHERE grade=? AND class_name=?",
                    (g_text, c_text),
                )
                row = cur.fetchone()
                if row:
                    class_id = row[0]
                else:
                    cur.execute(
                        "INSERT INTO classes (grade, class_name) VALUES (?, ?)",
                        (g_text, c_text),
                    )
                    class_id = cur.lastrowid

                # utf-8-sig 兼容 Excel 导出的中文 CSV。
                with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames:
                        raise ValueError("CSV 文件没有表头。")
                    if "学号" not in reader.fieldnames or "姓名" not in reader.fieldnames:
                        raise ValueError("CSV 表格必须包含【学号】和【姓名】表头。")

                    for row_data in reader:
                        s_no = str(row_data.get("学号", "") or "").strip()
                        s_name = str(row_data.get("姓名", "") or "").strip()
                        if not s_no or not s_name:
                            continue

                        cur.execute(
                            "SELECT id, name FROM students "
                            "WHERE class_id=? AND student_no=?",
                            (class_id, s_no),
                        )
                        old = cur.fetchone()
                        if old:
                            if old[1] != s_name:
                                cur.execute(
                                    "UPDATE students SET name=? WHERE id=?",
                                    (s_name, old[0]),
                                )
                            updated_count += 1
                        else:
                            cur.execute(
                                "INSERT INTO students "
                                "(class_id, student_no, name) VALUES (?, ?, ?)",
                                (class_id, s_no, s_name),
                            )
                            imported_count += 1

            load_classes_to_dropdown()
            grade_input.value = ""
            class_input.value = ""
            path_input.value = ""
            path_input.data = None

            set_status(
                f"导入完成：新增 {imported_count} 人，已存在/更新 {updated_count} 人。"
            )
        except UnicodeDecodeError:
            set_status("导入失败：CSV 编码无法识别，请用 UTF-8/UTF-8-BOM 保存。", True)
        except Exception as ex:
            set_status(f"导入失败：{ex}", True)

    import_btn = ft.ElevatedButton(
        "📥 确认导入 CSV 名单",
        width=300,
        on_click=confirm_import,
    )

    # ---------- 成绩录入 ----------
    students_list_view = ft.ListView(
        expand=True,
        spacing=8,
        padding=5,
    )

    score_dlg = ft.AlertDialog(
        title=ft.Text("📝 班级成绩录入"),
        content=ft.Container(
            content=students_list_view,
            width=520,
            height=500,
        ),
        actions=[],
    )
    page.overlay.append(score_dlg)

    def close_score_dlg(e=None):
        score_dlg.open = False
        page.update()

    def open_score_popup(e=None):
        class_value = class_dropdown.value
        if not class_value:
            set_status("请先选择班级！", True)
            return

        item_value = item_dropdown.value
        if not item_value:
            set_status("请选择体测项目！", True)
            return

        class_id = int(class_value)
        item_id = int(item_value)

        students_list_view.controls.clear()

        with db_connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.student_no, s.name, sc.score
                FROM students s
                LEFT JOIN scores sc
                    ON s.id = sc.student_id AND sc.item_id = ?
                WHERE s.class_id = ?
                ORDER BY
                    CASE
                        WHEN s.student_no GLOB '[0-9]*'
                        THEN CAST(s.student_no AS INTEGER)
                        ELSE 999999999
                    END,
                    s.student_no
                """,
                (item_id, class_id),
            ).fetchall()

        if not rows:
            set_status("该班级暂无学生名单！", True)
            return

        for student_id, s_no, s_name, current_score in rows:
            score_input = ft.TextField(
                value="" if current_score is None else str(current_score),
                width=90,
                text_align=ft.TextAlign.CENTER,
                keyboard_type=ft.KeyboardType.NUMBER,
            )

            def make_save_handler(s_id, inp, selected_item_id):
                def save_score(e):
                    raw = (inp.value or "").strip()

                    try:
                        value = None if raw == "" else float(raw)
                    except ValueError:
                        set_status(
                            f"{s_name}：成绩必须是数字。",
                            True,
                        )
                        return

                    try:
                        with db_connect() as conn:
                            if value is None:
                                conn.execute(
                                    "DELETE FROM scores "
                                    "WHERE student_id=? AND item_id=?",
                                    (s_id, selected_item_id),
                                )
                            else:
                                conn.execute(
                                    """
                                    INSERT INTO scores(student_id, item_id, score)
                                    VALUES (?, ?, ?)
                                    ON CONFLICT(student_id, item_id)
                                    DO UPDATE SET score=excluded.score
                                    """,
                                    (s_id, selected_item_id, value),
                                )
                        set_status("成绩保存成功。")
                    except Exception as ex:
                        set_status(f"保存失败：{ex}", True)

                return save_score

            save_btn = ft.ElevatedButton(
                "保存",
                width=75,
                on_click=make_save_handler(
                    student_id, score_input, item_id
                ),
            )

            row_item = ft.Row(
                [
                    ft.Text(
                        f"{s_no}号 {s_name}",
                        expand=True,
                        size=14,
                    ),
                    score_input,
                    save_btn,
                ],
                spacing=8,
            )
            students_list_view.controls.append(row_item)

        score_dlg.actions = [
            ft.ElevatedButton("完成/关闭", on_click=close_score_dlg)
        ]
        score_dlg.open = True
        page.update()

    project_dlg = ft.AlertDialog(
        title=ft.Text("请选择测试项目"),
        content=item_dropdown,
        actions=[],
    )
    page.overlay.append(project_dlg)

    def close_project_dlg(e=None):
        project_dlg.open = False
        page.update()

    project_dlg.actions = [
        ft.TextButton("取消", on_click=close_project_dlg),
        ft.ElevatedButton(
            "确定，开始记录",
            on_click=lambda e: (
                close_project_dlg(),
                open_score_popup(e),
            ),
        ),
    ]

    def start_recording(e):
        if not class_dropdown.value:
            set_status("请先选择要记录成绩的班级！", True)
            return
        project_dlg.open = True
        page.update()

    start_btn = ft.ElevatedButton(
        "📝 开始记录成绩",
        width=300,
        on_click=start_recording,
    )

    # ---------- 成绩数据 ----------
    def get_class_score_data(class_id):
        with db_connect() as conn:
            students = conn.execute(
                """
                SELECT id, student_no, name
                FROM students
                WHERE class_id=?
                ORDER BY
                    CASE
                        WHEN student_no GLOB '[0-9]*'
                        THEN CAST(student_no AS INTEGER)
                        ELSE 999999999
                    END,
                    student_no
                """,
                (class_id,),
            ).fetchall()

            if not students:
                return None, None

            items = conn.execute(
                "SELECT id, item_name, unit FROM items ORDER BY id"
            ).fetchall()

            scores = conn.execute(
                "SELECT student_id, item_id, score FROM scores"
            ).fetchall()

        scores_map = {(x[0], x[1]): x[2] for x in scores}
        headers = ["学号", "姓名"] + [
            f"{item[1]} ({item[2]})" for item in items
        ]

        data = []
        for student_id, student_no, name in students:
            row = [student_no, name]
            for item_id, _, _ in items:
                value = scores_map.get((student_id, item_id), "")
                row.append("" if value is None else value)
            data.append(row)

        return headers, data

    view_table_container = ft.Container(
        expand=True,
        content=ft.Text(""),
    )

    view_dlg = ft.AlertDialog(
        title=ft.Text("📊 班级成绩总览"),
        content=ft.Container(
            content=view_table_container,
            width=700,
            height=500,
        ),
        actions=[],
    )
    page.overlay.append(view_dlg)

    def close_view_dlg(e=None):
        view_dlg.open = False
        page.update()

    def view_scores(e):
        if not class_dropdown.value:
            set_status("请先选择要查看的班级！", True)
            return

        headers, rows_data = get_class_score_data(
            int(class_dropdown.value)
        )

        if not headers or not rows_data:
            set_status("该班级暂无学生数据！", True)
            return

        columns = [
            ft.DataColumn(ft.Text(h, weight=ft.FontWeight.BOLD))
            for h in headers
        ]
        rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(value)))
                    for value in row
                ]
            )
            for row in rows_data
        ]

        data_table = ft.DataTable(
            columns=columns,
            rows=rows,
            column_spacing=18,
        )

        view_table_container.content = ft.Row(
            [data_table],
            scroll=ft.ScrollMode.ALWAYS,
        )
        view_dlg.actions = [
            ft.ElevatedButton("关闭", on_click=close_view_dlg)
        ]
        view_dlg.open = True
        page.update()

    # ---------- 导出 ----------
    def on_export_result(e: ft.FilePickerResultEvent):
        if not e.path:
            return

        try:
            target = e.path
            data = pending_export["bytes"]
            with open(target, "wb") as f:
                f.write(data)
            set_status(f"✅ 导出成功：{os.path.basename(target)}")
        except Exception as ex:
            set_status(f"导出失败：{ex}", True)

    export_picker.on_result = on_export_result

    def export_csv(e):
        if not class_dropdown.value:
            set_status("请先选择要导出的班级！", True)
            return

        headers, rows_data = get_class_score_data(
            int(class_dropdown.value)
        )
        if not headers or not rows_data:
            set_status("该班级暂无数据可导出！", True)
            return

        try:
            with db_connect() as conn:
                c_info = conn.execute(
                    "SELECT grade, class_name FROM classes WHERE id=?",
                    (int(class_dropdown.value),),
                ).fetchone()

            class_tag = (
                f"{c_info[0]}{c_info[1]}"
                if c_info
                else "class"
            )
            filename = f"体测成绩_{class_tag}.csv"

            import io
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(rows_data)

            pending_export["bytes"] = output.getvalue().encode("utf-8-sig")
            pending_export["filename"] = filename

            export_picker.save_file(
                file_name=filename,
                dialog_title="保存体测成绩 CSV",
            )
        except Exception as ex:
            set_status(f"导出失败：{ex}", True)

    view_btn = ft.ElevatedButton(
        "📊 查看成绩",
        expand=True,
        on_click=view_scores,
    )
    export_btn = ft.ElevatedButton(
        "📤 导出 CSV",
        expand=True,
        on_click=export_csv,
    )

    # ---------- 页面 ----------
    page.add(
        ft.Column(
            [
                title,
                ft.Divider(),
                grade_input,
                class_input,
                ft.Row(
                    [path_input, choose_file_btn],
                    spacing=6,
                ),
                import_btn,
                ft.Divider(height=20),
                class_dropdown,
                start_btn,
                ft.Row(
                    [view_btn, export_btn],
                    spacing=10,
                ),
                status_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
