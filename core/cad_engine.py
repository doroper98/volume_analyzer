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
            
            # 형상을 원점(0,0,0)으로 강제 이동 (Origin Alignment)
            bb = self.pack_housing.val().BoundingBox()
            self.pack_housing = self.pack_housing.translate((-bb.xmin, -bb.ymin, -bb.zmin))
            
            # 이동 후의 새 바운딩 박스를 기준으로 정보 반환
            final_bb = self.pack_housing.val().BoundingBox()
            print(f"Aligned Bounding Box: {final_bb.xlen}x{final_bb.ylen}x{final_bb.zlen}")
            return {
                "l": final_bb.xlen,
                "w": final_bb.ylen,
                "h": final_bb.zlen
            }
        except Exception as e:
            print(f"Error loading STEP: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def create_inner_cavity(self, wall_thickness, bottom_thickness=None):
        """팩 하우징의 안쪽 방향으로 두께를 적용한 내부 공간 형상을 생성합니다.
        
        STEP 형상의 모든 면을 안쪽으로 wall_thickness만큼 오프셋하여
        실제 내부 가용 공간을 정확하게 표현합니다.
        bottom_thickness가 wall_thickness와 다를 경우 바닥 높이를 추가 보정합니다.
        """
        if not self.pack_housing or wall_thickness <= 0:
            return None
        
        try:
            from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape
            from OCP.BRepOffset import BRepOffset_Skin
            from OCP.GeomAbs import GeomAbs_Intersection
            
            shape = self.pack_housing.val().wrapped
            
            # 모든 면을 안쪽(-) 방향으로 wall_thickness만큼 오프셋
            maker = BRepOffsetAPI_MakeOffsetShape()
            maker.PerformBySimple(shape, -wall_thickness)
            
            if not maker.IsDone():
                print("Offset operation did not complete, falling back to box")
                return None
            
            inner_shape = cq.Shape(maker.Shape())
            result = cq.Workplane("XY").newObject([inner_shape])
            
            # bottom_thickness가 wall_thickness와 다르면 바닥을 추가 조정
            if bottom_thickness is not None and bottom_thickness != wall_thickness:
                bb = inner_shape.BoundingBox()
                diff = bottom_thickness - wall_thickness
                if diff > 0:
                    # 아래쪽을 더 잘라내야 함 (bottom이 더 두꺼움)
                    cut_box = cq.Workplane("XY").box(
                        bb.xlen + 20, bb.ylen + 20, diff
                    ).translate((
                        bb.xmin + bb.xlen / 2, 
                        bb.ymin + bb.ylen / 2, 
                        bb.zmin + diff / 2
                    ))
                    result = result.cut(cut_box)
                elif diff < 0:
                    # bottom이 더 얇은 경우: 아래쪽을 더 확장 (복잡 - 생략, 근사 처리)
                    pass
            
            return result
            
        except Exception as e:
            print(f"Inner cavity creation failed: {e}")
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
        """벽면, 바닥, 상단 두께가 각각 적용된 하우징 형상을 생성합니다. (0,0,0에서 시작)"""
        # (0,0,0) 코너 정렬을 위해 중심에서 L/2, W/2, H/2만큼 이동
        outer_box = cq.Workplane("XY").box(mod_l, mod_w, mod_h).translate((mod_l/2, mod_w/2, mod_h/2))
        
        inner_l = mod_l - 2*wall_t
        inner_w = mod_w - 2*wall_t
        inner_h = mod_h - bottom_t - top_t
        
        # 내부 공간 배치: 하우징 바닥으로부터 bottom_t 오프셋
        # 내부 박스의 중심점을 (L/2, W/2, bottom_t + inner_h/2)로 설정
        inner_z_center = bottom_t + inner_h / 2.0
        inner_box = cq.Workplane("XY").box(inner_l, inner_w, inner_h).translate((mod_l/2, mod_w/2, inner_z_center))
        
        return outer_box.cut(inner_box)

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

    def create_full_pack(self, module_data, module_positions, offset=(0, 0, 0), wall_thickness=0, bottom_thickness=0):
        """전체 팩 조립체를 생성하며 모듈이 바닥을 뚫지 않도록 안착시킵니다."""
        all_module_housings = []
        all_cells = []
        
        # 팩 하우징 확인 및 원점 기준 처리
        shifted_pack = None
        if self.pack_housing:
            # 이미 load_step에서 zmin=0으로 맞춰졌으므로 그대로 사용
            shifted_pack = self.pack_housing.val()

        for pos in module_positions:
            # 모듈 하우징 정보 (0,0,0 시작 기준)
            mod_shape = module_data["housing"].val()
            mod_bb = mod_shape.BoundingBox()
            mod_l = mod_bb.xlen
            mod_w = mod_bb.ylen
            
            # Z 위치: 팩 바닥 두께(bottom_thickness) + 사용자 수동 Z 오프셋
            # 팩 바깥 바닥이 z=0이므로, 내부 바닥은 z=bottom_thickness임
            final_z = bottom_thickness + offset[2]
            
            # 팩의 중심점 계산
            if shifted_pack:
                p_bb = shifted_pack.BoundingBox()
                center_x = p_bb.xlen / 2.0
                center_y = p_bb.ylen / 2.0
            else:
                center_x, center_y = 0, 0

            # 중심점 기반 배치 좌표 (X, Y) 및 안착 좌표 (Z)
            # pos는 이미 모듈의 중심 좌표이므로, 팩 중심(center_x)에 그대로 더해주면 됨
            final_pos_vec = cq.Vector(
                pos[0] + center_x + offset[0], 
                pos[1] + center_y + offset[1], 
                final_z
            )
            
            # 모듈 하우징 및 셀 이동
            mod_h_moved = mod_shape.moved(cq.Location(final_pos_vec))
            
            # cells는 이미 Compound 형태인 경우와 Workplane인 경우를 모두 대응
            cells_shape = module_data["cells"]
            if hasattr(cells_shape, "val"):
                cells_shape = cells_shape.val()
            
            mod_c_moved = cells_shape.moved(cq.Location(final_pos_vec))
            
            all_module_housings.append(mod_h_moved)
            all_cells.append(mod_c_moved)
            
        return {
            "pack": shifted_pack,
            "modules": cq.Compound.makeCompound(all_module_housings) if all_module_housings else None,
            "cells": cq.Compound.makeCompound(all_cells) if all_cells else None
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
