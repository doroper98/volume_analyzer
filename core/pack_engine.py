import cadquery as cq
import os
import math
from .volume_mesh_engine import VolumeMeshEngine


class PackEngine:
    """팩 구성 엔진: STEP 파일 로딩, 내부 공간 생성, 모듈 배치, 메시 분석, 내보내기를 담당합니다.
    모듈 엔진과 독립적으로 동작합니다.
    """

    def __init__(self):
        self.cq = cq
        self.pack_housing = None
        self.available_volume = None
        self.mesh_engine = VolumeMeshEngine()

    # ─── STEP Loading ───────────────────────────────────────

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
            
            # Aligned Bounding Box 정보 반환
            final_bb = self.pack_housing.val().BoundingBox()
            print(f"Aligned Bounding Box: {final_bb.xlen}x{final_bb.ylen}x{final_bb.zlen}")
            
            # VolumeMeshEngine에 정렬된 형상을 직접 공유 (원본 파일 재로드 방지)
            self.mesh_engine.original_shape = self.pack_housing
            self.mesh_engine.original_solid = self.pack_housing.val().wrapped
            
            # 볼륨 계산
            from OCP.GProp import GProp_GProps
            from OCP.BRepGProp import BRepGProp
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(self.mesh_engine.original_solid, props)
            volume = abs(props.Mass())
            
            self.mesh_engine._bbox_info = {
                "x_len": round(final_bb.xlen, 2),
                "y_len": round(final_bb.ylen, 2),
                "z_len": round(final_bb.zlen, 2),
                "x_min": round(final_bb.xmin, 2), "x_max": round(final_bb.xmax, 2),
                "y_min": round(final_bb.ymin, 2), "y_max": round(final_bb.ymax, 2),
                "z_min": round(final_bb.zmin, 2), "z_max": round(final_bb.zmax, 2),
                "volume_mm3": round(volume, 2),
            }
            self.mesh_engine.inner_volume = None
            self.mesh_engine.wall_solid = None
            self.mesh_engine.thickness = 0.0
            self.mesh_engine.volume_mesh = None
            
            print(f"[Engine] Mesh engine synced with aligned pack housing (Vol: {volume:.1f} mm³)")
            
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

    # ─── Inner Cavity ───────────────────────────────────────

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
                    cut_box = cq.Workplane("XY").box(
                        bb.xlen + 20, bb.ylen + 20, diff
                    ).translate((
                        bb.xmin + bb.xlen / 2, 
                        bb.ymin + bb.ylen / 2, 
                        bb.zmin + diff / 2
                    ))
                    result = result.cut(cut_box)
                elif diff < 0:
                    pass
            
            return result
            
        except Exception as e:
            print(f"Inner cavity creation failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ─── Module Packing in Pack ─────────────────────────────

    @staticmethod
    def pack_modules_in_pack(pack_l, pack_w, mod_l, mod_w, clearance, align_x="Center", align_y="Center"):
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
        
        if not positions:
            return []
        
        # Alignment
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        half_l = pack_l / 2
        half_w = pack_w / 2
        
        # X alignment
        shift_x = 0
        if align_x == "Even":
            unique_xs = sorted(set(xs))
            if len(unique_xs) > 1:
                new_start = -half_l + mod_l / 2
                new_end = half_l - mod_l / 2
                pitch = (new_end - new_start) / (len(unique_xs) - 1)
                mapping = {old: new_start + i * pitch for i, old in enumerate(unique_xs)}
                positions = [(mapping[p[0]], p[1]) for p in positions]
            # 1열이면 Center로 폴백 (아무것도 안 함 = 이미 중앙)
        elif align_x == "Start":
            shift_x = -half_l + mod_l / 2 - min(xs)
        elif align_x == "End":
            shift_x = half_l - mod_l / 2 - max(xs)
        
        if shift_x != 0:
            positions = [(p[0] + shift_x, p[1]) for p in positions]
        
        # Y alignment
        shift_y = 0
        ys = [p[1] for p in positions]
        if align_y == "Even":
            unique_ys = sorted(set(ys))
            if len(unique_ys) > 1:
                new_start = -half_w + mod_w / 2
                new_end = half_w - mod_w / 2
                pitch = (new_end - new_start) / (len(unique_ys) - 1)
                mapping = {old: new_start + i * pitch for i, old in enumerate(unique_ys)}
                positions = [(p[0], mapping[p[1]]) for p in positions]
            # 1행이면 Center로 폴백 (아무것도 안 함 = 이미 중앙)
        elif align_y == "Start":
            shift_y = -half_w + mod_w / 2 - min(ys)
        elif align_y == "End":
            shift_y = half_w - mod_w / 2 - max(ys)
        
        if shift_y != 0:
            positions = [(p[0], p[1] + shift_y) for p in positions]
        
        return positions

    # ─── Full Pack Assembly ─────────────────────────────────

    def create_full_pack(self, module_data, module_positions, offset=(0, 0, 0), wall_thickness=0, bottom_thickness=0, module_rotated=False, pack_dims=None):
        """전체 팩 조립체를 생성하며 모듈이 바닥을 뚫지 않도록 안착시킵니다."""
        all_module_housings = []
        all_cells = []
        
        # 팩 하우징 확인 및 원점 기준 처리
        shifted_pack = None
        if self.pack_housing:
            shifted_pack = self.pack_housing.val()

        # 팩 중심점: 반드시 load_step에서 계산한 치수 사용
        if pack_dims:
            center_x = pack_dims[0] / 2.0
            center_y = pack_dims[1] / 2.0
        elif shifted_pack:
            p_bb = shifted_pack.BoundingBox()
            center_x = p_bb.xlen / 2.0
            center_y = p_bb.ylen / 2.0
        else:
            center_x, center_y = 0, 0

        for pos in module_positions:
            # 모듈 하우징 정보 (0,0,0 시작 기준)
            mod_shape = module_data["housing"].val()
            mod_bb = mod_shape.BoundingBox()
            mod_l = mod_bb.xlen
            mod_w = mod_bb.ylen
            
            # 회전 적용: 모듈과 셀을 Z축 기준 90도 회전
            if module_rotated:
                mod_shape = mod_shape.located(cq.Location())
                mod_shape_wp = cq.Workplane("XY").newObject([cq.Shape(mod_shape)])
                mod_shape_wp = mod_shape_wp.rotate((mod_l/2, mod_w/2, 0), (mod_l/2, mod_w/2, 1), 90)
                mod_shape = mod_shape_wp.val()
                rot_mod_l = mod_w
                rot_mod_w = mod_l
            else:
                rot_mod_l = mod_l
                rot_mod_w = mod_w
            
            # Z 위치: 팩 바닥 두께(bottom_thickness) + 사용자 수동 Z 오프셋
            final_z = bottom_thickness + offset[2]

            # 중심점 기반 배치 좌표 (X, Y) 및 안착 좌표 (Z)
            if module_rotated:
                rot_bb = mod_shape.BoundingBox()
                final_pos_vec = cq.Vector(
                    pos[0] + center_x + offset[0] - rot_bb.xmin - rot_mod_l / 2.0,
                    pos[1] + center_y + offset[1] - rot_bb.ymin - rot_mod_w / 2.0,
                    final_z - rot_bb.zmin
                )
            else:
                final_pos_vec = cq.Vector(
                    pos[0] + center_x + offset[0] - mod_l / 2.0, 
                    pos[1] + center_y + offset[1] - mod_w / 2.0, 
                    final_z
                )
            
            # 모듈 하우징 이동
            mod_h_moved = mod_shape.moved(cq.Location(final_pos_vec))
            
            # cells는 이미 Compound 형태인 경우와 Workplane인 경우를 모두 대응
            cells_shape = module_data["cells"]
            if hasattr(cells_shape, "val"):
                cells_shape = cells_shape.val()
            
            if module_rotated:
                cells_wp = cq.Workplane("XY").newObject([cq.Shape(cells_shape)])
                cells_wp = cells_wp.rotate((mod_l/2, mod_w/2, 0), (mod_l/2, mod_w/2, 1), 90)
                cells_shape = cells_wp.val()
            
            mod_c_moved = cells_shape.moved(cq.Location(final_pos_vec))
            
            all_module_housings.append(mod_h_moved)
            all_cells.append(mod_c_moved)
            
        return {
            "pack": shifted_pack,
            "modules": cq.Compound.makeCompound(all_module_housings) if all_module_housings else None,
            "cells": cq.Compound.makeCompound(all_cells) if all_cells else None
        }

    # ─── Export ──────────────────────────────────────────────

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
            cq.exporters.export(shape, temp_file, cq.exporters.ExportTypes.STL)
            return temp_file
        except Exception as e:
            print(f"Mesh export error: {e}")
            return None
