import math

class Optimizer:
    @staticmethod
    def pack_cells_in_module(mod_l, mod_w, mod_thickness, cell_type, cell_l, cell_w, cell_gap, pattern="Grid (정사각형)"):
        """모듈 내부에 셀을 여러 패턴으로 배치할 수 있는 좌표 리스트를 반환합니다."""
        inner_l = mod_l - 2 * mod_thickness
        inner_w = mod_w - 2 * mod_thickness
        
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
