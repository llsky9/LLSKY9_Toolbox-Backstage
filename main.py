import sys
import os
import json
import time
import subprocess
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QWidget, 
    QListWidget, QListWidgetItem, QScrollArea, 
    QFrame, QFileIconProvider, QVBoxLayout,
    QMessageBox, QInputDialog, QMenu, QAction,
    QDialog, QLineEdit, QPushButton, QGridLayout, QFileDialog
)
from PyQt5.QtCore import Qt, QFileInfo, QSize, QPoint, QRect, QTimer
from PyQt5.QtGui import QPixmap, QFont, QCursor
import configparser

# 全局配置变量和图标缓存
USER_CONFIG = {}
ICON_CACHE = {}

# ==========================================
#           配置加载函数
# ==========================================
def load_config(current_dir, config_file=".res/config.ini"):
    """从ini文件加载配置并转换为字典格式"""
    global USER_CONFIG
    
    parser = configparser.ConfigParser()
    full_config_path = os.path.join(current_dir, config_file)
    
    # 🚨 注意: 在这里不能使用 QMessageBox，因为它需要 QApplication 实例
    try:
        if not os.path.exists(full_config_path):
            print(f"Error: Configuration file '{full_config_path}' not found!")
            return False 

        parser.read(full_config_path, encoding='utf-8')

        # 1. 窗口基础设置 (WINDOW_SETTINGS)
        USER_CONFIG.update({
            "WINDOW_WIDTH": parser.getint('WINDOW_SETTINGS', 'WINDOW_WIDTH'),
            "WINDOW_HEIGHT": parser.getint('WINDOW_SETTINGS', 'WINDOW_HEIGHT'),
            "BG_IMAGE": parser.get('WINDOW_SETTINGS', 'BG_IMAGE'),
            "JSON_FILE": parser.get('WINDOW_SETTINGS', 'JSON_FILE'),
            "SIDEBAR_RATIO": parser.getfloat('WINDOW_SETTINGS', 'SIDEBAR_RATIO'),
            "FONT_FAMILY": parser.get('WINDOW_SETTINGS', 'FONT_FAMILY'),
            "TEXT_COLOR": parser.get('WINDOW_SETTINGS', 'TEXT_COLOR'),
        })

        # 2. 字体大小独立控制 (FONT_SIZES)
        USER_CONFIG["FONT_SIZES"] = {
            "APP_TITLE": parser.getint('FONT_SIZES', 'APP_TITLE'),
            "VERSION": parser.getint('FONT_SIZES', 'VERSION'),
            "CATEGORY": parser.getint('FONT_SIZES', 'CATEGORY'),
            "DESCRIPTION": parser.getint('FONT_SIZES', 'DESCRIPTION'),
            "TOOL_NAME": parser.getint('FONT_SIZES', 'TOOL_NAME'),
        }

        # 3. 界面布局位置控制 (LAYOUT_GEOMETRY)
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
        USER_CONFIG["DESC_ALIGN"] = Qt.AlignCenter # 保持默认对齐

        # 4. 窗口控制按钮 (BUTTON_CONTROLS)
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

        # 5. 软件图标排版 (ITEM_CONFIG)
        USER_CONFIG["ITEM_CONFIG"] = {
            "WIDTH": parser.getint('ITEM_CONFIG', 'WIDTH'),
            "HEIGHT": parser.getint('ITEM_CONFIG', 'HEIGHT'),
            "ICON_SIZE": parser.getint('ITEM_CONFIG', 'ICON_SIZE'),
            "SPACING_X": parser.getint('ITEM_CONFIG', 'SPACING_X'),
            "SPACING_Y": parser.getint('ITEM_CONFIG', 'SPACING_Y'),
        }
        
        return True

    except Exception as e:
        print(f"Configuration Loading Error: {e}")
        return False


# ==========================================
#      核心组件1：自动居中流式容器
# ==========================================
class ResponsiveContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tools = []

    def add_tool(self, tool_btn):
        tool_btn.setParent(self)
        tool_btn.show()
        self.tools.append(tool_btn)
        self.update_layout() 

    def clear_tools(self):
        for btn in self.tools:
            btn.deleteLater()
        self.tools = []

    def resizeEvent(self, event):
        self.update_layout()
        super().resizeEvent(event)

    def update_layout(self):
        if not self.tools: return

        container_width = self.width()
        cfg = USER_CONFIG["ITEM_CONFIG"]
        w = cfg["WIDTH"]
        h = cfg["HEIGHT"]
        sx = cfg["SPACING_X"]
        sy = cfg["SPACING_Y"]

        safe_width = container_width - 20 
        cols = (safe_width + sx) // (w + sx)
        cols = max(1, int(cols))

        actual_grid_width = cols * w + (cols - 1) * sx
        start_x = (container_width - actual_grid_width) // 2
        
        for i, btn in enumerate(self.tools):
            row = i // cols
            col = i % cols
            x = start_x + col * (w + sx)
            y = 10 + row * (h + sy) 
            btn.move(int(x), int(y))

        total_rows = (len(self.tools) - 1) // cols + 1
        total_height = 20 + total_rows * (h + sy)
        self.setMinimumHeight(total_height)

# ==========================================
#      核心组件2：软件图标 (解析与交互)
# ==========================================
class ToolItem(QWidget):
    def __init__(self, name, desc, path, tool_info_str, parent_win):
        super().__init__()
        self.name = name
        self.desc = desc 
        self.path = path
        self.tool_info_str = tool_info_str # 存储完整的软件信息字符串
        self.parent_win = parent_win
        
        self.last_left_click = 0
        self.last_right_click = 0
        self.click_interval = 300 
        
        cfg = USER_CONFIG["ITEM_CONFIG"]
        self.setFixedSize(cfg["WIDTH"], cfg["HEIGHT"])
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.style_normal = """
            QWidget#ToolItem {
                background: transparent;
                border: none;
                border-radius: 5px;
            }
        """
        self.style_hover = """
            QWidget#ToolItem {
                background: rgba(255, 255, 255, 40);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 5px;
            }
        """

        self.setObjectName("ToolItem")
        self.setStyleSheet(self.style_normal)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(2)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(cfg["ICON_SIZE"], cfg["ICON_SIZE"])
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        
        self.text_label = QLabel(name, self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        
        font_size = USER_CONFIG["FONT_SIZES"]["TOOL_NAME"]
        self.text_label.setStyleSheet(f"""
            color: {USER_CONFIG['TEXT_COLOR']}; 
            font-size: {font_size}px; 
            font-family: '{USER_CONFIG['FONT_FAMILY']}';
            background: transparent; 
            border: none;
        """)

        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)
        layout.addWidget(self.text_label, 0, Qt.AlignHCenter)
        
        # 异步加载图标
        self.load_icon()

    def load_icon(self):
        cache_key = self.path
        if cache_key in ICON_CACHE:
            self.icon_label.setPixmap(ICON_CACHE[cache_key])
            return

        current_dir = self.parent_win.current_dir
        icon_size = USER_CONFIG["ITEM_CONFIG"]["ICON_SIZE"]
        pixmap = None
        
        # 优先加载同名PNG图标
        icon_path_png = os.path.join(current_dir, "icons", f"{self.name}.png")
        if os.path.exists(icon_path_png):
            pixmap = QPixmap(icon_path_png)
        
        # 其次尝试加载程序文件图标
        if not pixmap or pixmap.isNull():
            full_path = os.path.join(current_dir, self.path.lstrip(os.sep))
            if os.path.exists(full_path):
                file_info = QFileInfo(full_path)
                icon = QFileIconProvider().icon(file_info)
                pixmap = icon.pixmap(icon_size, icon_size)

        # 最后使用默认图标
        if not pixmap or pixmap.isNull():
            default_path = os.path.join(current_dir, "default.png")
            if os.path.exists(default_path):
                pixmap = QPixmap(default_path)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(scaled)
            ICON_CACHE[cache_key] = scaled
        else:
            self.icon_label.setText("?")

    # --- 交互逻辑：悬停显示描述，双击启动 ---
    def enterEvent(self, event):
        self.setStyleSheet(self.style_hover)
        
        if self.desc: 
            text_to_show = f"{self.name} : {self.desc}"
        else:
            text_to_show = self.name
            
        self.parent_win.update_description(text_to_show)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.style_normal)
        self.parent_win.update_description("") 
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        current_time = time.time() * 1000
        if event.button() == Qt.LeftButton:
            # 单击: 选中软件并更新描述 (用于后续管理)
            if current_time - self.last_left_click > self.click_interval:
                self.parent_win.selected_software_info = self.tool_info_str 
                
            if current_time - self.last_left_click < self.click_interval:
                # 左键双击 -> 启动
                self.parent_win.launch_app(self.path)
            self.last_left_click = current_time
            
        elif event.button() == Qt.RightButton:
            # 单击右键: 选中软件并弹出管理菜单
            if current_time - self.last_right_click > self.click_interval:
                self.parent_win.selected_software_info = self.tool_info_str
                self.parent_win.show_tool_context_menu(self.tool_info_str, event.globalPos())
            
            if current_time - self.last_right_click < self.click_interval:
                # 右键双击 -> 打开文件夹
                self.parent_win.open_folder(self.path)
            self.last_right_click = current_time

# ==========================================
#      核心组件3：软件添加/编辑对话框
# ==========================================
class AddEditSoftwareDialog(QDialog):
    """用于添加和编辑软件信息的对话框"""
    def __init__(self, parent, category, tool_info_str=None):
        super().__init__(parent)
        self.setWindowTitle("添加软件" if not tool_info_str else "编辑软件")
        self.category = category
        self.tool_info_str = tool_info_str
        self.result = None # Stores the new tool info string or None
        self.parent_win = parent
        
        self.setMinimumWidth(400)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #333; color: white;") # 保持暗色风格

        self.setup_ui()
        if tool_info_str:
            self.load_data(tool_info_str)

    def setup_ui(self):
        layout = QGridLayout(self)

        # 1. 工具名
        layout.addWidget(QLabel("工具名:"), 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet("background-color: #555; color: white;")
        layout.addWidget(self.name_input, 0, 1, 1, 2)

        # 2. 说明
        layout.addWidget(QLabel("说明:"), 1, 0)
        self.desc_input = QLineEdit()
        self.desc_input.setStyleSheet("background-color: #555; color: white;")
        layout.addWidget(self.desc_input, 1, 1, 1, 2)

        # 3. 路径
        layout.addWidget(QLabel("路径:"), 2, 0)
        self.path_input = QLineEdit()
        self.path_input.setStyleSheet("background-color: #555; color: white;")
        layout.addWidget(self.path_input, 2, 1)

        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet("background-color: #00aaff; color: white; border-radius: 5px;")
        browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(browse_btn, 2, 2)
        
        # 4. 保存按钮
        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet("background-color: #00aaff; color: white; border-radius: 5px; height: 30px;")
        save_btn.clicked.connect(self.save_data)
        layout.addWidget(save_btn, 3, 0, 1, 3)

    def load_data(self, tool_info_str):
        name, desc, path = [p.strip() for p in tool_info_str.split("|")]
        self.name_input.setText(name)
        self.desc_input.setText(desc)
        self.path_input.setText(path)
        self.setWindowTitle(f"编辑软件: {name}")

    def browse_file(self):
        # 尝试使用配置的目录作为初始目录
        initial_dir = self.parent_win.current_dir
        file_path, _ = QFileDialog.getOpenFileName(self, "选择软件文件", initial_dir, "所有文件 (*.*)")
        if file_path:
            # 获取相对路径
            relative_path = os.path.relpath(file_path, self.parent_win.current_dir)
            self.path_input.setText(relative_path)

    def save_data(self):
        name = self.name_input.text().strip()
        desc = self.desc_input.text().strip()
        path = self.path_input.text().strip()
        
        if not name or not path:
            QMessageBox.warning(self, "警告", "工具名和路径不能为空！")
            return
            
        self.result = f"{name} | {desc} | {path}"
        self.accept()

# ==========================================
#           主窗口逻辑
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 获取程序运行目录
        self.current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.drag_pos = None
        self.data = {} # 存储数据
        self.data_path = "" # data.json 的路径
        self.is_dirty = False # 数据是否已修改的标志
        self.selected_software_info = None # 当前选中的软件信息 (完整字符串)
        
        # 从全局配置中获取尺寸
        # 🚨 确保 USER_CONFIG 已经在 if __name__ == "__main__": 中成功加载
        self.W = USER_CONFIG.get("WINDOW_WIDTH", 1280)
        self.H = USER_CONFIG.get("WINDOW_HEIGHT", 760)
        self.SIDEBAR_W = int(self.W * USER_CONFIG.get("SIDEBAR_RATIO", 0.2))
        self.CONTENT_W = self.W - self.SIDEBAR_W
        
        self.setup_window()
        self.setup_ui()

        # 延迟加载数据
        QTimer.singleShot(10, self.load_data)

    def setup_window(self):
        self.setFixedSize(self.W, self.H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(USER_CONFIG.get("TITLE_TEXT", "LLSKY9工具箱"))

    def setup_ui(self):
        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(0, 0, self.W, self.H)
        bg_path = os.path.join(self.current_dir, USER_CONFIG.get("BG_IMAGE", ""))
        if os.path.exists(bg_path):
            self.bg_label.setPixmap(QPixmap(bg_path).scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            ))
        else:
            self.bg_label.setStyleSheet("background-color: #2b2b2b;")

        self.create_sidebar()
        self.create_content_area()
        self.create_top_elements()

    def create_sidebar(self):
        container = QWidget(self)
        container.setGeometry(0, 0, self.SIDEBAR_W, self.H)
        container.setStyleSheet("background: transparent;") 

        # 标题
        title = QLabel(USER_CONFIG.get("TITLE_TEXT", "LLSKY9工具箱"), container)
        title.setGeometry(*USER_CONFIG.get("TITLE_Geometry", (0, 20, 256, 40))) 
        title.setAlignment(Qt.AlignCenter)
        f_size = USER_CONFIG["FONT_SIZES"].get("APP_TITLE", 18)
        title.setStyleSheet(f"color: white; font-family: '{USER_CONFIG['FONT_FAMILY']}'; font-size: {f_size}px; font-weight: bold;")

        # --- 新增: 管理按钮区 ---
        self.create_management_buttons(container)
        
        # 分类列表 - 调整高度以容纳新按钮
        self.category_list = QListWidget(container)
        self.category_list.setGeometry(0, 130, self.SIDEBAR_W, self.H - 170) 
        self.category_list.setFocusPolicy(Qt.NoFocus)
        self.category_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        cat_f_size = USER_CONFIG["FONT_SIZES"].get("CATEGORY", 15)
        self.category_list.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; }}
            QListWidget::item {{
                height: 45px;
                color: rgba(255,255,255,0.7);
                font-family: '{USER_CONFIG['FONT_FAMILY']}';
                font-size: {cat_f_size}px;
                padding-left: 0px; 
                margin-bottom: 2px;
                border: none;
            }}
            QListWidget::item:hover {{ 
                color: #ffffff;
                padding-left: 20px;
                background: rgba(255,255,255,0.1); 
            }}
            QListWidget::item:selected {{
                color: #FFFFFF;
                font-weight: bold;
                background: rgba(255, 255, 255, 30);
                border-left: 4px solid #00aaff;
                color: #00aaff;
            }}
        """)
        self.category_list.currentItemChanged.connect(self.on_category_changed)
        # 允许右键菜单
        self.category_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.category_list.customContextMenuRequested.connect(self.on_category_context_menu)


        # 版本号
        ver = QLabel(USER_CONFIG.get("VERSION_TEXT", "Version: 11.0"), container)
        ver.setGeometry(*USER_CONFIG.get("VERSION_Geometry", (0, 730, 256, 20)))
        ver.setAlignment(Qt.AlignCenter)
        v_f_size = USER_CONFIG["FONT_SIZES"].get("VERSION", 12)
        ver.setStyleSheet(f"color: rgba(255,255,255,0.3); font-size: {v_f_size}px;")

    def create_management_buttons(self, parent):
        """在侧边栏添加管理按钮 (取代旧版左侧的多个按钮)"""
        y_start = 75 # 位于标题下方
        h = 25
        
        # 1. 添加分类按钮
        btn_add_cat = QLabel("➕ 添加分类", parent)
        btn_add_cat.setGeometry(5, y_start, self.SIDEBAR_W // 2 - 7, h)
        btn_add_cat.setAlignment(Qt.AlignCenter)
        btn_add_cat.setStyleSheet(f"""
            QLabel {{ background-color: #00aaff; color: white; border-radius: 5px; font-weight: normal; font-size: 13px; }}
            QLabel:hover {{ background-color: #0088cc; }} 
        """)
        btn_add_cat.setCursor(Qt.PointingHandCursor)
        btn_add_cat.mousePressEvent = lambda e: self.add_category()
        
        # 2. 添加软件按钮 (连接到 add_software 方法)
        btn_add_tool = QLabel("📁 添加软件", parent)
        btn_add_tool.setGeometry(self.SIDEBAR_W // 2 + 2, y_start, self.SIDEBAR_W // 2 - 7, h)
        btn_add_tool.setAlignment(Qt.AlignCenter)
        btn_add_tool.setStyleSheet(f"""
            QLabel {{ background-color: #2ECC71; color: white; border-radius: 5px; font-weight: normal; font-size: 13px; }}
            QLabel:hover {{ background-color: #27AE60; }} 
        """)
        btn_add_tool.setCursor(Qt.PointingHandCursor)
        btn_add_tool.mousePressEvent = lambda e: self.add_software()

    def create_content_area(self):
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setGeometry(self.SIDEBAR_W, 60, self.CONTENT_W, self.H - 60)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical { width: 6px; background: transparent; margin: 0px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.2); min-height: 20px; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::sub-page:vertical, QScrollBar::add-page:vertical { background: none; }
        """)

        self.responsive_container = ResponsiveContainer()
        self.responsive_container.setStyleSheet("background: transparent;")
        self.scroll_area.setWidget(self.responsive_container)

    def create_top_elements(self):
        # 描述框
        self.desc_label = QLabel("", self)
        self.desc_label.setGeometry(*USER_CONFIG.get("DESC_Geometry", (280, 15, 870, 35)))
        self.desc_label.setAlignment(USER_CONFIG.get("DESC_ALIGN", Qt.AlignCenter))
        d_f_size = USER_CONFIG["FONT_SIZES"].get("DESCRIPTION", 14)
        self.desc_label.setStyleSheet(f"""
            color: rgba(255,255,255,0.9); 
            font-family: '{USER_CONFIG['FONT_FAMILY']}'; 
            font-size: {d_f_size}px;
        """)

        # 控制按钮
        close_conf = USER_CONFIG["BTN_CLOSE"]
        btn_close = QLabel(close_conf["TEXT"], self)
        btn_close.setGeometry(*close_conf["GEOMETRY"])
        btn_close.setAlignment(Qt.AlignCenter)
        btn_close.setStyleSheet(f"""
            QLabel {{ color: white; font-size: {close_conf['FONT_SIZE']}px; background: transparent; }}
            QLabel:hover {{ background-color: rgba(255, 0, 0, 0.3); }} 
        """)
        btn_close.setCursor(Qt.PointingHandCursor)
        # 更改关闭操作为 self.close()，它会触发 closeEvent
        btn_close.mousePressEvent = lambda e: self.close() 
        
        min_conf = USER_CONFIG["BTN_MIN"]
        btn_min = QLabel(min_conf["TEXT"], self)
        btn_min.setGeometry(*min_conf["GEOMETRY"])
        btn_min.setAlignment(Qt.AlignCenter)
        btn_min.setStyleSheet(f"""
            QLabel {{ color: white; font-size: {min_conf['FONT_SIZE']}px; background: transparent; }}
            QLabel:hover {{ background-color: rgba(255, 255, 255, 0.1); }}
        """)
        btn_min.setCursor(Qt.PointingHandCursor)
        btn_min.mousePressEvent = lambda e: self.showMinimized()

    # --- 数据加载/保存/关闭 ---
    def load_data(self):
        json_path = os.path.join(self.current_dir, USER_CONFIG.get("JSON_FILE", "data.json"))
        self.data_path = json_path
        if not os.path.exists(json_path): 
            self.data = {}
            QMessageBox.information(self, "提示", f"数据文件 '{USER_CONFIG.get('JSON_FILE', 'data.json')}' 未找到，已初始化空数据。")
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            for category in self.data.keys():
                item = QListWidgetItem(category)
                item.setTextAlignment(Qt.AlignCenter) 
                self.category_list.addItem(item)
            
            # 默认选中第一个分类
            if self.category_list.count() > 0:
                 self.category_list.setCurrentRow(0)
        except Exception as e:
            QMessageBox.critical(self, "数据错误", f"加载数据时发生错误: {e}")

    def save_data(self):
        """保存数据到 data.json"""
        if not self.is_dirty:
            return True
        
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            self.is_dirty = False
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存数据时发生错误: {e}")
            return False

    def closeEvent(self, event):
        """拦截窗口关闭事件，检查是否有未保存的数据"""
        if self.is_dirty:
            reply = QMessageBox.question(
                self, '确认退出',
                "数据已修改，是否保存并退出?", 
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, 
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                if self.save_data():
                    event.accept()
                else:
                    event.ignore() # 如果保存失败，忽略关闭
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    # --- 分类管理方法 ---
    def on_category_changed(self, item):
        if not item: return
        self.responsive_container.clear_tools()
        tools = self.data.get(item.text(), [])
        
        for tool_str in tools:
            parts = tool_str.split("|")
            if len(parts) >= 3:
                name = parts[0].strip()
                desc = parts[1].strip()
                path = parts[2].strip() 
                
                # 传递完整的工具字符串给 ToolItem
                btn = ToolItem(name, desc, path, tool_str, self) 
                self.responsive_container.add_tool(btn)

    def on_category_context_menu(self, point):
        """分类列表右键菜单"""
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

    def add_category(self):
        """添加新分类"""
        new_category, ok = QInputDialog.getText(self, '添加分类', '请输入新的分类名称:', text='新分类')
        
        if ok and new_category and new_category not in self.data:
            self.data[new_category] = []
            item = QListWidgetItem(new_category)
            item.setTextAlignment(Qt.AlignCenter)
            self.category_list.addItem(item)
            self.category_list.setCurrentItem(item)
            self.is_dirty = True
        elif ok and new_category in self.data:
            QMessageBox.warning(self, "警告", "分类名称已存在！")

    def rename_category(self, item):
        """修改分类名称"""
        old_category = item.text()
        new_category, ok = QInputDialog.getText(self, '修改分类名称', '请输入新的分类名称:', text=old_category)
        
        if ok and new_category and new_category != old_category:
            if new_category in self.data:
                QMessageBox.warning(self, "警告", "新分类名称已存在！")
                return
                
            self.data[new_category] = self.data.pop(old_category)
            item.setText(new_category)
            self.is_dirty = True
            
    def delete_category(self, item):
        """删除分类"""
        category_name = item.text()
        reply = QMessageBox.question(
            self, '确认删除',
            f"您确定要删除分类 '{category_name}' 吗？\n此操作将删除分类下的所有软件。", 
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.data.pop(category_name, None)
            self.category_list.takeItem(self.category_list.row(item))
            self.is_dirty = True
            self.responsive_container.clear_tools()
            self.update_description("")
            
    # --- 软件管理方法 ---
    def show_tool_context_menu(self, tool_info_str, global_pos):
        """显示软件工具的右键管理菜单"""
        if not self.category_list.currentItem(): return

        menu = QMenu(self)
        
        action_edit = QAction("修改软件信息", self)
        action_edit.triggered.connect(lambda: self.edit_software(tool_info_str))
        menu.addAction(action_edit)

        action_delete = QAction("删除软件", self)
        action_delete.triggered.connect(lambda: self.delete_software(tool_info_str))
        menu.addAction(action_delete)
        
        menu.exec_(global_pos)

    def add_software(self):
        """打开添加软件对话框"""
        current_item = self.category_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先在左侧选择一个分类！")
            return
        
        category = current_item.text()
        dialog = AddEditSoftwareDialog(self, category)
        
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            self.data[category].append(dialog.result)
            self.is_dirty = True
            self.on_category_changed(current_item) # 刷新 UI

    def edit_software(self, old_tool_info_str):
        """打开编辑软件对话框"""
        current_item = self.category_list.currentItem()
        if not current_item: return
        
        category = current_item.text()
        dialog = AddEditSoftwareDialog(self, category, old_tool_info_str)
        
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            if old_tool_info_str in self.data[category]:
                index = self.data[category].index(old_tool_info_str)
                self.data[category][index] = dialog.result
                self.selected_software_info = dialog.result # 更新选中状态
                self.is_dirty = True
                self.on_category_changed(current_item) # 刷新 UI
            else:
                 QMessageBox.warning(self, "错误", "未能找到原软件信息进行更新！")


    def delete_software(self, tool_info_str):
        """删除软件"""
        current_item = self.category_list.currentItem()
        if not current_item: return
        category = current_item.text()
        
        # 解析软件名称
        try:
            name = tool_info_str.split(' | ')[0]
        except:
             name = "未知软件"
        
        reply = QMessageBox.question(
            self, '确认删除',
            f"您确定要删除分类 [{category}] 下的软件 '{name}' 吗?", 
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if tool_info_str in self.data[category]:
                self.data[category].remove(tool_info_str)
                self.selected_software_info = None 
                self.is_dirty = True
                self.on_category_changed(current_item) 
                QMessageBox.information(self, "成功", f"软件 '{name}' 已删除。")
            else:
                 QMessageBox.warning(self, "错误", "未能找到该软件进行删除！")

    # --- 运行/操作方法 (保持不变) ---
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
                if os.name == 'nt': # Windows系统
                    os.startfile(full_path)
                else: # 其他系统（如Linux/macOS）
                    subprocess.Popen(
                        [full_path], 
                        cwd=os.path.dirname(full_path)
                    )
                
                time.sleep(1) 
                QTimer.singleShot(0, lambda: self.desc_label.setText(""))
                
            except Exception as e:
                error_msg = f"启动失败！错误: {e}"
                print(error_msg)
                QTimer.singleShot(0, lambda: self.desc_label.setText(error_msg))

        threading.Thread(target=_run, daemon=True).start()
    
    def open_folder(self, path):
        full_path = os.path.join(self.current_dir, path.lstrip(os.sep))
        target = full_path if os.path.isdir(full_path) and os.path.exists(full_path) else os.path.dirname(full_path)
        
        if os.name == 'nt': # Windows
            subprocess.Popen(f'explorer /select,"{os.path.abspath(full_path)}"', shell=True)
        elif sys.platform == 'darwin': # macOS
            subprocess.Popen(['open', os.path.abspath(target)])
        else: # Linux
            subprocess.Popen(['xdg-open', os.path.abspath(target)])


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)
    def mouseReleaseEvent(self, event):
        self.drag_pos = None

if __name__ == "__main__":
    # 1. 获取程序运行目录
    current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    # 2. 尝试加载配置，如果失败，则退出
    if not load_config(current_dir):
        # 此时还没有 QApplication，所以只能用 print 或 sys.exit(1)
        sys.exit(1)
        
    # 3. 🚨 关键修复：创建 QApplication 实例
    app = QApplication(sys.argv)
    
    # 4. 设置全局字体
    font = QFont(USER_CONFIG["FONT_FAMILY"])
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    
    # 5. 创建主窗口
    win = MainWindow()
    win.show()
    
    # 6. 运行事件循环
    sys.exit(app.exec_())
