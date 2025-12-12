import sys
import os
import sqlite3
import time
import subprocess
import threading
import configparser
import shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QWidget, 
    QListWidget, QListWidgetItem, QScrollArea, 
    QFrame, QFileIconProvider, QVBoxLayout,
    QMessageBox, QInputDialog, QMenu, QAction,
    QDialog, QLineEdit, QPushButton, QGridLayout, QFileDialog,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QFileInfo, QPoint, QTimer, QThread, QUrl, QRectF
from PyQt5.QtGui import QPixmap, QFont, QDesktopServices, QPainter, QPainterPath, QBrush, QColor

# ==========================================
#           全局配置与缓存
# ==========================================
USER_CONFIG = {}
ICON_CACHE = {}

# ==========================================
#      数据对象类 (内存中操作的对象)
# ==========================================
class ToolData:
    def __init__(self, name, desc, path, url):
        self.name = name
        self.desc = desc
        self.path = path
        self.url = url

# ==========================================
#      数据库管理类 (只负责读和整体写)
# ==========================================
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
            except Exception as e:
                print(f"Error creating directory {db_dir}: {e}")
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE,
                        sort_order INTEGER DEFAULT 0
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS tools (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category_id INTEGER,
                        name TEXT,
                        description TEXT,
                        path TEXT,
                        url TEXT,
                        sort_order INTEGER DEFAULT 0,
                        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
                     )''')
        conn.commit()
        conn.close()

    def load_all_data(self):
        data = {}
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name FROM categories ORDER BY sort_order ASC")
        categories = c.fetchall()
        for cat_id, cat_name in categories:
            tool_list = []
            c.execute("SELECT name, description, path, url FROM tools WHERE category_id=? ORDER BY sort_order ASC", (cat_id,))
            tools = c.fetchall()
            for row in tools:
                tool_obj = ToolData(row[0], row[1], row[2], row[3])
                tool_list.append(tool_obj)
            data[cat_name] = tool_list 
        conn.close()
        return data

    def create_backup(self):
        if not os.path.exists(self.db_path):
            return
        try:
            res_dir = os.path.dirname(self.db_path)
            root_dir = os.path.dirname(res_dir)
            save_dir = os.path.join(root_dir, "save")

            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"data_{timestamp}.db"
            backup_path = os.path.join(save_dir, backup_name)

            shutil.copy2(self.db_path, backup_path)
            print(f"Backup created: {backup_path}")

            all_backups = []
            for f in os.listdir(save_dir):
                if f.startswith("data_") and f.endswith(".db"):
                    full_p = os.path.join(save_dir, f)
                    all_backups.append(full_p)
            
            all_backups.sort(key=os.path.getmtime)
            while len(all_backups) > 5:
                oldest_file = all_backups.pop(0)
                try:
                    os.remove(oldest_file)
                    print(f"Removed old backup: {oldest_file}")
                except Exception as e:
                    print(f"Failed to remove old backup: {e}")
        except Exception as e:
            print(f"Backup Process Error: {e}")

    def save_snapshot(self, data_dict):
        self.create_backup()
        conn = self.get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute("DELETE FROM tools")
            conn.execute("DELETE FROM categories")
            
            cat_sort_index = 0
            for cat_name, tools_list in data_dict.items():
                cursor = conn.execute("INSERT INTO categories (name, sort_order) VALUES (?, ?)", (cat_name, cat_sort_index))
                cat_id = cursor.lastrowid
                cat_sort_index += 1
                
                tool_sort_index = 0
                for tool in tools_list:
                    conn.execute("""
                        INSERT INTO tools (category_id, name, description, path, url, sort_order) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (cat_id, tool.name, tool.desc, tool.path, tool.url, tool_sort_index))
                    tool_sort_index += 1
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Save Error: {e}")
            return False
        finally:
            conn.close()

# ==========================================
#      配置加载
# ==========================================
def load_config(current_dir, config_file=".res/config.ini"):
    global USER_CONFIG
    parser = configparser.ConfigParser()
    full_config_path = os.path.join(current_dir, config_file)
    try:
        if not os.path.exists(full_config_path):
            print(f"Config not found: {full_config_path}")
            return False 
        
        parser.read(full_config_path, encoding='utf-8')

        USER_CONFIG.update({
            "WINDOW_WIDTH": parser.getint('WINDOW_SETTINGS', 'WINDOW_WIDTH'),
            "WINDOW_HEIGHT": parser.getint('WINDOW_SETTINGS', 'WINDOW_HEIGHT'),
            "BG_IMAGE": parser.get('WINDOW_SETTINGS', 'BG_IMAGE'),
            "SIDEBAR_RATIO": parser.getfloat('WINDOW_SETTINGS', 'SIDEBAR_RATIO'),
            "FONT_FAMILY": parser.get('WINDOW_SETTINGS', 'FONT_FAMILY'),
            "TEXT_COLOR": parser.get('WINDOW_SETTINGS', 'TEXT_COLOR'),
        })

        USER_CONFIG["FONT_SIZES"] = {
            "APP_TITLE": parser.getint('FONT_SIZES', 'APP_TITLE'),
            "VERSION": parser.getint('FONT_SIZES', 'VERSION'),
            "CATEGORY": parser.getint('FONT_SIZES', 'CATEGORY'),
            "DESCRIPTION": parser.getint('FONT_SIZES', 'DESCRIPTION'),
            "TOOL_NAME": parser.getint('FONT_SIZES', 'TOOL_NAME'),
        }

        USER_CONFIG["TITLE_Geometry"] = (
            parser.getint('LAYOUT_GEOMETRY', 'TITLE_X'), 
            parser.getint('LAYOUT_GEOMETRY', 'TITLE_Y'), 
            parser.getint('LAYOUT_GEOMETRY', 'TITLE_W'), 
            parser.getint('LAYOUT_GEOMETRY', 'TITLE_H')
        )
        USER_CONFIG["TITLE_TEXT"] = parser.get('LAYOUT_GEOMETRY', 'TITLE_TEXT')

        USER_CONFIG["VERSION_Geometry"] = (
            parser.getint('LAYOUT_GEOMETRY', 'VERSION_X'), 
            parser.getint('LAYOUT_GEOMETRY', 'VERSION_Y'), 
            parser.getint('LAYOUT_GEOMETRY', 'VERSION_W'), 
            parser.getint('LAYOUT_GEOMETRY', 'VERSION_H')
        )
        USER_CONFIG["VERSION_TEXT"] = parser.get('LAYOUT_GEOMETRY', 'VERSION_TEXT')

        USER_CONFIG["DESC_Geometry"] = (
            parser.getint('LAYOUT_GEOMETRY', 'DESC_X'), 
            parser.getint('LAYOUT_GEOMETRY', 'DESC_Y'), 
            parser.getint('LAYOUT_GEOMETRY', 'DESC_W'), 
            parser.getint('LAYOUT_GEOMETRY', 'DESC_H')
        )
        USER_CONFIG["DESC_ALIGN"] = Qt.AlignCenter 

        USER_CONFIG["BTN_CLOSE"] = {
            "GEOMETRY": (
                parser.getint('BUTTON_CONTROLS', 'CLOSE_X'), 
                parser.getint('BUTTON_CONTROLS', 'CLOSE_Y'), 
                parser.getint('BUTTON_CONTROLS', 'CLOSE_W'), 
                parser.getint('BUTTON_CONTROLS', 'CLOSE_H')
            ), 
            "TEXT": "", 
            "FONT_SIZE": parser.getint('BUTTON_CONTROLS', 'CLOSE_FONT_SIZE')
        }
        
        USER_CONFIG["BTN_MIN"] = {
            "GEOMETRY": (
                parser.getint('BUTTON_CONTROLS', 'MIN_X'), 
                parser.getint('BUTTON_CONTROLS', 'MIN_Y'), 
                parser.getint('BUTTON_CONTROLS', 'MIN_W'), 
                parser.getint('BUTTON_CONTROLS', 'MIN_H')
            ), 
            "TEXT": "", 
            "FONT_SIZE": parser.getint('BUTTON_CONTROLS', 'MIN_FONT_SIZE')
        }

        USER_CONFIG["ITEM_CONFIG"] = {
            "WIDTH": parser.getint('ITEM_CONFIG', 'WIDTH'),
            "HEIGHT": parser.getint('ITEM_CONFIG', 'HEIGHT'),
            "ICON_SIZE": parser.getint('ITEM_CONFIG', 'ICON_SIZE'),
            "SPACING_X": parser.getint('ITEM_CONFIG', 'SPACING_X'),
            "SPACING_Y": parser.getint('ITEM_CONFIG', 'SPACING_Y'),
        }
        return True
    except Exception as e:
        print(f"Config Error: {e}")
        return False

# ==========================================
#      后台线程：预加载图标
# ==========================================
class IconPreloader(QThread):
    def __init__(self, data_dict, current_dir):
        super().__init__()
        self.data_dict = data_dict
        self.current_dir = current_dir
        self.icon_size = USER_CONFIG["ITEM_CONFIG"]["ICON_SIZE"]

    def run(self):
        for category, tool_objects in self.data_dict.items():
            for tool in tool_objects:
                name = tool.name
                path = tool.path
                cache_key = path
                
                if cache_key in ICON_CACHE: continue
                pixmap = self._load_single_icon(name, path)
                if pixmap: ICON_CACHE[cache_key] = pixmap

    def _load_single_icon(self, name, path):
        # 1. 优先检查 icons 文件夹
        icon_path_png = os.path.join(self.current_dir, "icons", f"{name}.png")
        if os.path.exists(icon_path_png):
            return QPixmap(icon_path_png).scaled(self.icon_size, self.icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # 2. Exe提取
        full_path = os.path.join(self.current_dir, path.lstrip(os.sep))
        if os.path.exists(full_path):
            file_info = QFileInfo(full_path)
            icon = QFileIconProvider().icon(file_info)
            pixmap_raw = icon.pixmap(self.icon_size, self.icon_size)
            if not pixmap_raw.isNull():
                 return pixmap_raw.scaled(self.icon_size, self.icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # 3. 默认图标
        default_path = os.path.join(self.current_dir, ".res", "default.png")
        if not os.path.exists(default_path):
            default_path = os.path.join(self.current_dir, "default.png")
            
        if os.path.exists(default_path):
             return QPixmap(default_path).scaled(self.icon_size, self.icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None

# ==========================================
#      UI组件：占位符
# ==========================================
class GridPlaceholder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = USER_CONFIG["ITEM_CONFIG"]
        self.setFixedSize(cfg["WIDTH"], cfg["HEIGHT"])
        self.setStyleSheet("background-color: rgba(255, 255, 255, 10); border: 2px dashed rgba(255, 255, 255, 50); border-radius: 5px;")
        self.show()

# ==========================================
#      UI组件：流式布局容器
# ==========================================
class ResponsiveContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tools = [] 
        self.parent_win = None
        self.placeholder = None 

    def set_window_instance(self, win):
        self.parent_win = win

    def add_tool(self, tool_btn):
        tool_btn.setParent(self)
        tool_btn.show()
        self.tools.append(tool_btn)
        self.update_layout() 

    def clear_tools(self):
        self.placeholder = None
        for btn in self.tools:
            btn.hide()
            btn.setParent(None)
            btn.deleteLater()
        self.tools = []

    def resizeEvent(self, event):
        self.update_layout()
        super().resizeEvent(event)

    def get_layout_params(self):
        container_width = self.width()
        cfg = USER_CONFIG["ITEM_CONFIG"]
        w, h = cfg["WIDTH"], cfg["HEIGHT"]
        sx, sy = cfg["SPACING_X"], cfg["SPACING_Y"]
        safe_width = container_width - 20 
        cols = max(1, int((safe_width + sx) // (w + sx)))
        actual_grid_width = cols * w + (cols - 1) * sx
        start_x = (container_width - actual_grid_width) // 2
        return w, h, sx, sy, cols, start_x

    def update_layout(self):
        if not self.tools: 
            self.setMinimumHeight(20)
            return
        w, h, sx, sy, cols, start_x = self.get_layout_params()
        for i, item in enumerate(self.tools):
            row = i // cols
            col = i % cols
            item.move(int(start_x + col * (w + sx)), int(10 + row * (h + sy)))
            item.show()
        total_rows = (len(self.tools) - 1) // cols + 1
        self.setMinimumHeight(20 + total_rows * (h + sy))

    def get_index_at_pos(self, pos):
        w, h, sx, sy, cols, start_x = self.get_layout_params()
        rel_x = pos.x() - start_x
        rel_y = pos.y() - 10
        col = round(rel_x / (w + sx))
        row = round(rel_y / (h + sy))
        if col < 0: col = 0
        if col >= cols: col = cols - 1
        if row < 0: row = 0
        return int(row * cols + col)

    def add_placeholder_at_index(self, index=-1):
        if self.placeholder and self.placeholder in self.tools: return 
        self.placeholder = GridPlaceholder(self)
        if index == -1 or index >= len(self.tools): self.tools.append(self.placeholder)
        else: self.tools.insert(index, self.placeholder)
        self.update_layout()

    def update_placeholder_position(self, global_mouse_pos):
        if not self.placeholder:
            self.add_placeholder_at_index()
            return
        local_pos = self.mapFromGlobal(global_mouse_pos)
        target_index = self.get_index_at_pos(local_pos)
        try: current_index = self.tools.index(self.placeholder)
        except ValueError: 
            self.add_placeholder_at_index()
            return
        if target_index >= len(self.tools): target_index = len(self.tools) - 1
        if current_index != target_index:
            self.tools.pop(current_index)
            self.tools.insert(target_index, self.placeholder)
            self.update_layout()

    def remove_placeholder(self):
        if self.placeholder and self.placeholder in self.tools:
            self.tools.remove(self.placeholder)
            self.placeholder.hide()
            self.placeholder.deleteLater()
            self.placeholder = None
            self.update_layout()
            
    def get_placeholder_index(self):
        if self.placeholder and self.placeholder in self.tools:
            return self.tools.index(self.placeholder)
        return len(self.tools)

# ==========================================
#      UI组件：单个软件图标
# ==========================================
class ToolItem(QWidget):
    def __init__(self, tool_data, parent_win):
        super().__init__()
        self.tool_data = tool_data
        self.name = tool_data.name
        self.desc = tool_data.desc
        self.path = tool_data.path
        self.url = tool_data.url
        
        self.parent_win = parent_win
        self.last_left_click = 0
        self.click_interval = 300 
        self.drag_start_pos = None
        self.is_dragging = False
        self.original_category = None 
        
        cfg = USER_CONFIG["ITEM_CONFIG"]
        self.setFixedSize(cfg["WIDTH"], cfg["HEIGHT"])
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.style_normal = "QWidget#ToolItem { background: transparent; border: none; border-radius: 5px; }"
        self.style_hover = "QWidget#ToolItem { background: rgba(255, 255, 255, 40); border: 1px solid rgba(255, 255, 255, 50); border-radius: 5px; }"
        self.style_dragging = "QWidget#ToolItem { background: rgba(0, 170, 255, 80); border: 2px solid #00aaff; border-radius: 5px; }"

        self.setObjectName("ToolItem")
        self.setStyleSheet(self.style_normal)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(2)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(cfg["ICON_SIZE"], cfg["ICON_SIZE"])
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        
        self.text_label = QLabel(self.name, self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        f_size = USER_CONFIG["FONT_SIZES"]["TOOL_NAME"]
        self.text_label.setStyleSheet(f"color: {USER_CONFIG['TEXT_COLOR']}; font-size: {f_size}px; font-family: '{USER_CONFIG['FONT_FAMILY']}'; background: transparent; border: none;")

        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)
        layout.addWidget(self.text_label, 0, Qt.AlignHCenter)
        self.load_icon()

    def load_icon(self):
        cache_key = self.path
        if cache_key in ICON_CACHE:
            self.icon_label.setPixmap(ICON_CACHE[cache_key])
            return
        
        current_dir = self.parent_win.current_dir
        icon_size = USER_CONFIG["ITEM_CONFIG"]["ICON_SIZE"]
        pixmap = None
        
        icon_path_png = os.path.join(current_dir, "icons", f"{self.name}.png")
        if os.path.exists(icon_path_png):
            pixmap = QPixmap(icon_path_png)
        
        if not pixmap or pixmap.isNull():
            full_path = os.path.join(current_dir, self.path.lstrip(os.sep))
            if os.path.exists(full_path):
                file_info = QFileInfo(full_path)
                icon = QFileIconProvider().icon(file_info)
                pixmap = icon.pixmap(icon_size, icon_size)

        if not pixmap or pixmap.isNull():
            default_path = os.path.join(current_dir, ".res", "default.png")
            if not os.path.exists(default_path):
                default_path = os.path.join(current_dir, "default.png")
            
            if os.path.exists(default_path):
                pixmap = QPixmap(default_path)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(scaled)
            ICON_CACHE[cache_key] = scaled
        else:
            self.icon_label.setText("?")

    def enterEvent(self, event):
        if not self.is_dragging:
            self.setStyleSheet(self.style_hover)
            text = f"{self.name} : {self.desc}" if self.desc else self.name
            self.parent_win.update_description(text)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_dragging:
            self.setStyleSheet(self.style_normal)
            self.parent_win.update_description("") 
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPos() 
            self.is_dragging = False 
            
            current_cat_item = self.parent_win.category_list.currentItem()
            self.original_category = current_cat_item.text() if current_cat_item else None
            
            self.last_left_click = time.time() * 1000
            
        elif event.button() == Qt.RightButton:
            self.parent_win.show_tool_context_menu(self.tool_data, event.globalPos())

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton): return
        if not self.drag_start_pos: return

        dist = (event.globalPos() - self.drag_start_pos).manhattanLength()
        
        if not self.is_dragging and dist > 10:
            self.is_dragging = True
            self.setStyleSheet(self.style_dragging)
            self.parent_win.dragging_tool_data = self.tool_data 
            
            container = self.parent_win.responsive_container
            current_index = -1
            if self in container.tools:
                current_index = container.tools.index(self)
                container.tools.remove(self) 
            
            global_pos = self.mapToGlobal(QPoint(0, 0))
            self.setParent(self.parent_win) 
            self.move(self.parent_win.mapFromGlobal(global_pos))
            self.show()
            container.add_placeholder_at_index(current_index)
                
        if self.is_dragging:
            delta = event.globalPos() - self.drag_start_pos
            self.drag_start_pos = event.globalPos()
            self.move(self.pos() + delta)
            
            sidebar_list = self.parent_win.category_list
            container = self.parent_win.responsive_container
            
            local_sb_pos = sidebar_list.mapFromGlobal(event.globalPos())
            hovered_cat = sidebar_list.itemAt(local_sb_pos)
            if hovered_cat and hovered_cat != sidebar_list.currentItem():
                sidebar_list.setCurrentItem(hovered_cat) 
                container.add_placeholder_at_index()

            container.update_placeholder_position(event.globalPos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.is_dragging:
                self.is_dragging = False
                self.setStyleSheet(self.style_hover) 
                self.parent_win.dragging_tool_data = None
                
                container = self.parent_win.responsive_container
                final_cat_item = self.parent_win.category_list.currentItem()
                
                if final_cat_item:
                    target_category = final_cat_item.text()
                    target_index = container.get_placeholder_index()
                    container.remove_placeholder()
                    
                    if self.original_category and self.original_category in self.parent_win.data:
                         old_list = self.parent_win.data[self.original_category]
                         if self.tool_data in old_list:
                             old_list.remove(self.tool_data)
                    
                    if target_category not in self.parent_win.data:
                        self.parent_win.data[target_category] = []
                    
                    new_list = self.parent_win.data[target_category]
                    if target_index >= len(new_list):
                        new_list.append(self.tool_data)
                    else:
                        new_list.insert(target_index, self.tool_data)
                    
                    self.parent_win.is_dirty = True
                    self.parent_win.refresh_ui_from_memory()
                    
                self.deleteLater()
            else:
                current_time = time.time() * 1000
                if current_time - self.last_left_click < self.click_interval:
                    self.parent_win.launch_app(self.path)
                
        self.drag_start_pos = None

# ==========================================
#      弹窗：添加/编辑软件
# ==========================================
class AddEditSoftwareDialog(QDialog):
    def __init__(self, parent, category, tool_data=None):
        super().__init__(parent)
        self.setWindowTitle("添加软件" if not tool_data else "编辑软件")
        self.category = category
        self.tool_data = tool_data
        self.parent_win = parent
        self.result_data = None
        
        self.setMinimumWidth(450)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #333; color: white;") 

        self.setup_ui()
        if tool_data:
            self.load_data()

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.addWidget(QLabel("工具名:"), 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet("background-color: #555; color: white;")
        layout.addWidget(self.name_input, 0, 1, 1, 2)

        layout.addWidget(QLabel("说明:"), 1, 0)
        self.desc_input = QLineEdit()
        self.desc_input.setStyleSheet("background-color: #555; color: white;")
        layout.addWidget(self.desc_input, 1, 1, 1, 2)

        layout.addWidget(QLabel("路径:"), 2, 0)
        self.path_input = QLineEdit()
        self.path_input.setStyleSheet("background-color: #555; color: white;")
        layout.addWidget(self.path_input, 2, 1)

        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet("background-color: #00aaff; color: white; border-radius: 5px;")
        browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(browse_btn, 2, 2)
        
        layout.addWidget(QLabel("官网:"), 3, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://... (选填)")
        self.url_input.setStyleSheet("background-color: #555; color: white;")
        layout.addWidget(self.url_input, 3, 1, 1, 2)
        
        save_btn = QPushButton("💾 确定(暂存)")
        save_btn.setStyleSheet("background-color: #00aaff; color: white; border-radius: 5px; height: 30px;")
        save_btn.clicked.connect(self.save_data)
        layout.addWidget(save_btn, 4, 0, 1, 3)

    def load_data(self):
        self.name_input.setText(self.tool_data.name)
        self.desc_input.setText(self.tool_data.desc)
        self.path_input.setText(self.tool_data.path)
        self.url_input.setText(self.tool_data.url)

    def browse_file(self):
        initial_dir = self.parent_win.current_dir
        file_path, _ = QFileDialog.getOpenFileName(self, "选择软件文件", initial_dir, "所有文件 (*.*)")
        if file_path:
            relative_path = os.path.relpath(file_path, self.parent_win.current_dir)
            self.path_input.setText(relative_path)

    def save_data(self):
        name = self.name_input.text().strip()
        desc = self.desc_input.text().strip()
        path = self.path_input.text().strip()
        url  = self.url_input.text().strip()
        
        if not name or not path:
            QMessageBox.warning(self, "警告", "工具名和路径不能为空！")
            return
        
        self.result_data = ToolData(name, desc, path, url)
        self.accept()

# ==========================================
#           主窗口逻辑
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.drag_pos = None
        
        # 数据库路径 .res/data.db
        db_path = os.path.join(self.current_dir, ".res", "data.db")
        self.db = DatabaseManager(db_path)
        
        self.data = {} 
        self.dragging_tool_data = None 
        self.is_dirty = False 
        
        self.W = USER_CONFIG.get("WINDOW_WIDTH", 1280)
        self.H = USER_CONFIG.get("WINDOW_HEIGHT", 760)
        self.SIDEBAR_W = int(self.W * USER_CONFIG.get("SIDEBAR_RATIO", 0.2))
        self.CONTENT_W = self.W - self.SIDEBAR_W
        self.border_radius = 12

        self.setup_window()
        self.setup_ui()
        
        QTimer.singleShot(10, self.initial_load)

    def setup_window(self):
        self.setFixedSize(self.W, self.H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(USER_CONFIG.get("TITLE_TEXT", "LLSKY9工具箱"))
        
        # 【新增】启用主窗口的拖放功能
        self.setAcceptDrops(True)

    def setup_ui(self):
        # 背景
        bg_path = os.path.join(self.current_dir, USER_CONFIG.get("BG_IMAGE", ""))
        self.bg_pixmap = None
        if os.path.exists(bg_path):
            self.bg_pixmap = QPixmap(bg_path).scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        self.create_sidebar()
        self.create_content_area()
        self.create_top_elements()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) 
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.border_radius, self.border_radius)
        painter.setClipPath(path)
        if self.bg_pixmap: painter.drawPixmap(self.rect(), self.bg_pixmap)
        else: painter.fillPath(path, QBrush(QColor("#2b2b2b")))

    def create_sidebar(self):
        container = QWidget(self)
        container.setGeometry(0, 0, self.SIDEBAR_W, self.H)
        container.setStyleSheet("background: transparent;") 

        title = QLabel(USER_CONFIG["TITLE_TEXT"], container)
        title.setGeometry(*USER_CONFIG["TITLE_Geometry"]) 
        title.setAlignment(Qt.AlignCenter)
        f_size = USER_CONFIG["FONT_SIZES"]["APP_TITLE"]
        title.setStyleSheet(f"color: white; font-family: '{USER_CONFIG['FONT_FAMILY']}'; font-size: {f_size}px; font-weight: bold;")

        self.create_management_buttons(container)
        
        self.category_list = QListWidget(container)
        self.category_list.setGeometry(0, 130, self.SIDEBAR_W, self.H - 170) 
        self.category_list.setFocusPolicy(Qt.NoFocus)
        self.category_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.category_list.setDragEnabled(True)
        self.category_list.setAcceptDrops(True)
        self.category_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.category_list.setDefaultDropAction(Qt.MoveAction)
        self.category_list.model().rowsMoved.connect(self.on_category_reordered)

        cat_f_size = USER_CONFIG["FONT_SIZES"]["CATEGORY"]
        self.category_list.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; outline: 0; }}
            QListWidget::item {{
                height: 45px;
                color: rgba(255,255,255,0.7);
                font-family: '{USER_CONFIG['FONT_FAMILY']}';
                font-size: {cat_f_size}px;
                padding-left: 0px; 
                margin-bottom: 2px;
                border: none;
            }}
            QListWidget::item:hover {{ color: #ffffff; padding-left: 20px; background: rgba(255,255,255,0.1); }}
            QListWidget::item:selected {{ color: #00aaff; font-weight: bold; background: rgba(255, 255, 255, 30); border-left: 4px solid #00aaff; }}
        """)
        self.category_list.currentItemChanged.connect(self.on_category_changed)
        self.category_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.category_list.customContextMenuRequested.connect(self.on_category_context_menu)

        ver = QLabel(USER_CONFIG["VERSION_TEXT"], container)
        ver.setGeometry(*USER_CONFIG["VERSION_Geometry"])
        ver.setAlignment(Qt.AlignCenter)
        v_f_size = USER_CONFIG["FONT_SIZES"]["VERSION"]
        ver.setStyleSheet(f"color: rgba(255,255,255,0.3); font-size: {v_f_size}px;")

    def create_management_buttons(self, parent):
        y_start = 75; h = 25
        btn_add_cat = QLabel("➕ 添加分类", parent)
        btn_add_cat.setGeometry(5, y_start, self.SIDEBAR_W // 2 - 7, h)
        btn_add_cat.setAlignment(Qt.AlignCenter)
        btn_add_cat.setStyleSheet("QLabel { background-color: #00aaff; color: white; border-radius: 5px; font-size: 13px; } QLabel:hover { background-color: #0088cc; }")
        btn_add_cat.setCursor(Qt.PointingHandCursor)
        btn_add_cat.mousePressEvent = lambda e: self.add_category()
        
        btn_add_tool = QLabel("📁 添加软件", parent)
        btn_add_tool.setGeometry(self.SIDEBAR_W // 2 + 2, y_start, self.SIDEBAR_W // 2 - 7, h)
        btn_add_tool.setAlignment(Qt.AlignCenter)
        btn_add_tool.setStyleSheet("QLabel { background-color: #2ECC71; color: white; border-radius: 5px; font-size: 13px; } QLabel:hover { background-color: #27AE60; }")
        btn_add_tool.setCursor(Qt.PointingHandCursor)
        btn_add_tool.mousePressEvent = lambda e: self.add_software()

    def create_content_area(self):
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setGeometry(self.SIDEBAR_W, 60, self.CONTENT_W, self.H - 60)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; } QScrollBar:vertical { width: 6px; background: transparent; } QScrollBar::handle:vertical { background: rgba(255,255,255,0.2); border-radius: 3px; } QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; } QScrollBar::sub-page:vertical, QScrollBar::add-page:vertical { background: none; }")
        self.responsive_container = ResponsiveContainer()
        self.responsive_container.set_window_instance(self) 
        self.responsive_container.setStyleSheet("background: transparent;")
        self.scroll_area.setWidget(self.responsive_container)

    def create_top_elements(self):
        self.desc_label = QLabel("", self)
        self.desc_label.setGeometry(*USER_CONFIG["DESC_Geometry"])
        self.desc_label.setAlignment(USER_CONFIG["DESC_ALIGN"])
        d_f_size = USER_CONFIG["FONT_SIZES"]["DESCRIPTION"]
        self.desc_label.setStyleSheet(f"color: rgba(255,255,255,0.9); font-family: '{USER_CONFIG['FONT_FAMILY']}'; font-size: {d_f_size}px;")

        close_conf = USER_CONFIG["BTN_CLOSE"]
        btn_close = QLabel(close_conf["TEXT"], self)
        btn_close.setGeometry(*close_conf["GEOMETRY"])
        btn_close.setAlignment(Qt.AlignCenter)
        btn_close.setStyleSheet(f"QLabel {{ color: white; font-size: {close_conf['FONT_SIZE']}px; background: transparent; }} QLabel:hover {{ background-color: rgba(255, 0, 0, 0.3); }}")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.mousePressEvent = lambda e: self.close() 
        
        min_conf = USER_CONFIG["BTN_MIN"]
        btn_min = QLabel(min_conf["TEXT"], self)
        btn_min.setGeometry(*min_conf["GEOMETRY"])
        btn_min.setAlignment(Qt.AlignCenter)
        btn_min.setStyleSheet(f"QLabel {{ color: white; font-size: {min_conf['FONT_SIZE']}px; background: transparent; }} QLabel:hover {{ background-color: rgba(255, 255, 255, 0.1); }}")
        btn_min.setCursor(Qt.PointingHandCursor)
        btn_min.mousePressEvent = lambda e: self.showMinimized()

    def initial_load(self):
        """启动时读取数据库"""
        self.data = self.db.load_all_data()
        self.is_dirty = False
        self.refresh_ui_from_memory()
        self.preloader = IconPreloader(self.data, self.current_dir)
        self.preloader.start()

    def refresh_ui_from_memory(self):
        """只从内存 self.data 刷新 UI"""
        current_row = self.category_list.currentRow()
        self.category_list.clear()
        for category in self.data.keys():
            item = QListWidgetItem(category)
            item.setTextAlignment(Qt.AlignCenter) 
            self.category_list.addItem(item)
        if self.category_list.count() > 0:
            if current_row >= 0 and current_row < self.category_list.count():
                self.category_list.setCurrentRow(current_row)
            else:
                self.category_list.setCurrentRow(0)
        else:
            self.responsive_container.clear_tools()

    def on_category_changed(self, item):
        if not item: return
        self.responsive_container.clear_tools()
        cat_name = item.text()
        tools = self.data.get(cat_name, [])
        for tool_obj in tools:
            if self.dragging_tool_data == tool_obj: continue
            btn = ToolItem(tool_obj, self) 
            self.responsive_container.add_tool(btn)

    def on_category_reordered(self, parent, start, end, destination, row):
        new_data = {}
        for i in range(self.category_list.count()):
            cat_name = self.category_list.item(i).text()
            if cat_name in self.data:
                new_data[cat_name] = self.data[cat_name]
        self.data = new_data
        self.is_dirty = True 

    def on_category_context_menu(self, point):
        item = self.category_list.itemAt(point)
        if not item: return
        menu = QMenu(self)
        action_add = QAction("在此分类下添加软件", self)
        action_add.triggered.connect(lambda: self.add_software())
        menu.addAction(action_add)
        menu.addSeparator()
        action_rename = QAction("修改分类名称", self)
        action_rename.triggered.connect(lambda: self.rename_category(item))
        menu.addAction(action_rename)
        action_delete = QAction("删除分类", self)
        action_delete.triggered.connect(lambda: self.delete_category(item))
        menu.addAction(action_delete)
        menu.exec_(self.category_list.mapToGlobal(point))

    def show_tool_context_menu(self, tool_data, global_pos):
        menu = QMenu(self)
        action_folder = menu.addAction("📂 打开所在文件夹")
        action_folder.triggered.connect(lambda: self.open_folder(tool_data.path))
        action_web = menu.addAction("🌐 访问官方网站")
        if tool_data.url:
             action_web.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(tool_data.url)))
        else:
             action_web.setEnabled(False)
        menu.addSeparator()
        action_edit = QAction("✏️ 修改软件信息", self)
        action_edit.triggered.connect(lambda: self.edit_software(tool_data))
        menu.addAction(action_edit)
        action_delete = QAction("🗑️ 删除软件", self)
        action_delete.triggered.connect(lambda: self.delete_software(tool_data))
        menu.addAction(action_delete)
        menu.exec_(global_pos)

    def add_category(self):
        new_category, ok = QInputDialog.getText(self, '添加分类', '请输入新的分类名称:', text='新分类')
        if ok and new_category:
            if new_category not in self.data:
                self.data[new_category] = []
                self.is_dirty = True
                self.refresh_ui_from_memory()
                self.category_list.setCurrentRow(self.category_list.count() - 1)
            else:
                QMessageBox.warning(self, "警告", "分类名称已存在。")

    def rename_category(self, item):
        old_name = item.text()
        new_name, ok = QInputDialog.getText(self, '修改分类名称', '请输入新的分类名称:', text=old_name)
        if ok and new_name and new_name != old_name:
            if new_name in self.data:
                QMessageBox.warning(self, "警告", "新分类名称已存在。")
                return
            new_data = {}
            for k, v in self.data.items():
                if k == old_name: new_data[new_name] = v
                else: new_data[k] = v
            self.data = new_data
            self.is_dirty = True
            self.refresh_ui_from_memory()

    def delete_category(self, item):
        name = item.text()
        reply = QMessageBox.question(self, '确认删除', f"删除分类 '{name}' 会移除内存中的该分类！\n只有退出时保存才会生效。", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if name in self.data:
                del self.data[name]
                self.is_dirty = True
                self.refresh_ui_from_memory()

    def add_software(self):
        current_item = self.category_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先在左侧选择一个分类！")
            return
        category = current_item.text()
        dialog = AddEditSoftwareDialog(self, category)
        if dialog.exec_() == QDialog.Accepted and dialog.result_data:
            self.data[category].append(dialog.result_data)
            self.is_dirty = True
            self.refresh_ui_from_memory()

    def edit_software(self, tool_data):
        current_item = self.category_list.currentItem()
        if not current_item: return
        category = current_item.text()
        dialog = AddEditSoftwareDialog(self, category, tool_data)
        if dialog.exec_() == QDialog.Accepted and dialog.result_data:
            tools_list = self.data[category]
            if tool_data in tools_list:
                idx = tools_list.index(tool_data)
                tools_list[idx] = dialog.result_data
                self.is_dirty = True
                self.refresh_ui_from_memory()

    def delete_software(self, tool_data):
        current_item = self.category_list.currentItem()
        if not current_item: return
        category = current_item.text()
        reply = QMessageBox.question(self, '确认删除', f"确定要从列表中移除 '{tool_data.name}' 吗?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            tools_list = self.data.get(category, [])
            if tool_data in tools_list:
                tools_list.remove(tool_data)
                self.is_dirty = True
                self.refresh_ui_from_memory()

    def closeEvent(self, event):
        if self.is_dirty:
            reply = QMessageBox.question(
                self, '保存更改',
                "检测到布局或数据已修改。\n是否保存到数据库？\n(同时会创建旧版本的备份到 save 目录)", 
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, 
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                if self.db.save_snapshot(self.data):
                    # 保存成功，强制退出
                    os._exit(0)
                else:
                    QMessageBox.critical(self, "错误", "保存失败！无法写入数据库。")
                    event.ignore()
            
            elif reply == QMessageBox.No:
                # 放弃修改，强制退出
                os._exit(0)
            
            else:
                event.ignore()
        else:
            # 无修改，强制退出
            os._exit(0)

    def update_description(self, text):
        self.desc_label.setText(text)

    def launch_app(self, path):
        full_path = os.path.join(self.current_dir, path.lstrip(os.sep))
        self.desc_label.setText(f"正在启动: {os.path.basename(path)}...")
        if not os.path.exists(full_path):
            self.desc_label.setText("错误: 文件不存在！")
            return
        def _run():
            try:
                if os.name == 'nt': os.startfile(full_path)
                else: subprocess.Popen([full_path], cwd=os.path.dirname(full_path))
                time.sleep(1) 
                QTimer.singleShot(0, lambda: self.desc_label.setText(""))
            except Exception as e: 
                QTimer.singleShot(0, lambda: self.desc_label.setText(f"启动失败: {e}"))
        threading.Thread(target=_run, daemon=True).start()
    
    def open_folder(self, path):
        full_path = os.path.join(self.current_dir, path.lstrip(os.sep))
        target = full_path if os.path.isdir(full_path) else os.path.dirname(full_path)
        if os.name == 'nt': subprocess.Popen(f'explorer /select,"{os.path.abspath(full_path)}"', shell=True)
        elif sys.platform == 'darwin': subprocess.Popen(['open', os.path.abspath(target)])
        else: subprocess.Popen(['xdg-open', os.path.abspath(target)])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)
    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    # ==========================================
    #      【新增】 拖放功能实现 (含路径逻辑)
    # ==========================================
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        # 1. 获取当前选中的分类，若无则尝试选第一个
        current_item = self.category_list.currentItem()
        if not current_item:
            if self.category_list.count() > 0:
                self.category_list.setCurrentRow(0)
                current_item = self.category_list.currentItem()
            else:
                QMessageBox.warning(self, "提示", "请先创建并选择一个分类，再拖入文件！")
                return
        
        category = current_item.text()
        has_added = False

        # 2. 遍历拖入的文件
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if not file_path: continue
            
            # --- 核心路径处理逻辑 ---
            
            # 标准化路径分隔符
            abs_file_path = os.path.normpath(file_path)
            abs_app_dir = os.path.normpath(self.current_dir)

            # 获取盘符并转大写
            file_drive = os.path.splitdrive(abs_file_path)[0].upper()
            app_drive = os.path.splitdrive(abs_app_dir)[0].upper()

            final_path = abs_file_path # 默认绝对路径

            # 1. 如果盘符相同 -> 相对路径
            if file_drive == app_drive and file_drive != "":
                try:
                    # 自动处理为 "subdir/..." 或 "../dir/..."
                    final_path = os.path.relpath(abs_file_path, abs_app_dir)
                except ValueError:
                    final_path = abs_file_path
            else:
                # 2. 不同盘符 -> 绝对路径
                final_path = abs_file_path
            
            # --- 处理结束 ---

            # 获取文件名
            file_info = QFileInfo(file_path)
            name = file_info.baseName()
            
            # 预填充数据
            prefill_data = ToolData(name, "", final_path, "")
            dialog = AddEditSoftwareDialog(self, category, tool_data=prefill_data)
            dialog.setWindowTitle(f"添加拖入的文件: {name}") 
            
            if dialog.exec_() == QDialog.Accepted and dialog.result_data:
                self.data[category].append(dialog.result_data)
                has_added = True

        if has_added:
            self.is_dirty = True
            self.refresh_ui_from_memory()

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    if not load_config(current_dir): sys.exit(1)
    
    app = QApplication(sys.argv)
    font = QFont(USER_CONFIG["FONT_FAMILY"])
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
