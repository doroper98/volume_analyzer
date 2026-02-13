import math

class Optimizer:
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
                # 가로 지그재그 (60도)
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
                # 세로 지그재그 (60도)
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
                # 45도 대각 엇갈림 (간격은 dia 유지, 행간격도 dia)
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
                # 1/3 오프셋 엇갈림
                dx = dia
                dy = dia * 0.9 # 약간 더 조밀하게
                rows = int((inner_w - dia) / dy) + 1 if inner_w >= dia else 0
                for r in range(rows):
                    y_pos = -inner_w/2 + radius + r * dy
                    off_x = (dia * (r % 3) / 3) # 3행 주기로 엇갈림
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
                # 첫 열과 끝 열 사이를 균등 분할
                new_start_x = -inner_l/2 + cl/2
                new_end_x = inner_l/2 - cl/2
                pitch_x = (new_end_x - new_start_x) / (len(unique_xs) - 1)
                mapping_x = {old: new_start_x + i * pitch_x for i, old in enumerate(unique_xs)}
                positions = [(mapping_x[p[0]], p[1]) for p in positions]
            else:
                shift_x = -min_x # 중앙 정렬과 유사
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

    @staticmethod
    def pack_modules_in_pack(pack_l, pack_w, mod_l, mod_w, clearance):
        """팩 내부에 모듈을 배치할 좌표 리스트를 반환합니다."""
        pitch_l = mod_l + clearance
        pitch_w = mod_w + clearance
        
        cols = int(pack_l / pitch_l)
        rows = int(pack_w / pitch_w)
        
        positions = []
        if cols > 0 and rows > 0:
            start_x = -(cols * pitch_l - clearance) / 2 + mod_l / 2
            start_y = -(rows * pitch_w - clearance) / 2 + mod_w / 2
            
            for r in range(rows):
                for c in range(cols):
                    positions.append((start_x + c * pitch_l, start_y + r * pitch_w))
        
        return positions
