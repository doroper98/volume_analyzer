import sys
import os
import math

# PySide6를 사용하도록 설정
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QFrame, QSplitter, QGroupBox, 
                             QFormLayout, QDoubleSpinBox, QComboBox, QScrollArea, QMessageBox,
                             QRadioButton, QButtonGroup, QLineEdit, QGridLayout, QSlider)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap, QPen, QBrush

import pyvista as pv
from pyvistaqt import QtInteractor

from core.module_engine import ModuleEngine
from core.pack_engine import PackEngine

# 스타일 정의 (최상의 밝은 레이아웃)
STYLE_SHEET = """
QMainWindow { background-color: #F8F9FA; }
QWidget { background-color: #F8F9FA; color: #212529; font-family: 'Segoe UI', sans-serif; }
QFrame.Panel { background-color: #FFFFFF; border: 1px solid #DEE2E6; border-radius: 8px; }
QGroupBox { border: 1px solid #CED4DA; border-radius: 10px; margin-top: 15px; padding-top: 20px; font-weight: bold; color: #007AFF; background-color: #FFFFFF; }
QLabel#Header { font-size: 14px; font-weight: 800; color: #495057; padding-bottom: 5px; border-bottom: 2px solid #007AFF; margin-bottom: 10px; }
QPushButton { background-color: #E9ECEF; border: 1px solid #CED4DA; padding: 10px; border-radius: 6px; font-weight: 600; }
QPushButton:hover { background-color: #DEE2E6; }
QPushButton#Primary { background-color: #007AFF; color: white; border: none; }
QPushButton#Primary:hover { background-color: #0056B3; }
QDoubleSpinBox, QComboBox { background-color: #FFFFFF; border: 1px solid #CED4DA; padding: 5px; border-radius: 5px; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 20px;
    height: 12px;
    background: #F8F9FA;
    border-left: 1px solid #CED4DA;
}
QDoubleSpinBox::up-button {
    border-top-right-radius: 5px;
    border-bottom: 0.5px solid #CED4DA;
}
QDoubleSpinBox::down-button {
    border-bottom-right-radius: 5px;
    border-top: 0.5px solid #CED4DA;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: #DEE2E6;
}
QDoubleSpinBox::up-arrow {
    image: url(none); /* Remove default arrow */
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #495057;
    width: 0; height: 0;
}
QDoubleSpinBox::down-arrow {
    image: url(none);
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #495057;
    width: 0; height: 0;
}
QScrollArea { border: none; background-color: transparent; }
"""

class EcoPackApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EcoPack Optimizer v3.0 - Dual View Professional")
        self.setMinimumSize(1800, 1000)
        
        # 스타일 보강 (시인성 개선: 은은한 하늘색)
        self.STYLE_MOD = """
            QPushButton:checked { 
                background-color: #E3F2FD; 
                border: 2px solid #2196F3; 
                border-radius: 8px;
            }
            QLabel#CountLabel {
                font-size: 10px;
                color: #007AFF;
                font-weight: bold;
                background: transparent;
            }
        """
        
        self.module_engine = ModuleEngine()
        self.pack_engine = PackEngine()
        
        # State
        self.pack_info = None
        self.optimized_module_data = None
        self.final_result = None
        self.current_cell_rotation = 0 # 0 or 90
        self.last_manual_gap = 2.0
        
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 1. 왼쪽 패널 (Cell & Module Specs)
        left_panel = QFrame()
        left_panel.setFixedWidth(350)
        left_panel.setObjectName("Panel")
        left_panel.setProperty("class", "Panel")
        left_panel_layout = QVBoxLayout(left_panel)
        
        l_header = QLabel("MODULE & CELL DESIGN")
        l_header.setObjectName("Header")
        left_panel_layout.addWidget(l_header)
        
        l_content_layout = QVBoxLayout()
        l_content_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.addLayout(l_content_layout)
        
        # Cell Section
        cell_group = QGroupBox("CELL SPECIFICATIONS")
        self.cell_grid = QGridLayout(cell_group)
        self.cell_grid.setSpacing(8)
        
        # Type Selection (Button Group) - Row 0
        self.cell_type_group = QButtonGroup(self)
        self.cell_type_group.setExclusive(True)
        self.cell_type_layout = QHBoxLayout()
        
        types = [
            ("Cylindrical", "Cylindrical (원통형)"),
            ("Prismatic", "Prismatic (각형)"),
            ("Pouch", "Pouch (파우치)")
        ]
        
        for i, (short_name, full_name) in enumerate(types):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(60, 45)
            btn.setToolTip(full_name)
            btn.setProperty("cell_type_full", full_name)
            btn.clicked.connect(lambda checked, name=full_name: self.on_cell_type_changed(name))
            self.cell_type_group.addButton(btn)
            self.cell_type_layout.addWidget(btn)
            if i == 0: btn.setChecked(True)
            
        self.type_label = QLabel("Type")
        self.cell_grid.addWidget(self.type_label, 0, 0)
        self.cell_grid.addLayout(self.cell_type_layout, 0, 1, 1, 3)
        
        # Std Preset (Cylindrical only) - Row 1
        self.std_size_label = QLabel("Std Size")
        self.std_preset = QComboBox()
        self.std_preset.addItems(["Custom", "18650 (D18 H65)", "21700 (D21 H70)", "4680 (D46 H80)"])
        self.std_preset.currentTextChanged.connect(self.on_preset_changed)
        self.cell_grid.addWidget(self.std_size_label, 1, 0)
        self.cell_grid.addWidget(self.std_preset, 1, 1, 1, 3)
        
        # Row 2: Dimensions (공통, 라벨과 위치만 다름)
        self.dim_label = QLabel("D / H")
        self.cell_l_label = QLabel("Diameter")
        self.cell_l = self.create_spinbox(None, "", 18)
        self.cell_l.valueChanged.connect(self.update_module_view)
        
        self.cell_h_label = QLabel("Height")
        self.cell_h = self.create_spinbox(None, "", 65)
        self.cell_h.valueChanged.connect(self.update_module_view)

        self.cell_w_label = QLabel("Width")
        self.cell_w = self.create_spinbox(None, "", 27)
        self.cell_w.valueChanged.connect(self.update_module_view)
        
        self.cell_grid.addWidget(self.dim_label, 2, 0)
        self.cell_grid.addWidget(self.cell_l, 2, 1)
        self.cell_grid.addWidget(self.cell_w, 2, 2)
        self.cell_grid.addWidget(self.cell_h, 2, 3)
        
        # Row 3: Gaps
        self.cell_gap_label = QLabel("Cell 간 갭")
        self.cell_gap = self.create_spinbox(None, "", 2)
        self.cell_gap.valueChanged.connect(self.update_module_view)
        
        self.wall_gap_label = QLabel("Wall Gap")
        self.wall_gap = self.create_spinbox(None, "", 2)
        self.wall_gap.valueChanged.connect(self.update_module_view)
        
        self.cell_grid.addWidget(self.cell_gap_label, 3, 0)
        self.cell_grid.addWidget(self.cell_gap, 3, 1)
        self.cell_grid.addWidget(self.wall_gap_label, 3, 2)
        self.cell_grid.addWidget(self.wall_gap, 3, 3)
        
        # Row 4: Rotate (Prismatic/Pouch only)
        self.btn_rotate = QPushButton("Rotate 90°")
        self.btn_rotate.setFixedWidth(100)
        self.btn_rotate.clicked.connect(self.rotate_cell)
        self.cell_grid.addWidget(self.btn_rotate, 4, 1, 1, 3)
        
        # Row 5: Pattern Label (Cylindrical only)
        self.pattern_label = QLabel("Pattern Selection")
        self.pattern_label.setStyleSheet("font-weight: bold; margin-top: 2px;")
        self.cell_grid.addWidget(self.pattern_label, 5, 0, 1, 4)
        
        # Row 6: Pattern Buttons (Cylindrical only)
        self.pattern_btn_layout = QGridLayout()
        self.pattern_group = QButtonGroup(self)
        self.pattern_group.setExclusive(True)
        
        self.pattern_widgets = [] # (button, label, full_name)
        
        patterns = [
            ("Grid (정사각형)", "Grid"),
            ("Hexagonal-H (가로 육각)", "Hex-H"),
            ("Hexagonal-V (세로 육각)", "Hex-V"),
            ("Diagonal (대각)", "Diag"),
            ("Staggered (엇갈림)", "Stag")
        ]
        
        for i, (full_name, short_name) in enumerate(patterns):
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(2)
            
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(50, 40)
            btn.setToolTip(full_name)
            btn.setIcon(self.create_pattern_icon(full_name))
            btn.setIconSize(QSize(40, 30))
            btn.setProperty("pattern_name", full_name)
            btn.clicked.connect(self.on_layout_button_clicked)
            
            count_label = QLabel("0 EA")
            count_label.setObjectName("CountLabel")
            count_label.setAlignment(Qt.AlignCenter)
            
            vbox.addWidget(btn)
            vbox.addWidget(count_label)
            
            if i == 0: btn.setChecked(True)
            
            self.pattern_group.addButton(btn)
            self.pattern_btn_layout.addWidget(container, 0, i)
            self.pattern_widgets.append((btn, count_label, full_name))
            
        self.cell_grid.addLayout(self.pattern_btn_layout, 6, 0, 1, 4)

        # Row 7-8: Alignment Section (공통)
        self.align_label = QLabel("Batch Alignment (X / Y)")
        self.align_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.cell_grid.addWidget(self.align_label, 7, 0, 1, 4)

        self.align_x_group = QButtonGroup(self)
        self.align_x_group.setExclusive(True)
        self.align_x_layout = QHBoxLayout()
        for i, (label, val) in enumerate([("Left", "Start"), ("Right", "End"), ("Center", "Center"), ("Even", "Even")]):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(50, 40)
            btn.setIcon(self.create_alignment_icon('X', val))
            btn.setIconSize(QSize(40, 30))
            btn.setToolTip(label)
            if val == "Center": btn.setChecked(True)
            btn.setProperty("align_val", val)
            btn.clicked.connect(self.on_layout_button_clicked)
            self.align_x_group.addButton(btn)
            self.align_x_layout.addWidget(btn)
        self.cell_grid.addLayout(self.align_x_layout, 8, 0, 1, 4)

        self.align_y_group = QButtonGroup(self)
        self.align_y_group.setExclusive(True)
        self.align_y_layout = QHBoxLayout()
        for i, (label, val) in enumerate([("Top", "End"), ("Bottom", "Start"), ("Middle", "Center"), ("Even", "Even")]):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(50, 40)
            btn.setIcon(self.create_alignment_icon('Y', val))
            btn.setIconSize(QSize(40, 30))
            btn.setToolTip(label)
            if val == "Center": btn.setChecked(True)
            btn.setProperty("align_val", val)
            btn.clicked.connect(self.on_layout_button_clicked)
            self.align_y_group.addButton(btn)
            self.align_y_layout.addWidget(btn)
        self.cell_grid.addLayout(self.align_y_layout, 9, 0, 1, 4)

        # 원통형 전용 / 각형·파우치 전용 위젯 목록 (가시성 토글용)
        self._cylindrical_only = [self.std_size_label, self.std_preset, self.pattern_label]
        # pattern container widgets
        for btn, label, _ in self.pattern_widgets:
            self._cylindrical_only.append(btn.parentWidget())
        
        self._prismatic_only = [self.cell_w, self.btn_rotate]
        
        l_content_layout.addWidget(cell_group)
        
        # Module Section
        mod_group = QGroupBox("MODULE HOUSING")
        self.mod_grid = QGridLayout(mod_group)
        self.mod_grid.setSpacing(8)
        
        self.mod_l = self.create_spinbox(None, "", 400)
        self.mod_w = self.create_spinbox(None, "", 200)
        self.mod_h = self.create_spinbox(None, "", 100)
        self.wall_t = self.create_spinbox(None, "", 5)
        self.bottom_t = self.create_spinbox(None, "", 5)
        self.top_t = self.create_spinbox(None, "", 5)
        
        self.mod_grid.addWidget(QLabel("Outer L/W/H"), 0, 0)
        self.mod_grid.addWidget(self.mod_l, 0, 1)
        self.mod_grid.addWidget(self.mod_w, 0, 2)
        self.mod_grid.addWidget(self.mod_h, 0, 3)
        
        self.mod_grid.addWidget(QLabel("T (W/B/T)"), 1, 0)
        self.mod_grid.addWidget(self.wall_t, 1, 1)
        self.mod_grid.addWidget(self.bottom_t, 1, 2)
        self.mod_grid.addWidget(self.top_t, 1, 3)
        
        self.mod_l.valueChanged.connect(self.update_module_view)
        self.mod_w.valueChanged.connect(self.update_module_view)
        self.mod_h.valueChanged.connect(self.update_module_view)
        self.wall_t.valueChanged.connect(self.update_module_view)
        self.bottom_t.valueChanged.connect(self.update_module_view)
        self.top_t.valueChanged.connect(self.update_module_view)
        
        # Opacity Slider for Module
        self.mod_opacity = QSlider(Qt.Horizontal)
        self.mod_opacity.setRange(0, 100)
        self.mod_opacity.setValue(10) # Default 0.1
        self.mod_opacity.valueChanged.connect(self.update_module_view)
        self.mod_grid.addWidget(QLabel("Opacity"), 2, 0)
        self.mod_grid.addWidget(self.mod_opacity, 2, 1, 1, 3)
        
        # Gap Section (New)
        gap_inner_group = QGroupBox("VERTICAL PLACEMENT")
        self.gap_layout = QFormLayout(gap_inner_group)
        
        # Mode Toggle (Bottom vs Top)
        self.gap_mode_combo = QComboBox()
        self.gap_mode_combo.addItems(["Bottom Gap Input", "Top Gap Input"])
        self.gap_mode_combo.currentTextChanged.connect(self.sync_gap_ui)
        self.gap_layout.addRow(self.gap_mode_combo)
        
        self.gap_input_pair = QHBoxLayout()
        self.gap_input_label = QLabel("Gap Val")
        self.gap_input = self.create_spinbox(None, "", 2)
        self.gap_input.valueChanged.connect(self.calculate_vertical_gaps)
        self.gap_input_pair.addWidget(self.gap_input_label)
        self.gap_input_pair.addWidget(self.gap_input)
        
        self.gap_res_pair = QHBoxLayout()
        self.gap_result_label = QLabel("Calc Gap")
        self.gap_result_val = QLineEdit("0.0")
        self.gap_result_val.setReadOnly(True)
        self.gap_result_val.setStyleSheet("background-color: #E9ECEF; font-weight: bold;")
        self.gap_res_pair.addWidget(self.gap_result_label)
        self.gap_res_pair.addWidget(self.gap_result_val)
        
        self.gap_layout.addRow(self.gap_input_pair)
        self.gap_layout.addRow(self.gap_res_pair)
        
        self.v_error_label = QLabel("")
        self.v_error_label.setStyleSheet("color: red; font-weight: bold;")
        self.gap_layout.addRow(self.v_error_label)
        
        # Connections
        self.mod_h.valueChanged.connect(self.calculate_vertical_gaps)
        self.wall_t.valueChanged.connect(self.calculate_vertical_gaps)
        self.bottom_t.valueChanged.connect(self.calculate_vertical_gaps)
        self.top_t.valueChanged.connect(self.calculate_vertical_gaps)
        self.cell_h.valueChanged.connect(self.calculate_vertical_gaps)
        
        l_content_layout.addWidget(mod_group)
        l_content_layout.addWidget(gap_inner_group)
        
        l_content_layout.addStretch()
        
        self.btn_opt_mod = QPushButton("Step 1: Optimize Module")
        self.btn_opt_mod.setObjectName("Primary")
        self.btn_opt_mod.clicked.connect(self.optimize_module)
        left_panel_layout.addWidget(self.btn_opt_mod)
        
        # 2 & 3. 3D Viewers Area (Center)
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        # 3D View Controls
        view_ctrl_layout = QHBoxLayout()
        self.btn_ortho = QPushButton("Parallel (OFF)")
        self.btn_ortho.setCheckable(True)
        self.btn_ortho.setFixedWidth(120)
        self.btn_ortho.clicked.connect(self.toggle_projection)
        
        self.btn_view_xy = QPushButton("Top (XY)")
        self.btn_view_yz = QPushButton("Side (YZ)")
        self.btn_view_xz = QPushButton("Front (XZ)")
        self.btn_view_iso = QPushButton("ISO")
        
        for btn in [self.btn_view_xy, self.btn_view_yz, self.btn_view_xz, self.btn_view_iso]:
            btn.setFixedWidth(80)
            btn.clicked.connect(self.set_view_preset)
            
        view_ctrl_layout.addStretch()
        view_ctrl_layout.addWidget(self.btn_ortho)
        view_ctrl_layout.addWidget(self.btn_view_xy)
        view_ctrl_layout.addWidget(self.btn_view_yz)
        view_ctrl_layout.addWidget(self.btn_view_xz)
        view_ctrl_layout.addWidget(self.btn_view_iso)
        view_ctrl_layout.addStretch()
        center_layout.addLayout(view_ctrl_layout)
        
        viewers_splitter = QSplitter(Qt.Horizontal)
        viewers_splitter.setHandleWidth(12)
        viewers_splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                background-color: transparent;
                margin: 0 2px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: rgba(0, 0, 0, 0.03);
            }
        """)
        
        # 2. 왼쪽 3D 뷰어 (Module View)
        self.module_viewer_frame = QFrame()
        self.module_viewer_frame.setStyleSheet("background-color: white; border: 1px solid #DEE2E6; border-radius: 8px;")
        mv_layout = QVBoxLayout(self.module_viewer_frame)
        self.module_plotter = QtInteractor(self.module_viewer_frame)
        self.module_plotter.set_background("white")
        mv_layout.addWidget(self.module_plotter.interactor)
        mv_label = QLabel("MODULE & CELL PREVIEW")
        mv_label.setAlignment(Qt.AlignCenter)
        mv_label.setStyleSheet("font-weight: bold; color: #6C757D;")
        mv_layout.addWidget(mv_label)
        
        # 3. 오른쪽 3D 뷰어 (Pack View)
        self.pack_viewer_frame = QFrame()
        self.pack_viewer_frame.setStyleSheet("background-color: white; border: 1px solid #DEE2E6; border-radius: 8px;")
        pv_layout = QVBoxLayout(self.pack_viewer_frame)
        self.pack_plotter = QtInteractor(self.pack_viewer_frame)
        self.pack_plotter.set_background("white")
        pv_layout.addWidget(self.pack_plotter.interactor)
        pv_label = QLabel("FULL PACK ASSEMBLY PREVIEW")
        pv_label.setAlignment(Qt.AlignCenter)
        pv_label.setStyleSheet("font-weight: bold; color: #6C757D;")
        pv_layout.addWidget(pv_label)
        
        viewers_splitter.addWidget(self.module_viewer_frame)
        viewers_splitter.addWidget(self.pack_viewer_frame)
        viewers_splitter.setSizes([500, 500])  # 초기 비율 50:50
        
        # 스플리터 핸들에 그립 바 추가
        handle = viewers_splitter.handle(1)
        grip_layout = QVBoxLayout(handle)
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_bar = QFrame(handle)
        grip_bar.setFixedSize(4, 40)
        grip_bar.setStyleSheet("""
            background-color: #ADB5BD;
            border-radius: 2px;
        """)
        grip_bar.setCursor(Qt.SplitHCursor)
        grip_layout.addStretch()
        grip_layout.addWidget(grip_bar, 0, Qt.AlignCenter)
        grip_layout.addStretch()
        
        center_layout.addWidget(viewers_splitter, 1)
        
        # 4. 오른쪽 패널 (Pack Housing & Placement)
        right_panel = QFrame()
        right_panel.setFixedWidth(350)
        right_panel.setObjectName("Panel")
        right_panel.setProperty("class", "Panel")
        right_panel_layout = QVBoxLayout(right_panel)
        
        r_header = QLabel("PACK CONFIGURATION")
        r_header.setObjectName("Header")
        right_panel_layout.addWidget(r_header)
        
        r_content_layout = QVBoxLayout()
        r_content_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.addLayout(r_content_layout)
        
        # Pack Housing Section
        pack_housing_group = QGroupBox("PACK HOUSING")
        ph_layout = QVBoxLayout(pack_housing_group)
        self.btn_load_pack = QPushButton("Load Pack STEP File")
        self.btn_load_pack.clicked.connect(self.load_step_file)
        ph_layout.addWidget(self.btn_load_pack)
        self.pack_file_label = QLabel("No file loaded")
        self.pack_file_label.setStyleSheet("font-size: 11px; color: #6C757D;")
        ph_layout.addWidget(self.pack_file_label)

        # Pack Thickness (Subscribed to Side Wall and Bottom)
        thickness_grid = QGridLayout()
        thickness_grid.addWidget(QLabel("Side Wall T"), 0, 0)
        self.pack_wall_t = self.create_spinbox(None, "", 5, update_module=False) 
        self.pack_wall_t.valueChanged.connect(self.optimize_pack) # 즉시 재배치
        thickness_grid.addWidget(self.pack_wall_t, 0, 1)

        thickness_grid.addWidget(QLabel("Bottom T"), 0, 2)
        self.pack_bottom_t = self.create_spinbox(None, "", 5, update_module=False) 
        self.pack_bottom_t.valueChanged.connect(self.optimize_pack) # 즉시 재배치
        thickness_grid.addWidget(self.pack_bottom_t, 0, 3)
        ph_layout.addLayout(thickness_grid)
        
        # Opacity Slider for Pack
        self.pack_opacity = QSlider(Qt.Horizontal)
        self.pack_opacity.setRange(0, 100)
        self.pack_opacity.setValue(5) # Default 0.05
        self.pack_opacity.valueChanged.connect(self.update_pack_view)
        ph_layout.addWidget(QLabel("Housing Opacity"))
        ph_layout.addWidget(self.pack_opacity)
        
        r_content_layout.addWidget(pack_housing_group)
        
        # Pack Opt Section
        pack_opt_group = QGroupBox("PACK PLACEMENT")
        p_opt_layout = QVBoxLayout(pack_opt_group)
        
        # Row 1: Mod Gap
        gap_row = QHBoxLayout()
        gap_row.addWidget(QLabel("Mod Gap"))
        self.mod_clearance = self.create_spinbox(None, "", 10, update_module=False)
        self.mod_clearance.valueChanged.connect(self.update_pack_view)
        gap_row.addWidget(self.mod_clearance)
        p_opt_layout.addLayout(gap_row)
        
        # Row 2: Rotate Module 90°
        self.pack_module_rotated = False
        self.btn_rotate_module = QPushButton("Rotate Module 90°")
        self.btn_rotate_module.setFixedHeight(35)
        self.btn_rotate_module.clicked.connect(self.rotate_pack_module)
        p_opt_layout.addWidget(self.btn_rotate_module)
        
        # Row 3: Module Alignment X
        pack_align_x_label = QLabel("Module Align X")
        pack_align_x_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        p_opt_layout.addWidget(pack_align_x_label)
        
        self.pack_align_x_group = QButtonGroup(self)
        self.pack_align_x_group.setExclusive(True)
        pack_ax_layout = QHBoxLayout()
        for label, val in [("Left", "Start"), ("Right", "End"), ("Center", "Center"), ("Even", "Even")]:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(50, 40)
            btn.setIcon(self.create_alignment_icon('X', val))
            btn.setIconSize(QSize(40, 30))
            btn.setToolTip(label)
            if val == "Center": btn.setChecked(True)
            btn.setProperty("align_val", val)
            btn.clicked.connect(self.optimize_pack)
            self.pack_align_x_group.addButton(btn)
            pack_ax_layout.addWidget(btn)
        p_opt_layout.addLayout(pack_ax_layout)
        
        # Row 4: Module Alignment Y
        pack_align_y_label = QLabel("Module Align Y")
        pack_align_y_label.setStyleSheet("font-weight: bold; margin-top: 2px;")
        p_opt_layout.addWidget(pack_align_y_label)
        
        self.pack_align_y_group = QButtonGroup(self)
        self.pack_align_y_group.setExclusive(True)
        pack_ay_layout = QHBoxLayout()
        for label, val in [("Top", "End"), ("Bottom", "Start"), ("Middle", "Center"), ("Even", "Even")]:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(50, 40)
            btn.setIcon(self.create_alignment_icon('Y', val))
            btn.setIconSize(QSize(40, 30))
            btn.setToolTip(label)
            if val == "Center": btn.setChecked(True)
            btn.setProperty("align_val", val)
            btn.clicked.connect(self.optimize_pack)
            self.pack_align_y_group.addButton(btn)
            pack_ay_layout.addWidget(btn)
        p_opt_layout.addLayout(pack_ay_layout)
        
        r_content_layout.addWidget(pack_opt_group)
        
        # Coordinate Adjustment
        move_group = QGroupBox("MANUAL POSITION ADJUST")
        move_grid = QGridLayout(move_group)
        self.off_x = self.create_spinbox(None, "", 0, range=(-2000, 2000), update_module=False)
        self.off_y = self.create_spinbox(None, "", 0, range=(-2000, 2000), update_module=False)
        self.off_z = self.create_spinbox(None, "", 0, range=(-2000, 2000), update_module=False)
        self.off_x.valueChanged.connect(self.update_pack_view)
        self.off_y.valueChanged.connect(self.update_pack_view)
        self.off_z.valueChanged.connect(self.update_pack_view)
        
        move_grid.addWidget(QLabel("X"), 0, 0)
        move_grid.addWidget(self.off_x, 0, 1)
        move_grid.addWidget(QLabel("Y"), 0, 2)
        move_grid.addWidget(self.off_y, 0, 3)
        move_grid.addWidget(QLabel("Z"), 1, 0)
        move_grid.addWidget(self.off_z, 1, 1, 1, 3)
        r_content_layout.addWidget(move_group)
        
        # New Meshing & Analysis Section
        mesh_group = QGroupBox("MESHING & ANALYSIS")
        mesh_layout = QVBoxLayout(mesh_group)
        
        self.btn_mesh_analyze = QPushButton("Analysis Inner Volume")
        self.btn_mesh_analyze.clicked.connect(self.analyze_inner_volume)
        mesh_layout.addWidget(self.btn_mesh_analyze)
        
        self.btn_gen_mesh = QPushButton("Generate Tetra Mesh")
        self.btn_gen_mesh.clicked.connect(self.generate_tetra_mesh)
        self.btn_gen_mesh.setEnabled(False)
        mesh_layout.addWidget(self.btn_gen_mesh)
        
        self.mesh_stats_label = QLabel("Nodes: 0 | Elements: 0")
        self.mesh_stats_label.setStyleSheet("font-size: 11px; color: #007AFF; font-weight: bold;")
        self.mesh_stats_label.setAlignment(Qt.AlignCenter)
        mesh_layout.addWidget(self.mesh_stats_label)
        
        r_content_layout.addWidget(mesh_group)
        
        r_content_layout.addStretch()
        
        self.btn_opt_pack = QPushButton("Step 2: Start Pack Placement")
        self.btn_opt_pack.setObjectName("Primary")
        self.btn_opt_pack.setEnabled(False)
        self.btn_opt_pack.clicked.connect(self.optimize_pack)
        right_panel_layout.addWidget(self.btn_opt_pack)
        
        self.export_btn = QPushButton("EXPORT FULL ASSEMBLY (STEP)")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_result)
        right_panel_layout.addWidget(self.export_btn)
        
        # 메인 레이아웃 결합
        main_layout.addWidget(left_panel)
        main_layout.addWidget(center_container, 1)
        main_layout.addWidget(right_panel)
        
        self.setStyleSheet(STYLE_SHEET + self.STYLE_MOD)
        
        # 초기 설정 호출
        # 초기 설정 호출
        self.on_cell_type_changed(None)
        
        # 기본 팩 파일 자동 로드
        self.load_default_pack()

    def load_default_pack(self):
        """지정된 기본 경로에서 pack.stp 파일을 자동으로 불러옵니다."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(base_dir, "sample", "pack.stp")
        
        if os.path.exists(default_path):
            self.process_loaded_pack(default_path)
        else:
            # 대체 경로 확인 (루트 폴더)
            alt_path = os.path.join(base_dir, "pack.stp")
            if os.path.exists(alt_path):
                self.process_loaded_pack(alt_path)

    def create_spinbox(self, layout, label, default_val, range=(0, 10000), update_module=True):
        sb = QDoubleSpinBox()
        sb.setRange(range[0], range[1])
        sb.setDecimals(1)
        sb.setValue(default_val)
        if update_module:
            sb.valueChanged.connect(self.on_geometry_changed)
        
        if layout:
            layout.addRow(label, sb)
        return sb

    def on_geometry_changed(self):
        """기하학적 파라미터가 변경되면 최적화 결과를 초기화합니다."""
        self.optimized_module_data = None
        self.final_result = None
        self.btn_opt_pack.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.update_module_view()

    def on_cell_type_changed(self, text):
        # 텍스트가 전달되지 않은 경우(초기화 등) 현재 체크된 버튼에서 가져옴
        if not text:
            checked_btn = self.cell_type_group.checkedButton()
            text = checked_btn.property("cell_type_full") if checked_btn else "Cylindrical (원통형)"
            
        is_cylindrical = "Cylindrical" in text
        is_prismatic_or_pouch = not is_cylindrical
        
        # 원통형 전용 위젯 가시성
        for w in self._cylindrical_only:
            w.setVisible(is_cylindrical)
        
        # 각형/파우치 전용 위젯 가시성
        for w in self._prismatic_only:
            w.setVisible(is_prismatic_or_pouch)
        
        # 라벨 텍스트 변경
        if is_cylindrical:
            self.dim_label.setText("D / H")
            self.cell_w.setVisible(False)
            self.std_preset.setCurrentText("18650 (D18 H65)")
        else:
            self.dim_label.setText("L / W / H")
            self.cell_w.setVisible(True)
            # 각형/파우치 기본값 설정
            if "Prismatic" in text:
                self.cell_l.setValue(148); self.cell_w.setValue(27); self.cell_h.setValue(91)
            else: # Pouch
                self.cell_l.setValue(200); self.cell_w.setValue(100); self.cell_h.setValue(10)
        
        # 아이콘 업데이트
        self.update_all_cell_icons()
        
        self.update_module_view()

    def rotate_cell(self):
        """Len과 Wid 값을 서로 바꾸어 셀을 90도 회전에 해당하는 배치가 되도록 합니다."""
        l = self.cell_l.value()
        w = self.cell_w.value()
        self.cell_l.blockSignals(True)
        self.cell_w.blockSignals(True)
        self.cell_l.setValue(w)
        self.cell_w.setValue(l)
        self.cell_l.blockSignals(False)
        self.cell_w.blockSignals(False)
        
        # 토글 상태 기록 (비주얼 회전 시 사용 가능)
        self.current_cell_rotation = 90 if self.current_cell_rotation == 0 else 0
        
        self.update_module_view()

    def get_current_cell_type(self):
        """현재 선택된 셀 타입 텍스트를 반환합니다."""
        checked_btn = self.cell_type_group.checkedButton()
        return checked_btn.property("cell_type_full") if checked_btn else "Cylindrical (원통형)"

    def create_pattern_icon(self, name):
        """프로그램적으로 패턴 아이콘을 생성합니다 (QPainter 활용)"""
        pixmap = QPixmap(100, 80)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 배경 원형 가이드 (선택 사항)
        # painter.setBrush(QColor("#F0F0F0"))
        # painter.drawRoundedRect(5, 5, 90, 90, 10, 10)
        
        if "Cylindrical" in self.get_current_cell_type():
            painter.setBrush(QColor("#007AFF"))
        else:
            painter.setBrush(QColor("#495057"))
        painter.setPen(Qt.NoPen)
        
        d = 15
        gap = 4
        start_x, start_y = 22, 12
        
        if "Grid" in name:
            for r in range(3):
                for c in range(3):
                    painter.drawEllipse(start_x + c*(d+gap), start_y + r*(d+gap), d, d)
        elif "Hexagonal-H" in name:
            for r in range(3):
                off = (d+gap)/2 if r % 2 != 0 else 0
                for c in range(3):
                    painter.drawEllipse(start_x + off + c*(d+gap) - 8, start_y + r*(d+gap)*0.85, d, d)
        elif "Hexagonal-V" in name:
            for c in range(3):
                off = (d+gap)/2 if c % 2 != 0 else 0
                for r in range(3):
                    painter.drawEllipse(start_x + c*(d+gap)*0.85, start_y + off + r*(d+gap) - 8, d, d)
        elif "Diagonal" in name:
            for r in range(3):
                off = (d+gap)/2 if r % 2 != 0 else 0
                for c in range(3):
                    painter.drawEllipse(start_x + off + c*(d+gap) - 4, start_y + r*(d+gap), d, d)
        elif "Staggered" in name:
            for r in range(3):
                off = (d+gap) * (r % 3) / 3
                for c in range(3):
                    painter.drawEllipse(start_x + off + c*(d+gap) - 8, start_y + r*(d+gap)*0.9, d, d)
        
        painter.end()
        return QIcon(pixmap)

    def create_alignment_icon(self, axis, align_type):
        """사용자가 업로드한 이미지 도식에 맞춰 정렬 아이콘을 생성합니다."""
        pixmap = QPixmap(100, 80)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 테두리 박스 (모듈 하우징 상징)
        painter.setPen(QPen(QColor("#007AFF"), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(5, 5, 90, 70, 8, 8)
        
        # 내부 셀 상징 (파란색 박스들)
        painter.setBrush(QColor("#A0C4FF"))
        painter.setPen(QPen(QColor("#007AFF"), 1))
        
        if axis == 'X':
            # 수직 바 3개
            w, h = 12, 40
            y = 20
            if align_type == "Start": # Left
                for i in range(3): painter.drawRect(12 + i*15, y, w, h)
            elif align_type == "End": # Right
                for i in range(3): painter.drawRect(53 + i*15, y, w, h)
            elif align_type == "Center": # Center
                for i in range(3): painter.drawRect(32 + i*15, y, w, h)
            elif align_type == "Even": # Spread
                for i in range(3): painter.drawRect(12 + i*30, y, w, h)
        else:
            # 수평 바 3개
            w, h = 40, 12
            x = 30
            if align_type == "End": # Top (Qt 좌표계 기준 작은 Y)
                for i in range(3): painter.drawRect(x, 12 + i*15, w, h)
            elif align_type == "Start": # Bottom (Qt 좌표계 기준 큰 Y)
                for i in range(3): painter.drawRect(x, 43 + i*15, w, h)
            elif align_type == "Center": # Center
                for i in range(3): painter.drawRect(x, 27 + i*15, w, h)
            elif align_type == "Even": # Spread
                for i in range(3): painter.drawRect(x, 12 + i*23, w, h)
        
        painter.end()
        return QIcon(pixmap)

    def update_alignment_icons(self):
        """현재 셀 이미지에 맞춰 아이콘을 갱신할 수 있으나, 여기서는 고정 도식 아이콘 사용"""
        pass

    def update_all_pattern_counts(self):
        """모든 패턴에 대해 배치 가능한 셀 개수를 실시간으로 계산하여 표시합니다."""
        cell_type_text = self.get_current_cell_type()
        if "Cylindrical" not in cell_type_text:
            return
            
        for btn, label, pattern_name in self.pattern_widgets:
            positions = self.module_engine.pack_cells_in_module(
                self.mod_l.value(), self.mod_w.value(), self.wall_t.value(),
                cell_type_text, self.cell_l.value(), self.cell_w.value(), self.cell_gap.value(),
                wall_gap=self.wall_gap.value(),
                pattern=pattern_name,
                align_x=self.align_x_group.checkedButton().property("align_val"),
                align_y=self.align_y_group.checkedButton().property("align_val")
            )
            label.setText(f"{len(positions)} EA")

    def sync_gap_ui(self):
        is_bottom = "Bottom" in self.gap_mode_combo.currentText()
        if is_bottom:
            self.gap_result_label.setText("Calculated Top Gap")
        else:
            self.gap_result_label.setText("Calc Bot Gap")
        self.calculate_vertical_gaps()

    def calculate_vertical_gaps(self):
        mod_h = self.mod_h.value()
        bt = self.bottom_t.value()
        tt = self.top_t.value()
        cell_h = self.cell_h.value()
        inner_h = mod_h - bt - tt
        
        available_clearance = inner_h - cell_h
        input_val = self.gap_input.value()
        result_val = available_clearance - input_val
        
        # UI Update
        if result_val < 0:
            self.gap_result_val.setText("ERROR")
            self.gap_result_val.setStyleSheet("background-color: #FFE3E3; color: red; font-weight: bold; border: 1px solid red;")
            self.v_error_label.setText("⚠ ERROR: Cell exceeds module height!")
        else:
            self.gap_result_val.setText(f"{result_val:.1f}")
            self.gap_result_val.setStyleSheet("background-color: #E9ECEF; color: #212529; font-weight: bold;")
            self.v_error_label.setText("")
        
        self.update_module_view()

    def toggle_projection(self, checked):
        """원근감(Perspective)과 평행 투영(Parallel Projection/Ortho) 모드를 토글합니다."""
        if checked:
            self.module_plotter.enable_parallel_projection()
            self.pack_plotter.enable_parallel_projection()
            self.btn_ortho.setText("Parallel Projection (ON)")
            self.btn_ortho.setStyleSheet("background-color: #007AFF; color: white;")
        else:
            self.module_plotter.disable_parallel_projection()
            self.pack_plotter.disable_parallel_projection()
            self.btn_ortho.setText("Parallel Projection (OFF)")
            self.btn_ortho.setStyleSheet("")
        
        # 즉시 반영을 위한 렌더링 호출
        self.module_plotter.render()
        self.pack_plotter.render()

    def set_view_preset(self):
        """선택한 뷰 방향(XY, YZ, XZ, ISO)으로 양쪽 뷰어의 카메라를 설정합니다."""
        sender = self.sender()
        if not sender: return
        
        view_text = sender.text()
        
        for plotter in [self.module_plotter, self.pack_plotter]:
            if "Top" in view_text:
                plotter.view_xy()
            elif "Side" in view_text:
                plotter.view_yz()
            elif "Front" in view_text:
                plotter.view_xz()
            elif "ISO" in view_text:
                plotter.view_isometric()
            plotter.render()

    def get_current_gaps(self):
        """현재 설정된 bottom/top gap 값을 (bottom, top) 튜플로 반환"""
        is_bottom = "Bottom" in self.gap_mode_combo.currentText()
        input_val = self.gap_input.value()
        try:
            res_val = float(self.gap_result_val.text())
        except ValueError:
            res_val = 0.0 # Error state
            
        if is_bottom:
            return input_val, res_val
        else:
            return res_val, input_val

    def on_preset_changed(self, text):
        if "18650" in text: self.cell_l.setValue(18); self.cell_h.setValue(65)
        elif "21700" in text: self.cell_l.setValue(21); self.cell_h.setValue(70)
        elif "4680" in text: self.cell_l.setValue(46); self.cell_h.setValue(80)

    def update_all_cell_icons(self):
        """셀 타입 버튼들의 아이콘을 생성/업데이트합니다."""
        for btn in self.cell_type_group.buttons():
            full_name = btn.property("cell_type_full")
            btn.setIcon(self.create_cell_type_icon(full_name))
            btn.setIconSize(QSize(40, 35))

    def create_cell_type_icon(self, name):
        """셀 타입(원통/각/파우치)을 도식화한 아이콘을 생성합니다."""
        pixmap = QPixmap(100, 80)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.setBrush(QColor("#007AFF" if "Cylindrical" in name else "#495057"))
        painter.setPen(QPen(Qt.white, 1))
        
        if "Cylindrical" in name:
            # 원통형 도식
            painter.drawEllipse(35, 10, 30, 20)
            painter.drawRect(35, 20, 30, 40)
            painter.drawEllipse(35, 50, 30, 20)
        elif "Prismatic" in name:
            # 각형 도식
            painter.drawRect(25, 20, 50, 40)
            painter.setBrush(QColor("#DEE2E6"))
            painter.drawRect(35, 15, 10, 5) # 단자
            painter.drawRect(55, 15, 10, 5)
        else: # Pouch
            # 파우치 도식
            painter.drawRoundedRect(20, 25, 60, 35, 5, 5)
            painter.setBrush(QColor("#ADB5BD"))
            painter.drawRect(30, 18, 12, 10) # 탭
            painter.drawRect(58, 18, 12, 10)
            
        painter.end()
        return QIcon(pixmap)

    def on_layout_button_clicked(self):
        """패턴이나 정렬 버튼 클릭 시 즉시 최적화를 수행하고 뷰를 Top View(XY)로 전환합니다."""
        self.optimize_module()  # 즉시 재계산 및 배치
        # 뷰 전환은 optimize_module 내부에서 처리하거나 필요 시 여기서 추가 호출
        self.module_plotter.view_xy()
        self.module_plotter.render()

    def update_module_view(self):
        """왼쪽 뷰어 업데이트: 단일 셀 프리뷰 또는 최적화된 결과 유지"""
        # --- 심화 기능: Even 정렬 시 Gap 자동 계산 및 UI 제어 ---
        ax = self.align_x_group.checkedButton().property("align_val")
        ay = self.align_y_group.checkedButton().property("align_val")
        is_even = (ax == "Even" or ay == "Even")
        
        if is_even:
            # 원본 수동 입력값을 보관 (처음 진입 시만)
            if self.cell_gap.isEnabled():
                self.last_manual_gap = self.cell_gap.value()
                self.cell_gap.setEnabled(False)
                # 회색 배경으로 비활성화 느낌 강조
                self.cell_gap.setStyleSheet("background-color: #E9ECEF; color: #6C757D; font-weight: bold;")
            
            # 계산을 위해 현재 패턴 및 셀 개수 파악
            selected_btn = self.pattern_group.checkedButton()
            pattern_name = selected_btn.property("pattern_name") if selected_btn else "Grid (정사각형)"
            
            # Optimizer를 호출하여 'Even' 정렬이 적용된 최종 좌표를 가져옴
            cell_type = self.get_current_cell_type()
            cl = self.cell_l.value()
            cw = self.cell_w.value()
            
            positions = self.module_engine.pack_cells_in_module(
                self.mod_l.value(), self.mod_w.value(), self.wall_t.value(),
                cell_type, cl, cw, self.last_manual_gap,
                wall_gap=self.wall_gap.value(),
                pattern=pattern_name,
                align_x=ax, align_y=ay
            )
            
            # 실제 배치된 좌표들 사이의 간격(Gap)을 역산
            calc_gap = self.last_manual_gap
            if positions and len(positions) > 1:
                xs = sorted(list(set(p[0] for p in positions)))
                ys = sorted(list(set(p[1] for p in positions)))
                
                # 원통형인지 판단
                size_x = cl
                size_y = cl if "Cylindrical" in cell_type else cw
                
                # Even인 방향의 갭을 우선적으로 보여줌
                if ax == "Even" and len(xs) > 1:
                    calc_gap = (xs[1] - xs[0]) - size_x
                elif ay == "Even" and len(ys) > 1:
                    calc_gap = (ys[1] - ys[0]) - size_y
            
            # UI 값 업데이트 (시그널 차단하여 재귀 방지)
            self.cell_gap.blockSignals(True)
            self.cell_gap.setValue(round(calc_gap, 1))
            self.cell_gap.blockSignals(False)
        else:
            # 수동 모드로 복귀
            if not self.cell_gap.isEnabled():
                self.cell_gap.setEnabled(True)
                self.cell_gap.setStyleSheet("")
                self.cell_gap.blockSignals(True)
                self.cell_gap.setValue(self.last_manual_gap)
                self.cell_gap.blockSignals(False)

        self.update_all_pattern_counts()
        self.module_plotter.clear()
        
        op = self.mod_opacity.value() / 100.0
        
        # 최적화 결과가 이미 있다면 해당 결과를 새 투명도로 다시 그림
        if self.optimized_module_data:
            self.add_shape_to_viewer(self.module_plotter, self.optimized_module_data["housing"], "#495057", op, line_color="black")
            self.add_shape_to_viewer(self.module_plotter, self.optimized_module_data["cells"], "#007AFF", 1.0)
            self.finalize_viewer(self.module_plotter)
            return
            
        # 결과가 없을 때만 프리뷰(단일 셀 + 하우징)를 그림
        cell_type = self.get_current_cell_type()
        l, w, h = self.cell_l.value(), self.cell_w.value(), self.cell_h.value()
        
        # 1. 단일 셀 프리뷰
        cell_shape = self.module_engine.create_cell(cell_type, l, w, h)
        
        # 2. 모듈 하우징 파라미터 가져오기
        mod_l, mod_w, mod_h = self.mod_l.value(), self.mod_w.value(), self.mod_h.value()
        wt, bt, tt = self.wall_t.value(), self.bottom_t.value(), self.top_t.value()
        
        # Z축 정렬 반영 프리뷰 (바닥 갭 적용)
        bg, tg = self.get_current_gaps()
        
        # 하우징 내 바닥 기준 위치 계산
        z_pos = bt + bg
        # 프리뷰 시 셀을 모듈 중심(L/2, W/2)에 위치시킴
        cell_shape = cell_shape.translate((mod_l/2, mod_w/2, z_pos))
        
        self.add_shape_to_viewer(self.module_plotter, cell_shape, "#007AFF", 1.0, line_color="black")
        
        # 2. 모듈 하우징 프리뷰 (반투명)
        op = self.mod_opacity.value() / 100.0
        module_housing = self.module_engine.create_module_housing(mod_l, mod_w, mod_h, wt, bt, tt)
        self.add_shape_to_viewer(self.module_plotter, module_housing, "#495057", op, line_color="black")
        
        self.finalize_viewer(self.module_plotter)

    def optimize_module(self):
        """Step 1 실행: 모듈 내부 셀 채우기 완료"""
        if "ERROR" in self.gap_result_val.text():
            QMessageBox.warning(self, "Placement Error", "Please resolve vertical gap errors first.")
            return

        bg, tg = self.get_current_gaps()
        cell_type_text = self.get_current_cell_type()
        
        cell_spec = {
            'type': cell_type_text, 
            'l': self.cell_l.value(), 
            'w': self.cell_w.value(), 
            'h': self.cell_h.value()
        }
        
        selected_btn = self.pattern_group.checkedButton()
        pattern_name = selected_btn.property("pattern_name") if selected_btn else "Grid (정사각형)"
        
        cell_positions = self.module_engine.pack_cells_in_module(
            self.mod_l.value(), self.mod_w.value(), self.wall_t.value(),
            cell_type_text, self.cell_l.value(), self.cell_w.value(), self.cell_gap.value(),
            wall_gap=self.wall_gap.value(),
            pattern=pattern_name,
            align_x=self.align_x_group.checkedButton().property("align_val"),
            align_y=self.align_y_group.checkedButton().property("align_val")
        )
        
        self.optimized_module_data = self.module_engine.create_module_assembly(
            self.mod_l.value(), self.mod_w.value(), self.mod_h.value(),
            self.wall_t.value(), self.bottom_t.value(), self.top_t.value(),
            cell_positions, cell_spec,
            vertical_offset=bg
        )
        
        # 결과 업데이트 (왼쪽 뷰어)
        self.module_plotter.clear()
        op = self.mod_opacity.value() / 100.0
        self.add_shape_to_viewer(self.module_plotter, self.optimized_module_data["housing"], "#495057", op, line_color="black")
        self.add_shape_to_viewer(self.module_plotter, self.optimized_module_data["cells"], "#007AFF", 1.0)
        self.module_plotter.reset_camera()
        
        self.btn_opt_pack.setEnabled(True)
        # 결과 수량을 Alignment 섹션 제목에 표시
        self.align_label.setText(f"Batch Alignment (X / Y) - 현재 {len(cell_positions)} Cell")
        # QMessageBox.information(self, "Step 1 Complete", f"Optimized {len(cell_positions)} cells into the module.")

    def load_step_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Pack STEP", "", "STEP Files (*.step *.stp)")
        if file_path:
            self.process_loaded_pack(file_path)

    def process_loaded_pack(self, file_path):
        """불러온 STEP 파일의 정보를 처리하고 뷰어를 업데이트합니다."""
        self.pack_file_label.setText(os.path.basename(file_path))
        self.pack_info = self.pack_engine.load_step(file_path)
        self.update_pack_view()

    def update_pack_view(self):
        """오른쪽 뷰어 업데이트: 팩 하우징 또는 최적화된 결과 유지"""
        if not self.pack_info: return
        self.pack_plotter.clear()
        
        pack_op = self.pack_opacity.value() / 100.0
        mod_op = self.mod_opacity.value() / 100.0
        
        # 최적화 결과가 있다면 결과물 그림
        if self.final_result:
            self.add_shape_to_viewer(self.pack_plotter, self.final_result["pack"], "#ADB5BD", pack_op, line_color="black")
            self.add_shape_to_viewer(self.pack_plotter, self.final_result["modules"], "#495057", mod_op, line_color="black")
            self.add_shape_to_viewer(self.pack_plotter, self.final_result["cells"], "#28A745", 1.0)
        else:
            # 결과가 없을 때 프리뷰 그림
            self.add_shape_to_viewer(self.pack_plotter, self.pack_engine.pack_housing, "#ADB5BD", pack_op, line_color="black")
            
        # 내부 용적 가이드 항상 표시
        self._draw_inner_cavity()
        self.finalize_viewer(self.pack_plotter)

    def _draw_inner_cavity(self):
        """Optimizer가 사용하는 것과 동일한 직사각형 내부 공간을 시각화합니다.
        모듈이 배치되는 실제 영역과 정확히 일치하도록 단순 박스로 표현합니다.
        """
        if not self.pack_info: return
        
        wt = self.pack_wall_t.value()
        bt = self.pack_bottom_t.value()
        
        if wt <= 0 and bt <= 0: return
        
        import cadquery as cq
        inner_l = max(1, self.pack_info['l'] - 2 * wt)
        inner_w = max(1, self.pack_info['w'] - 2 * wt)
        inner_h = max(1, self.pack_info['h'] - bt)
        
        # 팩 벽 안쪽의 직사각형 영역 (Optimizer가 사용하는 것과 동일)
        inner_box = cq.Workplane("XY").box(inner_l, inner_w, inner_h).translate(
            (self.pack_info['l'] / 2, self.pack_info['w'] / 2, bt + inner_h / 2)
        )
        self.add_shape_to_viewer(self.pack_plotter, inner_box, "#87CEFA", 0.15, line_color="#FF0000")

    def optimize_pack(self):
        """Step 2 실행: 팩 내부 모듈 채우기"""
        if not self.pack_info or not self.optimized_module_data: return
        
        offset = (self.off_x.value(), self.off_y.value(), self.off_z.value())
        wt = self.pack_wall_t.value()
        bt = self.pack_bottom_t.value()
        
        # 내부 가용 영역 계산 (바깥 치수 - 2 * 벽두께)
        inner_l = max(0, self.pack_info['l'] - 2 * wt)
        inner_w = max(0, self.pack_info['w'] - 2 * wt)
        
        # 모듈 회전 적용
        place_mod_l = self.mod_w.value() if self.pack_module_rotated else self.mod_l.value()
        place_mod_w = self.mod_l.value() if self.pack_module_rotated else self.mod_w.value()
        
        # 정렬 값 가져오기
        pack_ax = self.pack_align_x_group.checkedButton()
        pack_ay = self.pack_align_y_group.checkedButton()
        align_x = pack_ax.property("align_val") if pack_ax else "Center"
        align_y = pack_ay.property("align_val") if pack_ay else "Center"
        
        module_positions = self.pack_engine.pack_modules_in_pack(
            inner_l, inner_w, 
            place_mod_l, place_mod_w, self.mod_clearance.value(),
            align_x=align_x, align_y=align_y
        )
        
        self.final_result = self.pack_engine.create_full_pack(
            self.optimized_module_data, 
            module_positions, 
            offset=offset, 
            wall_thickness=wt,
            bottom_thickness=bt,
            module_rotated=self.pack_module_rotated,
            pack_dims=(self.pack_info['l'], self.pack_info['w'], self.pack_info['h'])
        )
        
        # 결과 시각화 (오른쪽 뷰어)
        self.pack_plotter.clear()
        pack_op = self.pack_opacity.value() / 100.0
        mod_op = self.mod_opacity.value() / 100.0
        self.add_shape_to_viewer(self.pack_plotter, self.final_result["pack"], "#ADB5BD", pack_op, line_color="black")
        self.add_shape_to_viewer(self.pack_plotter, self.final_result["modules"], "#495057", mod_op, line_color="black")
        self.add_shape_to_viewer(self.pack_plotter, self.final_result["cells"], "#28A745", 1.0)
        
        # 내부 용적 가이드 항상 표시
        self._draw_inner_cavity()
        self.finalize_viewer(self.pack_plotter)
        
        self.pack_plotter.reset_camera()
        self.export_btn.setEnabled(True)

    def rotate_pack_module(self):
        """팩 내 모듈 배치 방향을 90도 회전 토글합니다."""
        self.pack_module_rotated = not self.pack_module_rotated
        if self.pack_module_rotated:
            self.btn_rotate_module.setText("Rotate Module 90° (ON)")
            self.btn_rotate_module.setStyleSheet("background-color: #007AFF; color: white;")
        else:
            self.btn_rotate_module.setText("Rotate Module 90°")
            self.btn_rotate_module.setStyleSheet("")
        
        # 최적화 결과가 있으면 즉시 재배치
        if self.final_result:
            self.optimize_pack()

    def analyze_inner_volume(self):
        """전문 엔진을 사용하여 내부 공간(볼륨)만 분석합니다. 메시 생성 없이 빠르게 수행."""
        if not self.pack_info:
            QMessageBox.warning(self, "Warning", "Please load a Pack STEP file first.")
            return
            
        try:
            wt = self.pack_wall_t.value()
            result = self.pack_engine.mesh_engine.apply_thickness(wt)
            
            # mm³ → m³ 변환 (÷ 1e9)
            inner_m3 = result['inner_volume_mm3'] / 1e9
            wall_m3 = result['wall_volume_mm3'] / 1e9
            
            self.mesh_stats_label.setText(
                f"Inner: {inner_m3:,.6f} m³ | "
                f"Wall: {wall_m3:,.6f} m³ | "
                f"{result['utilization_pct']}%"
            )
            self.btn_gen_mesh.setEnabled(True)
                
            QMessageBox.information(self, "Analysis Complete", 
                                f"Inner Volume: {inner_m3:,.6f} m³\n"
                                f"Wall Volume: {wall_m3:,.6f} m³\n"
                                f"Utilization: {result['utilization_pct']}%")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Analysis failed: {str(e)}")

    def generate_tetra_mesh(self):
        """내부 공간에 대해 테트라헤드럴 메시를 생성합니다."""
        try:
            self.btn_gen_mesh.setText("Generating...")
            self.btn_gen_mesh.setEnabled(False)
            QApplication.processEvents()
            
            stats = self.pack_engine.mesh_engine.generate_volume_mesh()
            
            self.mesh_stats_label.setText(f"Nodes: {stats['n_nodes']:,} | Elements: {stats['n_elements']:,}")
            
            # 메시 시각화
            if self.pack_engine.mesh_engine.volume_mesh:
                surface = self.pack_engine.mesh_engine.volume_mesh.extract_surface()
                self.pack_plotter.add_mesh(surface, color="#28A745", opacity=0.8, 
                                          show_edges=True, edge_color="#1B5E20", 
                                          name="tetra_mesh", label="Tetra Mesh")
                self.pack_plotter.render()
                
            QMessageBox.information(self, "Meshing Complete", 
                                f"Generated {stats['n_elements']:,} tetrahedral elements.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Meshing failed: {str(e)}")
        finally:
            self.btn_gen_mesh.setText("Generate Tetra Mesh")
            self.btn_gen_mesh.setEnabled(True)

    def add_shape_to_viewer(self, plotter, shape, color, opacity, line_color="#495057"):
        """형상을 뷰어에 추가합니다. 실제 그리드 그리기는 finalize_viewer에서 처리합니다."""
        if not shape: return
        mesh_file = self.pack_engine.get_mesh_file(shape)
        if mesh_file and os.path.exists(mesh_file):
            mesh = pv.read(mesh_file)
            plotter.add_mesh(mesh, color=color, opacity=opacity, show_edges=True, edge_color=line_color, line_width=2)

    def finalize_viewer(self, plotter):
        """뷰어의 그리드, 좌표축 및 카메라를 최종 정리합니다."""
        # 100mm 단위 그리드 및 치수 표기 추가
        bounds = plotter.bounds # [xmin, xmax, ymin, ymax, zmin, zmax]
        
        # 바운즈가 유효한지 체크하여 레이블 개수 계산
        if bounds and not any(math.isinf(b) for b in bounds) and (bounds[1] > bounds[0]):
            n_x = max(2, int((bounds[1] - bounds[0]) / 100) + 1)
            n_y = max(2, int((bounds[3] - bounds[2]) / 100) + 1)
            n_z = max(2, int((bounds[5] - bounds[4]) / 100) + 1)
        else:
            n_x, n_y, n_z = 5, 5, 5

        try:
            plotter.show_grid(
                color='black',
                grid=True,
                location='outer',
                ticks='both',
                font_size=10,
                font_family='arial',
                use_3d_text=False,
                xtitle='X [mm]', ytitle='Y [mm]', ztitle='Z [mm]',
                n_xlabels=n_x,
                n_ylabels=n_y,
                n_zlabels=n_z,
                fmt='%.0f'
            )
        except Exception:
            pass  # 바운즈가 없으면 그리드 생략
        
        # 기본 좌표축 표시 (오른쪽 하단)
        try:
            plotter.add_axes(label_size=(0.05, 0.05), color='black')
        except Exception:
            pass
        plotter.reset_camera()

    def export_result(self):
        if not self.final_result: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export STEP", "EcoPack_Full_Assembly.step", "STEP (*.step)")
        if file_path:
            self.pack_engine.export_to_step(self.final_result, file_path)
            QMessageBox.information(self, "Export Success", "Assembly saved successfully!")

    def closeEvent(self, event):
        self.module_plotter.close()
        self.pack_plotter.close()
        event.accept()

if __name__ == "__main__":
    # CadQuery 모듈에 접근하기 위해 cad_engine의 cq를 노출시킬 필요가 있음
    # cad_engine.py에 self.cq = cq 추가 필요 (이미 CADEngine에서 import cadquery as cq 되어있음)
    app = QApplication(sys.argv)
    window = EcoPackApp()
    window.show()
    sys.exit(app.exec())
