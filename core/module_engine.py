import cadquery as cq
import math


class ModuleEngine:
    """모듈 구성 엔진: 셀 생성, 모듈 하우징 생성, 셀 배치를 담당합니다.
    팩 엔진과 독립적으로 동작합니다.
    """

    def __init__(self):
        self.cq = cq

    # ─── Cell ───────────────────────────────────────────────

    def create_cell(self, cell_type, l, w, h):
        """개별 셀 형상을 생성합니다."""
        if "Cylindrical" in cell_type:
            # l은 지름(Diameter), h는 높이
            return cq.Workplane("XY").circle(l/2).extrude(h)
        else:
            # 角形(Prismatic) 및 Pouch도 바닥이 Z=0에서 시작하게 함
            return cq.Workplane("XY").rect(l, w).extrude(h)

    # ─── Module Housing ─────────────────────────────────────

    def create_module_housing(self, mod_l, mod_w, mod_h, wall_t, bottom_t, top_t):
        """벽면, 바닥, 상단 두께가 각각 적용된 하우징 형상을 생성합니다. (0,0,0에서 시작)"""
        # (0,0,0) 코너 정렬을 위해 중심에서 L/2, W/2, H/2만큼 이동
        outer_box = cq.Workplane("XY").box(mod_l, mod_w, mod_h).translate((mod_l/2, mod_w/2, mod_h/2))
        
        inner_l = mod_l - 2*wall_t
        inner_w = mod_w - 2*wall_t
        inner_h = mod_h - bottom_t - top_t
        
        # 내부 공간 배치: 하우징 바닥으로부터 bottom_t 오프셋
        inner_z_center = bottom_t + inner_h / 2.0
        inner_box = cq.Workplane("XY").box(inner_l, inner_w, inner_h).translate((mod_l/2, mod_w/2, inner_z_center))
        
        return outer_box.cut(inner_box)

    # ─── Module Assembly ────────────────────────────────────

    def create_module_assembly(self, mod_l, mod_w, mod_h, wall_t, bottom_t, top_t, cells_positions, cell_spec, vertical_offset=0):
        """셀이 배치된 모듈 조립체를 생성하며, 개선된 바닥면 기준 정렬을 적용합니다."""
        module_housing = self.create_module_housing(mod_l, mod_w, mod_h, wall_t, bottom_t, top_t)
        
        cell_val_list = []
        # 하우징 내 바닥면 위치: housing bottom(0) + bottom_t
        base_z_bottom = bottom_t + vertical_offset
        
        for pos in cells_positions:
            cell = self.create_cell(cell_spec['type'], cell_spec['l'], cell_spec['w'], cell_spec['h'])
            # Optimizer는 (0,0) 중심 좌표를 주므로, 모듈 중심(L/2, W/2)을 더해줌
            final_x = pos[0] + mod_l / 2.0
            final_y = pos[1] + mod_w / 2.0
            cell = cell.translate((final_x, final_y, base_z_bottom))
            cell_val_list.append(cell.val())
            
        cells_compound = cq.Compound.makeCompound(cell_val_list)
        
        return {
            "housing": module_housing,
            "cells": cells_compound
        }

    # ─── Cell Packing Optimizer ─────────────────────────────

    @staticmethod
    def pack_cells_in_module(mod_l, mod_w, mod_thickness, cell_type, cell_l, cell_w, cell_gap, wall_gap=0, pattern="Grid (정사각형)", align_x="Center", align_y="Center"):
        """모듈 내부에 셀을 여러 패턴으로 배치할 수 있는 좌표 리스트를 반환합니다."""
        # 실제 셀이 배치될 수 있는 내부 가용 영역 계산 (벽 두께 + 사용자 지정 Wall Gap)
        inner_l = mod_l - 2 * mod_thickness - 2 * wall_gap
        inner_w = mod_w - 2 * mod_thickness - 2 * wall_gap
        
        positions = []
        
        if "Cylindrical" in cell_type:
            dia = cell_l + cell_gap
            radius = dia / 2
            
            if "Hexagonal-H" in pattern:
                dx = dia
                dy = dia * math.sqrt(3) / 2
                rows = int((inner_w - dia) / dy) + 1 if inner_w >= dia else 0
                for r in range(rows):
                    y_pos = -inner_w/2 + radius + r * dy
                    off_x = (dia / 2) if r % 2 != 0 else 0
                    cols = int((inner_l - dia - off_x) / dx) + 1 if inner_l >= (dia + off_x) else 0
                    for c in range(cols):
                        x_pos = -inner_l/2 + radius + off_x + c * dx
                        positions.append((x_pos, y_pos))
                        
            elif "Hexagonal-V" in pattern:
                dy = dia
                dx = dia * math.sqrt(3) / 2
                cols = int((inner_l - dia) / dx) + 1 if inner_l >= dia else 0
                for c in range(cols):
                    x_pos = -inner_l/2 + radius + c * dx
                    off_y = (dia / 2) if c % 2 != 0 else 0
                    rows = int((inner_w - dia - off_y) / dy) + 1 if inner_w >= (dia + off_y) else 0
                    for r in range(rows):
                        y_pos = -inner_w/2 + radius + off_y + r * dy
                        positions.append((x_pos, y_pos))

            elif "Diagonal" in pattern:
                dx = dia
                dy = dia
                rows = int((inner_w - dia) / dy) + 1 if inner_w >= dia else 0
                for r in range(rows):
                    y_pos = -inner_w/2 + radius + r * dy
                    off_x = (dia / 2) if r % 2 != 0 else 0
                    cols = int((inner_l - dia - off_x) / dx) + 1 if inner_l >= (dia + off_x) else 0
                    for c in range(cols):
                        x_pos = -inner_l/2 + radius + off_x + c * dx
                        positions.append((x_pos, y_pos))

            elif "Staggered" in pattern:
                dx = dia
                dy = dia * 0.9
                rows = int((inner_w - dia) / dy) + 1 if inner_w >= dia else 0
                for r in range(rows):
                    y_pos = -inner_w/2 + radius + r * dy
                    off_x = (dia * (r % 3) / 3)
                    cols = int((inner_l - dia - off_x) / dx) + 1 if inner_l >= (dia + off_x) else 0
                    for c in range(cols):
                        x_pos = -inner_l/2 + radius + off_x + c * dx
                        positions.append((x_pos, y_pos))
            
            else: # Grid (정사각형)
                cols = int(inner_l / dia)
                rows = int(inner_w / dia)
                start_x = -(cols * dia - cell_gap) / 2 + cell_l / 2
                start_y = -(rows * dia - cell_gap) / 2 + cell_l / 2
                for r in range(rows):
                    for c in range(cols):
                        positions.append((start_x + c * dia, start_y + r * dia))
                        
        else: # Prismatic or Pouch
            pitch_l = cell_l + cell_gap
            pitch_w = cell_w + cell_gap
            cols = int(inner_l / pitch_l)
            rows = int(inner_w / pitch_w)
            if cols > 0 and rows > 0:
                start_x = -(cols * pitch_l - cell_gap) / 2 + cell_l / 2
                start_y = -(rows * pitch_w - cell_gap) / 2 + cell_w / 2
                for r in range(rows):
                    for c in range(cols):
                        positions.append((start_x + c * pitch_l, start_y + r * pitch_w))
                    
        if not positions:
            return []

        # 정렬 처리 (X: Start/Center/End, Y: Start/Center/End)
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        cl = cell_l if "Cylindrical" in cell_type else cell_l
        cw = cell_l if "Cylindrical" in cell_type else cell_w
        
        # X축 정렬
        shift_x = 0
        if align_x == "Even":
            unique_xs = sorted(list(set(xs)))
            if len(unique_xs) > 1:
                new_start_x = -inner_l/2 + cl/2
                new_end_x = inner_l/2 - cl/2
                pitch_x = (new_end_x - new_start_x) / (len(unique_xs) - 1)
                mapping_x = {old: new_start_x + i * pitch_x for i, old in enumerate(unique_xs)}
                positions = [(mapping_x[p[0]], p[1]) for p in positions]
            else:
                shift_x = -min_x
        elif align_x == "Start":
            shift_x = -inner_l/2 + cl/2 - min_x
        elif align_x == "End":
            shift_x = inner_l/2 - cl/2 - max_x
            
        if shift_x != 0:
            positions = [(p[0] + shift_x, p[1]) for p in positions]

        # Y축 정렬
        shift_y = 0
        if align_y == "Even":
            unique_ys = sorted(list(set(p[1] for p in positions)))
            if len(unique_ys) > 1:
                new_start_y = -inner_w/2 + cw/2
                new_end_y = inner_w/2 - cw/2
                pitch_y = (new_end_y - new_start_y) / (len(unique_ys) - 1)
                mapping_y = {old: new_start_y + i * pitch_y for i, old in enumerate(unique_ys)}
                positions = [(p[0], mapping_y[p[1]]) for p in positions]
            else:
                shift_y = -(min(p[1] for p in positions))
        elif align_y == "Start":
            shift_y = -inner_w/2 + cw/2 - (min(p[1] for p in positions))
        elif align_y == "End":
            shift_y = inner_w/2 - cw/2 - (max(p[1] for p in positions))
            
        if shift_y != 0:
            positions = [(p[0], p[1] + shift_y) for p in positions]
            
        return positions
