import sys
import os

# PySide6를 사용하도록 설정
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QFrame, QSplitter, QGroupBox, 
                             QFormLayout, QDoubleSpinBox, QComboBox, QScrollArea, QMessageBox,
                             QRadioButton, QButtonGroup, QLineEdit, QGridLayout)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap, QPen, QBrush

import pyvista as pv
from pyvistaqt import QtInteractor

from core.cad_engine import CADEngine
from core.optimizer import Optimizer

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
        
        self.cad = CADEngine()
        self.opt = Optimizer()
        
        # State
        self.pack_info = None
        self.optimized_module_data = None
        self.final_result = None
        
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
        
        l_scroll = QScrollArea()
        l_scroll.setWidgetResizable(True)
        l_scroll_content = QWidget()
        l_content_layout = QVBoxLayout(l_scroll_content)
        
        # Cell Section
        cell_group = QGroupBox("CELL SPECIFICATIONS")
        self.cell_form = QFormLayout(cell_group)
        self.cell_type = QComboBox()
        self.cell_type.addItems(["Cylindrical (원통형)", "Prismatic (각형)", "Pouch (파우치)"])
        self.cell_type.currentTextChanged.connect(self.on_cell_type_changed)
        self.cell_form.addRow("Type", self.cell_type)
        
        self.std_preset = QComboBox()
        self.std_preset.addItems(["Custom", "18650 (D18 H65)", "21700 (D21 H70)", "4680 (D46 H80)"])
        self.std_preset.currentTextChanged.connect(self.on_preset_changed)
        self.cell_form.addRow("Std Size", self.std_preset)
        
        self.cell_l_label = QLabel("Diameter (mm)")
        self.cell_l = self.create_spinbox(None, "", 18)
        self.cell_l.valueChanged.connect(self.update_module_view)
        self.cell_form.addRow(self.cell_l_label, self.cell_l)
        
        self.cell_w_label = QLabel("Width (mm)")
        self.cell_w = self.create_spinbox(None, "", 27)
        self.cell_w.valueChanged.connect(self.update_module_view)
        self.cell_w_row = self.cell_form.addRow(self.cell_w_label, self.cell_w)
        
        self.cell_h = self.create_spinbox(self.cell_form, "Height (mm)", 65)
        self.cell_h.valueChanged.connect(self.update_module_view)
        
        # Pattern Button Group
        self.pattern_label = QLabel("Array Pattern Selection")
        self.pattern_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.cell_form.addRow(self.pattern_label)
        
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
            btn.setFixedSize(60, 60)
            btn.setToolTip(full_name)
            btn.setIcon(self.create_pattern_icon(full_name))
            btn.setIconSize(QSize(45, 45))
            btn.setProperty("pattern_name", full_name)
            btn.clicked.connect(self.update_module_view)
            
            count_label = QLabel("0 EA")
            count_label.setObjectName("CountLabel")
            count_label.setAlignment(Qt.AlignCenter)
            
            vbox.addWidget(btn)
            vbox.addWidget(count_label)
            
            if i == 0: btn.setChecked(True)
            
            self.pattern_group.addButton(btn)
            self.pattern_btn_layout.addWidget(container, i // 3, i % 3)
            self.pattern_widgets.append((btn, count_label, full_name))
            
        self.cell_form.addRow(self.pattern_btn_layout)
        
        self.cell_gap = self.create_spinbox(self.cell_form, "Cell-Gap (mm)", 2)
        l_content_layout.addWidget(cell_group)
        
        # Module Section
        mod_group = QGroupBox("MODULE HOUSING")
        mod_form = QFormLayout(mod_group)
        self.mod_l = self.create_spinbox(mod_form, "Outer L (mm)", 400)
        self.mod_w = self.create_spinbox(mod_form, "Outer W (mm)", 200)
        self.mod_h = self.create_spinbox(mod_form, "Outer H (mm)", 100)
        self.wall_t = self.create_spinbox(mod_form, "Side Wall T (mm)", 5)
        self.bottom_t = self.create_spinbox(mod_form, "Bottom T (mm)", 5)
        self.top_t = self.create_spinbox(mod_form, "Top T (mm)", 5)
        
        self.mod_l.valueChanged.connect(self.update_module_view)
        self.mod_w.valueChanged.connect(self.update_module_view)
        self.mod_h.valueChanged.connect(self.update_module_view)
        self.wall_t.valueChanged.connect(self.update_module_view)
        self.bottom_t.valueChanged.connect(self.update_module_view)
        self.top_t.valueChanged.connect(self.update_module_view)
        
        # Gap Section (New)
        gap_inner_group = QGroupBox("VERTICAL PLACEMENT")
        self.gap_layout = QFormLayout(gap_inner_group)
        
        # Mode Toggle (Bottom vs Top)
        self.gap_mode_combo = QComboBox()
        self.gap_mode_combo.addItems(["Bottom Gap Input", "Top Gap Input"])
        self.gap_mode_combo.currentTextChanged.connect(self.sync_gap_ui)
        self.gap_layout.addRow("Selection Mode", self.gap_mode_combo)
        
        # Input Spinbox
        self.gap_input = self.create_spinbox(self.gap_layout, "Gap Value (mm)", 2)
        self.gap_input.valueChanged.connect(self.calculate_vertical_gaps)
        
        # Result Display (Read-only)
        self.gap_result_label = QLabel("Calculated Top Gap")
        self.gap_result_val = QLineEdit("0.0")
        self.gap_result_val.setReadOnly(True)
        self.gap_result_val.setStyleSheet("background-color: #E9ECEF; font-weight: bold;")
        self.gap_layout.addRow(self.gap_result_label, self.gap_result_val)
        
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
        l_scroll.setWidget(l_scroll_content)
        left_panel_layout.addWidget(l_scroll)
        
        self.btn_opt_mod = QPushButton("Step 1: Optimize Module")
        self.btn_opt_mod.setObjectName("Primary")
        self.btn_opt_mod.clicked.connect(self.optimize_module)
        left_panel_layout.addWidget(self.btn_opt_mod)
        
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
        
        # 4. 오른쪽 패널 (Pack Housing & Placement)
        right_panel = QFrame()
        right_panel.setFixedWidth(350)
        right_panel.setObjectName("Panel")
        right_panel.setProperty("class", "Panel")
        right_panel_layout = QVBoxLayout(right_panel)
        
        r_header = QLabel("PACK CONFIGURATION")
        r_header.setObjectName("Header")
        right_panel_layout.addWidget(r_header)
        
        r_scroll = QScrollArea()
        r_scroll.setWidgetResizable(True)
        r_scroll_content = QWidget()
        r_content_layout = QVBoxLayout(r_scroll_content)
        
        # Pack Housing Section
        pack_housing_group = QGroupBox("PACK HOUSING")
        ph_layout = QVBoxLayout(pack_housing_group)
        self.btn_load_pack = QPushButton("Load Pack STEP File")
        self.btn_load_pack.clicked.connect(self.load_step_file)
        ph_layout.addWidget(self.btn_load_pack)
        self.pack_file_label = QLabel("No file loaded")
        self.pack_file_label.setStyleSheet("font-size: 11px; color: #6C757D;")
        ph_layout.addWidget(self.pack_file_label)
        r_content_layout.addWidget(pack_housing_group)
        
        # Pack Opt Section
        pack_opt_group = QGroupBox("PACK PLACEMENT")
        p_form = QFormLayout(pack_opt_group)
        self.mod_clearance = self.create_spinbox(p_form, "Mod Gap (mm)", 10)
        self.mod_clearance.valueChanged.connect(self.optimize_pack)
        r_content_layout.addWidget(pack_opt_group)
        
        # Coordinate Adjustment
        move_group = QGroupBox("MANUAL POSITION ADJUST")
        move_form = QFormLayout(move_group)
        self.off_x = self.create_spinbox(move_form, "Offset X (mm)", 0, range=(-2000, 2000))
        self.off_y = self.create_spinbox(move_form, "Offset Y (mm)", 0, range=(-2000, 2000))
        self.off_z = self.create_spinbox(move_form, "Offset Z (mm)", 0, range=(-2000, 2000))
        self.off_x.valueChanged.connect(self.optimize_pack)
        self.off_y.valueChanged.connect(self.optimize_pack)
        self.off_z.valueChanged.connect(self.optimize_pack)
        r_content_layout.addWidget(move_group)
        
        r_content_layout.addStretch()
        r_scroll.setWidget(r_scroll_content)
        right_panel_layout.addWidget(r_scroll)
        
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
        main_layout.addWidget(self.module_viewer_frame, 1)
        main_layout.addWidget(self.pack_viewer_frame, 1)
        main_layout.addWidget(right_panel)
        
        self.setStyleSheet(STYLE_SHEET + self.STYLE_MOD)
        
        # 초기 셀 설정 호출
        self.on_cell_type_changed(self.cell_type.currentText())

    def create_spinbox(self, layout, label, default_val, range=(0, 10000)):
        sb = QDoubleSpinBox()
        sb.setRange(range[0], range[1])
        sb.setDecimals(1)
        sb.setValue(default_val)
        if layout:
            layout.addRow(label, sb)
        return sb

    def on_cell_type_changed(self, text):
        is_cylindrical = "Cylindrical" in text
        self.std_preset.setVisible(is_cylindrical)
        self.cell_form.labelForField(self.std_preset).setVisible(is_cylindrical)
        self.cell_w.setVisible(not is_cylindrical)
        self.cell_form.labelForField(self.cell_w).setVisible(not is_cylindrical)
        
        if is_cylindrical:
            self.cell_l_label.setText("Diameter (mm)")
            self.std_preset.setCurrentText("18650 (D18 H65)")
            self.pattern_label.setVisible(True)
            for widget_data in self.pattern_widgets:
                btn, label, _ = widget_data
                btn.parentWidget().setVisible(True)
        else:
            self.cell_l_label.setText("Length (mm)")
            self.cell_l.setValue(148); self.cell_w.setValue(27); self.cell_h.setValue(91)
            self.pattern_label.setVisible(False)
            for widget_data in self.pattern_widgets:
                btn, label, _ = widget_data
                btn.parentWidget().setVisible(False)
        self.update_module_view()

    def create_pattern_icon(self, name):
        """프로그램적으로 패턴 아이콘을 생성합니다 (QPainter 활용)"""
        pixmap = QPixmap(100, 100)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 배경 원형 가이드 (선택 사항)
        # painter.setBrush(QColor("#F0F0F0"))
        # painter.drawRoundedRect(5, 5, 90, 90, 10, 10)
        
        if "Cylindrical" in self.cell_type.currentText():
            painter.setBrush(QColor("#007AFF"))
        else:
            painter.setBrush(QColor("#495057"))
        painter.setPen(Qt.NoPen)
        
        d = 18
        gap = 5
        start_x, start_y = 20, 20
        
        if "Grid" in name:
            for r in range(3):
                for c in range(3):
                    painter.drawEllipse(start_x + c*(d+gap), start_y + r*(d+gap), d, d)
        elif "Hexagonal-H" in name:
            for r in range(3):
                off = (d+gap)/2 if r % 2 != 0 else 0
                for c in range(3):
                    painter.drawEllipse(start_x + off + c*(d+gap) - 10, start_y + r*(d+gap)*0.85, d, d)
        elif "Hexagonal-V" in name:
            for c in range(3):
                off = (d+gap)/2 if c % 2 != 0 else 0
                for r in range(3):
                    painter.drawEllipse(start_x + c*(d+gap)*0.85, start_y + off + r*(d+gap) - 10, d, d)
        elif "Diagonal" in name:
            for r in range(3):
                off = (d+gap)/2 if r % 2 != 0 else 0
                for c in range(3):
                    painter.drawEllipse(start_x + off + c*(d+gap) - 5, start_y + r*(d+gap), d, d)
        elif "Staggered" in name:
            for r in range(3):
                off = (d+gap) * (r % 3) / 3
                for c in range(3):
                    painter.drawEllipse(start_x + off + c*(d+gap) - 10, start_y + r*(d+gap)*0.9, d, d)
        
        painter.end()
        return QIcon(pixmap)

    def update_all_pattern_counts(self):
        """모든 패턴에 대해 배치 가능한 셀 개수를 실시간으로 계산하여 표시합니다."""
        if "Cylindrical" not in self.cell_type.currentText():
            return
            
        for btn, label, pattern_name in self.pattern_widgets:
            positions = self.opt.pack_cells_in_module(
                self.mod_l.value(), self.mod_w.value(), self.wall_t.value(),
                self.cell_type.currentText(), self.cell_l.value(), self.cell_w.value(), self.cell_gap.value(),
                pattern=pattern_name
            )
            label.setText(f"{len(positions)} EA")

    def sync_gap_ui(self):
        is_bottom = "Bottom" in self.gap_mode_combo.currentText()
        if is_bottom:
            self.gap_result_label.setText("Calculated Top Gap")
        else:
            self.gap_result_label.setText("Calculated Bottom Gap")
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

    def update_module_view(self):
        """왼쪽 뷰어 업데이트: 단일 셀 또는 최적화된 모듈 프리뷰"""
        self.update_all_pattern_counts()
        self.module_plotter.clear()
        
        cell_type = self.cell_type.currentText()
        l, w, h = self.cell_l.value(), self.cell_w.value(), self.cell_h.value()
        
        # 현재 선택된 패턴 가져오기
        selected_btn = self.pattern_group.checkedButton()
        pattern_name = selected_btn.property("pattern_name") if selected_btn else "Grid (정사각형)"
        
        # 1. 단일 셀 프리뷰
        cell_shape = self.cad.create_cell(cell_type, l, w, h)
        
        # Z축 정렬 반영 프리뷰 (바닥 갭 적용)
        bg, tg = self.get_current_gaps()
        mod_h = self.mod_h.value()
        bt = self.bottom_t.value()
        
        # 하우징 내 바닥 기준 위치 계산: 
        # 하우징 중심이 0이므로 실제 내부 바닥면은 -mod_h/2 + bt
        # 셀은 0(바닥)에서 h까지 생성되므로, translate 시 h/2를 더하거나 
        # 원통의 경우 CADEngine에서 처리된 방식에 맞춰 오프셋 적용
        z_pos = -mod_h/2 + bt + bg
        cell_shape = cell_shape.translate((0, 0, z_pos))
        
        self.add_shape_to_viewer(self.module_plotter, cell_shape, "#007AFF", 1.0, line_color="black")
        
        # 2. 모듈 하우징 프리뷰 (반투명)
        mod_l, mod_w, mod_h = self.mod_l.value(), self.mod_w.value(), self.mod_h.value()
        wt, bt, tt = self.wall_t.value(), self.bottom_t.value(), self.top_t.value()
        
        module_housing = self.cad.create_module_housing(mod_l, mod_w, mod_h, wt, bt, tt)
        self.add_shape_to_viewer(self.module_plotter, module_housing, "#495057", 0.1, line_color="#343A40")
        
        self.module_plotter.reset_camera()

    def optimize_module(self):
        """Step 1 실행: 모듈 내부 셀 채우기 완료"""
        if "ERROR" in self.gap_result_val.text():
            QMessageBox.warning(self, "Placement Error", "Please resolve vertical gap errors first.")
            return

        bg, tg = self.get_current_gaps()
        
        cell_spec = {
            'type': self.cell_type.currentText(), 
            'l': self.cell_l.value(), 
            'w': self.cell_w.value(), 
            'h': self.cell_h.value()
        }
        
        selected_btn = self.pattern_group.checkedButton()
        pattern_name = selected_btn.property("pattern_name") if selected_btn else "Grid (정사각형)"
        
        cell_positions = self.opt.pack_cells_in_module(
            self.mod_l.value(), self.mod_w.value(), self.wall_t.value(),
            self.cell_type.currentText(), self.cell_l.value(), self.cell_w.value(), self.cell_gap.value(),
            pattern=pattern_name
        )
        
        self.optimized_module_data = self.cad.create_module_assembly(
            self.mod_l.value(), self.mod_w.value(), self.mod_h.value(),
            self.wall_t.value(), self.bottom_t.value(), self.top_t.value(),
            cell_positions, cell_spec,
            vertical_offset=bg
        )
        
        # 결과 업데이트 (왼쪽 뷰어)
        self.module_plotter.clear()
        self.add_shape_to_viewer(self.module_plotter, self.optimized_module_data["housing"], "#495057", 0.05, line_color="black")
        self.add_shape_to_viewer(self.module_plotter, self.optimized_module_data["cells"], "#007AFF", 1.0)
        self.module_plotter.reset_camera()
        
        self.btn_opt_pack.setEnabled(True)
        QMessageBox.information(self, "Step 1 Complete", f"Optimized {len(cell_positions)} cells into the module.")

    def load_step_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Pack STEP", "", "STEP Files (*.step *.stp)")
        if file_path:
            self.pack_file_label.setText(os.path.basename(file_path))
            self.pack_info = self.cad.load_step(file_path)
            self.update_pack_view()

    def update_pack_view(self):
        """오른쪽 뷰어 업데이트: 팩 하우징 프리뷰"""
        if not self.pack_info: return
        self.pack_plotter.clear()
        self.add_shape_to_viewer(self.pack_plotter, self.cad.pack_housing, "#ADB5BD", 0.05, line_color="black")
        self.pack_plotter.reset_camera()

    def optimize_pack(self):
        """Step 2 실행: 팩 내부 모듈 채우기"""
        if not self.pack_info or not self.optimized_module_data: return
        
        offset = (self.off_x.value(), self.off_y.value(), self.off_z.value())
        module_positions = self.opt.pack_modules_in_pack(
            self.pack_info['l'], self.pack_info['w'], 
            self.mod_l.value(), self.mod_w.value(), self.mod_clearance.value()
        )
        
        self.final_result = self.cad.create_full_pack(self.optimized_module_data, module_positions, offset=offset)
        
        # 결과 시각화 (오른쪽 뷰어)
        self.pack_plotter.clear()
        self.add_shape_to_viewer(self.pack_plotter, self.final_result["pack"], "#ADB5BD", 0.05, line_color="black")
        self.add_shape_to_viewer(self.pack_plotter, self.final_result["modules"], "#495057", 0.05, line_color="black")
        self.add_shape_to_viewer(self.pack_plotter, self.final_result["cells"], "#28A745", 1.0)
        self.pack_plotter.reset_camera()
        self.export_btn.setEnabled(True)

    def add_shape_to_viewer(self, plotter, shape, color, opacity, line_color="#495057"):
        if not shape: return
        mesh_file = self.cad.get_mesh_file(shape)
        if mesh_file and os.path.exists(mesh_file):
            mesh = pv.read(mesh_file)
            plotter.add_mesh(mesh, color=color, opacity=opacity, show_edges=True, edge_color=line_color, line_width=1)
            
            # 100mm 단위 그리드 및 치수 표기 추가
            bounds = mesh.bounds
            plotter.show_grid(
                color='black',
                grid=True,
                location='outer',
                ticks='both',
                font_size=10,
                font_family='arial',
                use_3d_text=False, # 2D 텍스트로 고정 크기 유지
                xtitle='X [mm]', ytitle='Y [mm]', ztitle='Z [mm]',
                n_xlabels=int((bounds[1]-bounds[0])/100) + 1,
                n_ylabels=int((bounds[3]-bounds[2])/100) + 1,
                n_zlabels=int((bounds[5]-bounds[4])/100) + 1,
                fmt='%.0f'
            )
            # 기본 좌표축 표시
            plotter.add_axes(label_size=(0.05, 0.05), color='black')

    def export_result(self):
        if not self.final_result: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export STEP", "EcoPack_Full_Assembly.step", "STEP (*.step)")
        if file_path:
            self.cad.export_to_step(self.final_result, file_path)
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
