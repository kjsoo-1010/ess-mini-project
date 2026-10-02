"""프로젝트 전역 설정: 경로, 배치 사양, 도메인 상수.

값의 근거는 DAY 1 보고서(docs/DAY-1.pdf)의 "데이터와 전처리"와 "모델 설계 전략"에 정리되어 있다.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"

KAGGLE_DATASET = "itshpark/data-driven-prediction-of-battery-cycle"
DATA_DIR_ENV = "ESS_DATA_DIR"  # 지정하면 kagglehub 대신 이 경로에서 .mat 파일을 읽는다

# 공칭 용량 1.1 Ah 인 셀에서 이보다 큰 방전 용량은 측정 오류로 본다
MAX_VALID_CAPACITY_AH = 1.3

# 모델 입력 범위와 과제 기준
EARLY_CYCLES = 100  # Regression 입력: 초기 100 사이클
SHORT_LIFE_THRESHOLD = 550  # 장/단수명 구분 기준 (가이드)
TARGET_MAPE = 9.1  # 원논문 성능 (%)
SCREENING_ALPHA = 0.1  # 단수명 선별에서 예측 하한의 수준 (1 - alpha = 90%)

SEED = 42


@dataclass(frozen=True)
class BatchSpec:
    """배치 하나의 원본 파일과 품질 처리 규칙."""

    name: str
    tag: str  # 셀 키 접두사. 예: "b1" -> "b1c0"
    filename: str
    drop_cells: tuple[int, ...] = ()  # 분석에서 제외하는 셀 번호
    life_offsets: Mapping[int, int] = field(default_factory=dict)  # 셀 번호 -> cycle_life 에 더할 값


BATCH_1 = BatchSpec(
    name="Batch 1",
    tag="b1",
    filename="2017-05-12_batchdata_updated_struct_errorcorrect.mat",
    # EOL 에 도달하기 전에 실험이 끝난 셀 (원논문 공식 코드 기준)
    drop_cells=(8, 10, 12, 13, 22),
    # 다음 배치로 실험이 이어진 셀. 보정 후 값이 원논문 Supplementary Table 9 와 일치한다
    life_offsets=MappingProxyType({0: 662, 1: 981, 2: 1060, 3: 208, 4: 482}),
)
BATCH_2 = BatchSpec(
    name="Batch 2",
    tag="b2",
    filename="2018-02-20_batchdata_updated_struct_errorcorrect.mat",
    # cycle_life 가 비어 있는 실험용 셀(VarCharge, SLOWCYCLE)은 로딩 단계에서 자동 제외된다
)
BATCH_3 = BatchSpec(
    name="Batch 3",
    tag="b3",
    filename="2018-04-12_batchdata_updated_struct_errorcorrect.mat",
    # 측정 노이즈, EOL 미도달 (원논문 공식 코드 기준)
    drop_cells=(2, 23, 32, 37, 42, 43),
)

BATCHES: tuple[BatchSpec, ...] = (BATCH_1, BATCH_2, BATCH_3)
TRAIN_BATCH = BATCH_1.name
TEST_BATCH = BATCH_2.name
EXTRA_TEST_BATCH = BATCH_3.name
