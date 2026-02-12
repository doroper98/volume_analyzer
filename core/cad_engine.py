import cadquery as cq
import os

class CADEngine:
    def __init__(self):
        self.cq = cq
        self.pack_housing = None
        self.available_volume = None
        
    def load_step(self, file_path):
        """STEP 파일을 불러오고 내부 볼륨을 분석합니다."""
        print(f"Attempting to load: {file_path}")
        if not os.path.exists(file_path):
            print(f"Error: File does not exist at {file_path}")
            return None
            
        try:
            self.pack_housing = cq.importers.importStep(file_path)
            print("STEP file loaded successfully.")
            
            # Option B: 내부 공간 분석 (단순화된 버전: 바운딩 박스 기반 가이드)
            bb = self.pack_housing.val().BoundingBox()
            print(f"Detected Bounding Box: {bb.xlen}x{bb.ylen}x{bb.zlen}")
            return {
                "l": bb.xlen,
                "w": bb.ylen,
                "h": bb.zlen
            }
        except Exception as e:
            print(f"Error loading STEP: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def create_cell(self, cell_type, l, w, h):
        """개별 셀 형상을 생성합니다."""
        if "Cylindrical" in cell_type:
            # l은 지름(Diameter), h는 높이
            return cq.Workplane("XY").circle(l/2).extrude(h)
        else:
            # 角形(Prismatic) 및 Pouch도 바닥이 Z=0에서 시작하게 함
            return cq.Workplane("XY").rect(l, w).extrude(h)

    def create_module_housing(self, mod_l, mod_w, mod_h, wall_t, bottom_t, top_t):
        """벽면, 바닥, 상단 두께가 각각 적용된 하우징 형상을 생성합니다."""
        outer_box = cq.Workplane("XY").box(mod_l, mod_w, mod_h)
        
        inner_l = mod_l - 2*wall_t
        inner_w = mod_w - 2*wall_t
        inner_h = mod_h - bottom_t - top_t
        
        # 내부 공간 배치: 바닥 두께와 상단 두께 차이만큼 Z 오프셋 필요
        # (bottom_t - top_t) / 2 가 중심점의 오프셋임
        z_offset = (bottom_t - top_t) / 2.0
        inner_box = cq.Workplane("XY").center(0, 0).workplane(offset=z_offset).box(inner_l, inner_w, inner_h)
        
        return outer_box.cut(inner_box)

    def create_module_assembly(self, mod_l, mod_w, mod_h, wall_t, bottom_t, top_t, cells_positions, cell_spec, vertical_offset=0):
        """셀이 배치된 모듈 조립체를 생성하며, 개선된 바닥면 기준 정렬을 적용합니다."""
        module_housing = self.create_module_housing(mod_l, mod_w, mod_h, wall_t, bottom_t, top_t)
        
        cell_val_list = []
        # 하우징 내 바닥면 위치: -mod_h/2 + bottom_t
        # 셀의 바닥을 이 위치에 맞춤. 
        # create_cell이 Z=0에서 h까지 생성하므로, translation 값은 단순히 바닥면 좌표 + gap
        base_z_bottom = -mod_h / 2.0 + bottom_t + vertical_offset
        
        for pos in cells_positions:
            cell = self.create_cell(cell_spec['type'], cell_spec['l'], cell_spec['w'], cell_spec['h'])
            # create_cell 결과물의 바닥이 0이므로, base_z_bottom만큼 그냥 이동시키면 됨
            cell = cell.translate((pos[0], pos[1], base_z_bottom))
            cell_val_list.append(cell.val())
            
        cells_compound = cq.Compound.makeCompound(cell_val_list)
        
        return {
            "housing": module_housing,
            "cells": cells_compound
        }

    def create_full_pack(self, module_data, module_positions, offset=(0, 0, 0)):
        """전체 팩 조립체를 생성하며 오프셋을 적용합니다."""
        all_module_housings = []
        all_cells = []
        
        for pos in module_positions:
            # 기본 위치 + 사용자 오프셋
            final_pos = (pos[0] + offset[0], pos[1] + offset[1], 10 + offset[2])
            
            mod_h = module_data["housing"].translate(final_pos)
            mod_c = cq.Compound.makeCompound([module_data["cells"]]).translate(final_pos)
            
            all_module_housings.append(mod_h.val())
            all_cells.append(mod_c.val())
            
        return {
            "pack": self.pack_housing,
            "modules": cq.Compound.makeCompound(all_module_housings),
            "cells": cq.Compound.makeCompound(all_cells)
        }

    def export_to_step(self, components_dict, output_path):
        """구성 요소들을 합쳐서 STEP 파일로 내보냅니다."""
        all_shapes = []
        for key in components_dict:
            if components_dict[key]:
                if isinstance(components_dict[key], cq.Workplane):
                    all_shapes.append(components_dict[key].val())
                else:
                    all_shapes.append(components_dict[key])
                    
        final_compound = cq.Compound.makeCompound(all_shapes)
        cq.exporters.export(final_compound, output_path)
        return output_path

    def get_mesh_file(self, shape):
        """시각화를 위해 형상을 임시 STL 파일로 변환합니다."""
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, "ecopack_temp_mesh.stl")
        try:
            # STL로 내보내어 뷰어에서 읽을 수 있게 함
            cq.exporters.export(shape, temp_file, cq.exporters.ExportTypes.STL)
            return temp_file
        except Exception as e:
            print(f"Mesh export error: {e}")
            return None
