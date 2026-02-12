# EcoPack Optimizer

배터리 팩, 모듈 및 셀의 배치를 최적화하고 CATIA에서 불러올 수 있는 STEP 파일로 내보내는 도구입니다.

## 주요 기능
- **팩 하우징 분석:** STEP 파일을 불러와 내부 가용 공간을 자동으로 파악합니다.
- **모듈 설계:** 모듈의 외곽 치수와 하네스를 고려한 벽 두께를 입력할 수 있습니다.
- **셀 최적 배치:** 
  - 원통형(Cylindrical): 지그재그(Hexagonal) 배치를 통한 밀도 극대화.
  - 각형(Prismatic/Pouch): 정밀 가이드를 통한 격자 배치.
- **CATIA 호환:** 모든 결과물은 개별 파트 정보가 유지된 STEP 파일로 내보내집니다.

## 실행 방법
1. `run.bat`을 실행하여 프로그램을 엽니다.
2. `Load STEP File` 버튼으로 팩 하우징(예: `sample_pack.step`)을 불러옵니다.
3. 모듈 및 셀 제원을 입력합니다.
4. `START OPTIMIZATION`을 클릭하여 배치를 완료합니다.
5. `EXPORT TO CATIA`를 통해 결과 파일을 저장합니다.

## 개발 정보
- **기술 스택:** Python, PySide6, CadQuery (OpenCASCADE)
- **복잡도:** 2단계 최적화 (Cell-in-Module, Module-in-Pack)
