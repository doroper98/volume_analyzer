"""
Volume Mesh Engine
==================
STEP 파일을 불러와 내부 방향 두께를 적용하고,
남은 내부 공간에 대해 볼륨 메시(Tetrahedral)를 생성하는 핵심 엔진.

용도: 열전파(Thermal Propagation), 열유동(Thermal Flow) 해석용 메시 생성
기술: CadQuery (OpenCASCADE), PyVista, TetGen
"""

import os
import sys
import tempfile
import numpy as np

# Windows 콘솔 인코딩 호환
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

import cadquery as cq
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape
from OCP.BRep import BRep_Tool
from OCP.GeomAbs import GeomAbs_Intersection
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

import pyvista as pv
import tetgen


class VolumeMeshEngine:
    """
    Volume Mesher 핵심 엔진

    파이프라인:
        1. load_step()        → STEP 파일 로드
        2. apply_thickness()  → 내부 방향 두께 적용 → 내부 공간 추출
        3. visualize()        → 원본/내부공간 3D 시각화
        4. generate_volume_mesh() → 내부 공간 테트라 메시 생성
        5. export_mesh()      → 메시 파일 내보내기
    """

    def __init__(self):
        self.original_shape = None      # CadQuery Workplane (원본 STEP)
        self.original_solid = None      # OCP TopoDS_Shape (원본 솔리드)
        self.inner_volume = None        # CadQuery Workplane (내부 공간)
        self.wall_solid = None          # CadQuery Workplane (벽체)
        self.thickness = 0.0
        self.volume_mesh = None         # PyVista UnstructuredGrid (볼륨 메시)
        self.surface_mesh = None        # PyVista PolyData (표면 메시)
        self._bbox_info = None

    # ──────────────────────────────────────────────
    # 1. STEP 파일 로딩
    # ──────────────────────────────────────────────
    def load_step(self, file_path: str) -> dict:
        """
        STEP 파일을 로드하고 바운딩 박스 정보를 반환합니다.

        Args:
            file_path: STEP 파일 경로 (.step, .stp)

        Returns:
            dict: 바운딩 박스 정보 {x, y, z, volume_mm3}
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        print(f"[Engine] STEP 파일 로딩 중: {file_path}")
        self.original_shape = cq.importers.importStep(file_path)
        self.original_solid = self.original_shape.val().wrapped

        bb = self.original_shape.val().BoundingBox()
        
        # 볼륨 계산
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(self.original_solid, props)
        volume = props.Mass()

        self._bbox_info = {
            "x_len": round(bb.xlen, 2),
            "y_len": round(bb.ylen, 2),
            "z_len": round(bb.zlen, 2),
            "x_min": round(bb.xmin, 2), "x_max": round(bb.xmax, 2),
            "y_min": round(bb.ymin, 2), "y_max": round(bb.ymax, 2),
            "z_min": round(bb.zmin, 2), "z_max": round(bb.zmax, 2),
            "volume_mm3": round(volume, 2),
        }

        print(f"[Engine] [OK] 로드 완료")
        print(f"[Engine]    크기: {self._bbox_info['x_len']} x {self._bbox_info['y_len']} x {self._bbox_info['z_len']} mm")
        print(f"[Engine]    볼륨: {self._bbox_info['volume_mm3']:.1f} mm³")

        # 상태 초기화
        self.inner_volume = None
        self.wall_solid = None
        self.thickness = 0.0
        self.volume_mesh = None

        return self._bbox_info

    # ──────────────────────────────────────────────
    # 2. 내부 방향 두께 적용
    # ──────────────────────────────────────────────
    def apply_thickness(self, thickness: float) -> dict:
        """
        원본 형상에 내부 방향 두께를 적용하여 내부 공간을 추출합니다.

        예: 지름 20cm 구에 두께 1cm → 지름 18cm 내부 공간

        Args:
            thickness: 벽 두께 (mm, 양수)

        Returns:
            dict: 내부 공간 정보 {inner_volume_mm3, wall_volume_mm3, thickness}
        """
        if self.original_shape is None:
            raise RuntimeError("먼저 load_step()으로 STEP 파일을 로드하세요.")
        if thickness <= 0:
            raise ValueError("두께는 양수여야 합니다.")

        self.thickness = thickness
        print(f"[Engine] 두께 {thickness}mm 적용 중...")

        # 방법 1: OCP BRepOffsetAPI_MakeOffsetShape (가장 범용적)
        inner_solid = self._offset_shape_ocp(thickness)

        if inner_solid is None:
            # 방법 2: CadQuery shell (fallback)
            print("[Engine] [WARN] OCP 오프셋 실패, CadQuery shell 시도...")
            inner_solid = self._offset_shape_cadquery(thickness)

        if inner_solid is None:
            raise RuntimeError(
                f"두께 {thickness}mm 오프셋 적용 실패. "
                "형상이 너무 복잡하거나 두께가 너무 큰 경우일 수 있습니다."
            )

        self.inner_volume = inner_solid

        # 볼륨 계산
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp

        inner_props = GProp_GProps()
        BRepGProp.VolumeProperties_s(self.inner_volume.val().wrapped, inner_props)
        inner_vol = abs(inner_props.Mass())

        original_vol = abs(self._bbox_info["volume_mm3"])
        wall_vol = original_vol - inner_vol

        result = {
            "thickness": thickness,
            "original_volume_mm3": round(original_vol, 2),
            "inner_volume_mm3": round(inner_vol, 2),
            "wall_volume_mm3": round(wall_vol, 2),
            "utilization_pct": round(inner_vol / original_vol * 100, 1) if original_vol > 0 else 0,
        }

        print(f"[Engine] [OK] 두께 적용 완료")
        print(f"[Engine]    원본 볼륨:  {result['original_volume_mm3']:.1f} mm³")
        print(f"[Engine]    내부 공간:  {result['inner_volume_mm3']:.1f} mm³")
        print(f"[Engine]    벽체 볼륨:  {result['wall_volume_mm3']:.1f} mm³")
        print(f"[Engine]    공간 활용:  {result['utilization_pct']}%")

        return result

    def _offset_shape_ocp(self, thickness: float):
        """OCP BRepOffsetAPI_MakeOffsetShape 로 내부 오프셋 생성"""
        try:
            offset_maker = BRepOffsetAPI_MakeOffsetShape()
            offset_maker.PerformBySimple(self.original_solid, -thickness)

            if not offset_maker.IsDone():
                print("[Engine]    OCP PerformBySimple 실패")
                return None

            offset_shape = offset_maker.Shape()

            # 솔리드 추출
            explorer = TopExp_Explorer(offset_shape, TopAbs_SOLID)
            if explorer.More():
                solid = TopoDS.Solid_s(explorer.Current())
                return cq.Workplane("XY").newObject([cq.Shape(solid)])
            else:
                print("[Engine]    OCP 결과에서 솔리드를 찾을 수 없음")
                return None

        except Exception as e:
            print(f"[Engine]    OCP 오프셋 오류: {e}")
            return None

    def _offset_shape_cadquery(self, thickness: float):
        """CadQuery shell() 로 내부 오프셋 생성 후 내부 공간 추출"""
        try:
            # shell(-thickness): 내부 방향으로 두께 생성
            # 면을 제거하지 않으면 쉘(속 빈 형상)이 됨
            # 원본 - 쉘 = 벽체
            # 내부 공간 = 원본에서 두께만큼 줄인 솔리드

            # 방법: 원본을 scale로 줄여서 Boolean 방식 사용
            # 이 방식은 범용적이지 않으므로 마지막 수단
            shelled = self.original_shape.shell(-thickness)
            
            # shelled 결과가 벽체(hollow shell)이므로,
            # 내부 공간 = 원본.cut(shelled)... 가 아니라
            # shelled 자체에서 내부 솔리드를 뽑아야 함
            # 실제로 shell은 벽체를 반환하므로 내부 공간은
            # 원본에서 벽체를 빼면 됨
            inner = self.original_shape.cut(shelled)
            
            # 솔리드 검증
            explorer = TopExp_Explorer(inner.val().wrapped, TopAbs_SOLID)
            if explorer.More():
                return inner
            else:
                return None

        except Exception as e:
            print(f"[Engine]    CadQuery shell 오류: {e}")
            return None

    # ──────────────────────────────────────────────
    # 3. 3D 시각화
    # ──────────────────────────────────────────────
    def _shape_to_pyvista(self, shape, tolerance=0.1) -> pv.PolyData:
        """CadQuery 형상을 PyVista PolyData로 변환"""
        temp_file = os.path.join(tempfile.gettempdir(), "vm_engine_temp.stl")
        try:
            if isinstance(shape, cq.Workplane):
                cq.exporters.export(shape, temp_file, cq.exporters.ExportTypes.STL,
                                    tolerance=tolerance)
            else:
                cq.exporters.export(shape, temp_file, cq.exporters.ExportTypes.STL,
                                    tolerance=tolerance)
            mesh = pv.read(temp_file)
            return mesh
        except Exception as e:
            print(f"[Engine] STL 변환 오류: {e}")
            return None
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    def visualize(self, target: str = "all", opacity_original: float = 0.15):
        """
        3D 시각화를 수행합니다.

        Args:
            target: 시각화 대상
                - "original": 원본만
                - "inner": 내부 공간만
                - "all": 원본(반투명) + 내부 공간
                - "mesh": 볼륨 메시
            opacity_original: 원본 형상 투명도 (0~1)
        """
        plotter = pv.Plotter(window_size=[1200, 800])
        plotter.set_background("white")

        if target in ("original", "all"):
            if self.original_shape is None:
                raise RuntimeError("먼저 load_step()으로 STEP 파일을 로드하세요.")
            
            original_mesh = self._shape_to_pyvista(self.original_shape)
            if original_mesh is not None:
                if target == "all" and self.inner_volume is not None:
                    plotter.add_mesh(original_mesh, color="#B0BEC5", opacity=opacity_original,
                                     show_edges=True, edge_color="#78909C", line_width=0.5,
                                     label="Original Shape")
                else:
                    plotter.add_mesh(original_mesh, color="#1976D2", opacity=0.6,
                                     show_edges=True, edge_color="#0D47A1", line_width=1,
                                     label="Original Shape")

        if target in ("inner", "all"):
            if self.inner_volume is None:
                raise RuntimeError("먼저 apply_thickness()로 두께를 적용하세요.")
            
            inner_mesh = self._shape_to_pyvista(self.inner_volume)
            if inner_mesh is not None:
                plotter.add_mesh(inner_mesh, color="#FF6F00", opacity=0.7,
                                 show_edges=True, edge_color="#E65100", line_width=1,
                                 label="Inner Volume")

        if target == "mesh":
            if self.volume_mesh is None:
                raise RuntimeError("먼저 generate_volume_mesh()로 메시를 생성하세요.")
            
            # 표면만 추출하여 시각화
            surface = self.volume_mesh.extract_surface()
            plotter.add_mesh(surface, color="#43A047", opacity=0.6,
                             show_edges=True, edge_color="#1B5E20", line_width=0.5,
                             label="Volume Mesh (Surface)")

        # 공통 설정
        plotter.add_axes(color="black", line_width=2)
        plotter.add_legend(face="circle")
        
        title_map = {
            "original": "Original STEP Shape",
            "inner": f"Inner Volume (Wall: {self.thickness}mm)",
            "all": f"Original + Inner Volume (Wall: {self.thickness}mm)",
            "mesh": "Volume Mesh (Tetrahedral)"
        }
        plotter.add_title(title_map.get(target, "Volume Mesh Engine"), font_size=14, color="black")

        plotter.show()

    # ──────────────────────────────────────────────
    # 4. 볼륨 메시 생성 (Tetrahedral)
    # ──────────────────────────────────────────────
    def generate_volume_mesh(self, max_edge_length: float = None,
                              quality: float = 1.2) -> dict:
        """
        내부 공간에 대해 테트라헤드럴 볼륨 메시를 생성합니다.

        Args:
            max_edge_length: 최대 엣지 길이 (mm). None이면 자동 계산.
            quality: 메시 품질 (라디우스-엣지 비율, 기본 1.2, 낮을수록 고품질)

        Returns:
            dict: 메시 통계 {n_nodes, n_elements, volume_mm3, ...}
        """
        if self.inner_volume is None:
            raise RuntimeError("먼저 apply_thickness()로 두께를 적용하세요.")

        print("[Engine] 볼륨 메시 생성 중...")

        # 1) 내부 공간을 STL 표면 메시로 변환
        surface_mesh = self._shape_to_pyvista(self.inner_volume, tolerance=0.05)
        if surface_mesh is None:
            raise RuntimeError("내부 공간의 표면 메시 생성 실패")

        # 표면 메시 정리
        surface_mesh = surface_mesh.clean()
        surface_mesh = surface_mesh.triangulate()
        self.surface_mesh = surface_mesh

        # 2) 자동 최대 엣지 길이 계산
        if max_edge_length is None:
            bounds = surface_mesh.bounds
            diag = np.sqrt(
                (bounds[1] - bounds[0])**2 +
                (bounds[3] - bounds[2])**2 +
                (bounds[5] - bounds[4])**2
            )
            max_edge_length = diag / 15.0  # 대각선의 1/15
            print(f"[Engine]    자동 엣지 길이: {max_edge_length:.2f} mm")

        # 3) TetGen으로 볼륨 메시 생성
        try:
            tet = tetgen.TetGen(surface_mesh)
            
            # TetGen 옵션:
            # order=1: linear tetrahedra
            # quality: radius-edge ratio
            # maxvolume: max tet volume based on edge length
            max_volume = (max_edge_length ** 3) / 6.0  # 정사면체 기준 근사
            
            tet.tetrahedralize(
                order=1,
                mindihedral=10,
                minratio=quality,
                maxvolume=max_volume,
                verbose=0,
            )

            self.volume_mesh = tet.grid

        except Exception as e:
            print(f"[Engine] [WARN] TetGen 실패: {e}")
            print("[Engine]    표면 메시로 대체합니다.")
            self.volume_mesh = None
            return {
                "n_nodes": surface_mesh.n_points,
                "n_elements": surface_mesh.n_cells,
                "mesh_type": "surface_only",
                "error": str(e),
            }

        # 4) 메시 통계
        stats = {
            "n_nodes": self.volume_mesh.n_points,
            "n_elements": self.volume_mesh.n_cells,
            "mesh_type": "tetrahedral",
            "max_edge_length": round(max_edge_length, 2),
            "quality_ratio": quality,
        }

        # 메시 볼륨 계산
        try:
            vol = self.volume_mesh.volume
            stats["mesh_volume_mm3"] = round(vol, 2)
        except:
            stats["mesh_volume_mm3"] = None

        print(f"[Engine] [OK] 볼륨 메시 생성 완료")
        print(f"[Engine]    노드 수:   {stats['n_nodes']:,}")
        print(f"[Engine]    요소 수:   {stats['n_elements']:,}")
        print(f"[Engine]    메시 타입: {stats['mesh_type']}")
        if stats.get("mesh_volume_mm3"):
            print(f"[Engine]    메시 볼륨: {stats['mesh_volume_mm3']:.1f} mm³")

        return stats

    # ──────────────────────────────────────────────
    # 5. 메시 내보내기
    # ──────────────────────────────────────────────
    def export_mesh(self, output_path: str, fmt: str = "vtk") -> str:
        """
        생성된 메시를 파일로 내보냅니다.

        Args:
            output_path: 출력 파일 경로
            fmt: 파일 형식 ("vtk", "stl", "vtu")

        Returns:
            str: 저장된 파일 경로
        """
        if self.volume_mesh is None and self.surface_mesh is None:
            raise RuntimeError("먼저 generate_volume_mesh()로 메시를 생성하세요.")

        mesh_to_save = self.volume_mesh if self.volume_mesh is not None else self.surface_mesh

        # 확장자 보정
        ext_map = {"vtk": ".vtk", "stl": ".stl", "vtu": ".vtu"}
        expected_ext = ext_map.get(fmt, f".{fmt}")
        if not output_path.endswith(expected_ext):
            output_path = output_path + expected_ext

        if fmt == "stl" and self.volume_mesh is not None:
            # STL은 표면만 저장 가능
            surface = self.volume_mesh.extract_surface()
            surface.save(output_path)
        else:
            mesh_to_save.save(output_path)

        print(f"[Engine] [OK] 메시 저장 완료: {output_path}")
        return output_path

    def export_inner_step(self, output_path: str) -> str:
        """
        내부 공간을 STEP 파일로 내보냅니다.

        Args:
            output_path: 출력 STEP 파일 경로

        Returns:
            str: 저장된 파일 경로
        """
        if self.inner_volume is None:
            raise RuntimeError("먼저 apply_thickness()로 두께를 적용하세요.")

        cq.exporters.export(self.inner_volume, output_path)
        print(f"[Engine] [OK] 내부 공간 STEP 저장 완료: {output_path}")
        return output_path

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────
    def get_info(self) -> dict:
        """현재 엔진 상태 요약 정보를 반환합니다."""
        info = {
            "step_loaded": self.original_shape is not None,
            "bbox": self._bbox_info,
            "thickness_applied": self.thickness > 0,
            "thickness_mm": self.thickness,
            "mesh_generated": self.volume_mesh is not None,
        }
        if self.volume_mesh is not None:
            info["mesh_nodes"] = self.volume_mesh.n_points
            info["mesh_elements"] = self.volume_mesh.n_cells
        return info
