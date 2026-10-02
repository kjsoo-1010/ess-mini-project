"""초기 사이클 데이터로 셀 단위 피처를 만든다.

모든 피처 함수는 Dataset.early_window() 로 잘라낸 데이터만 입력으로 받는다.
입력 범위 이후의 값이 피처에 섞이는 것(누수)을 구조적으로 막기 위해서다.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from src import config
from src.preprocess import Dataset

FeatureFn = Callable[[Dataset], np.ndarray]


@dataclass(frozen=True)
class Feature:
    name: str
    description: str
    compute: FeatureFn  # 셀 순서(cells.index)대로 값 하나씩


# --------------------------------------------------------------------------- #
# 공통 계산
# --------------------------------------------------------------------------- #
def discharge_curve(ds: Dataset, cycle: int, halfwidth: int = 0) -> np.ndarray:
    """cycle 주변 (2 * halfwidth + 1)개 사이클의 Q(V) 곡선 중앙값. shape=(셀 수, 전압 지점 수)."""
    lo, hi = max(cycle - halfwidth, 1), min(cycle + halfwidth, ds.n_cycles)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # 전부 NaN 인 구간은 NaN 으로 둔다
        return np.nanmedian(ds.qdlin[:, lo - 1 : hi], axis=1)


def delta_q(ds: Dataset, late: int, early: int, halfwidth: int = 0) -> np.ndarray:
    """ΔQ(V) = Q_late(V) - Q_early(V). shape=(셀 수, 전압 지점 수)."""
    return discharge_curve(ds, late, halfwidth) - discharge_curve(ds, early, halfwidth)


def summary_matrix(ds: Dataset, column: str) -> pd.DataFrame:
    """summary 의 한 컬럼을 (셀 x 사이클) 표로 펼친다. 행 순서는 cells.index 와 같다."""
    return ds.summary.pivot(index="cell_key", columns="cycle", values=column).reindex(ds.cells.index)


def value_near(matrix: pd.DataFrame, cycle: int, halfwidth: int = 1) -> np.ndarray:
    """cycle 주변 사이클 값의 중앙값. 단일 사이클의 측정 이상값에 흔들리지 않게 한다."""
    window = [c for c in matrix.columns if abs(c - cycle) <= halfwidth]
    return matrix[window].median(axis=1).to_numpy()


# --------------------------------------------------------------------------- #
# 피처 정의
# --------------------------------------------------------------------------- #
def _log_dq_var(ds: Dataset) -> np.ndarray:
    return np.log10(np.var(delta_q(ds, late=ds.n_cycles, early=10), axis=1))


def _log_dq_var_smooth(ds: Dataset) -> np.ndarray:
    return np.log10(np.var(delta_q(ds, late=ds.n_cycles, early=10, halfwidth=1), axis=1))


def _qd_fade(ds: Dataset) -> np.ndarray:
    qd = summary_matrix(ds, "QD")
    return value_near(qd, ds.n_cycles) - value_near(qd, 2)


def _chargetime_median(ds: Dataset) -> np.ndarray:
    return summary_matrix(ds, "chargetime").median(axis=1).to_numpy()


def _tavg_mean(ds: Dataset) -> np.ndarray:
    return summary_matrix(ds, "Tavg").mean(axis=1).to_numpy()


def _ir_diff(ds: Dataset) -> np.ndarray:
    ir = summary_matrix(ds, "IR")
    return value_near(ir, ds.n_cycles) - value_near(ir, 2)


def _qd_initial(ds: Dataset) -> np.ndarray:
    return value_near(summary_matrix(ds, "QD"), 2)


def _qd_rise(ds: Dataset) -> np.ndarray:
    qd = summary_matrix(ds, "QD")
    smoothed = qd.T.rolling(5, center=True, min_periods=1).median().T  # 사이클 방향 평활화
    return smoothed.max(axis=1).to_numpy() - value_near(qd, 2)


def _dq(ds: Dataset) -> np.ndarray:
    return delta_q(ds, late=ds.n_cycles, early=10)


def _log_abs(values: np.ndarray) -> np.ndarray:
    return np.log10(np.abs(values))


def _qd_slope(ds: Dataset, first_cycle: int) -> np.ndarray:
    """first_cycle 부터 마지막 사이클까지 용량의 선형 추세 기울기 (mAh / cycle). 결측 사이클은 건너뛴다."""
    qd = summary_matrix(ds, "QD").loc[:, first_cycle:]
    cycles = qd.columns.to_numpy(dtype=float)
    return np.array([np.polyfit(cycles[row.notna()], row.dropna(), 1)[0] * 1000 for _, row in qd.iterrows()])


FEATURES: dict[str, Feature] = {
    f.name: f
    for f in (
        Feature("log_dq_var", "log10 var(Q_last(V) - Q_10(V)). 핵심 피처", _log_dq_var),
        Feature("log_dq_var_smooth", "log_dq_var 를 인접 3개 사이클의 중앙값 곡선으로 계산", _log_dq_var_smooth),
        Feature("qd_fade", "초기 용량 변화: 마지막 사이클 용량 - cycle 2 용량 (Ah)", _qd_fade),
        Feature("chargetime_median", "충전 시간(0% -> 80%)의 중앙값 (분)", _chargetime_median),
        Feature("tavg_mean", "평균 온도의 평균 (°C)", _tavg_mean),
        Feature("ir_diff", "내부저항 변화: 마지막 사이클 - cycle 2 (Ω)", _ir_diff),
        # 아래 두 개는 사후 분석용이다. DAY 1 전략의 후보 피처가 아니다
        Feature("qd_initial", "초기 용량의 절대 수준: cycle 2 용량 (Ah)", _qd_initial),
        Feature("qd_rise", "초기 용량 상승폭: 평활화한 최대 용량 - cycle 2 용량 (Ah)", _qd_rise),
        # zero-shot 분류의 후보 피처. 원논문의 후보 피처 중 용량의 절대 수준과 내부저항을 뺀 것이다
        Feature("log_dq_min", "log10 |min ΔQ(V)|", lambda ds: _log_abs(_dq(ds).min(axis=1))),
        Feature("log_dq_mean", "log10 |mean ΔQ(V)|", lambda ds: _log_abs(_dq(ds).mean(axis=1))),
        Feature("log_dq_skew", "log10 |skewness of ΔQ(V)|", lambda ds: _log_abs(stats.skew(_dq(ds), axis=1))),
        Feature("log_dq_kurt", "log10 |kurtosis of ΔQ(V)|", lambda ds: _log_abs(stats.kurtosis(_dq(ds), axis=1))),
        Feature("log_dq_at_2v", "log10 |ΔQ(V = 2.0 V)|. 전압 축의 마지막 지점", lambda ds: _log_abs(_dq(ds)[:, -1])),
        Feature("qd_slope", "용량 추세의 기울기, cycle 2 ~ 마지막 (mAh / cycle)", lambda ds: _qd_slope(ds, 2)),
        Feature(
            "qd_slope_late",
            "용량 추세의 기울기, 마지막 10 사이클 (mAh / cycle)",
            lambda ds: _qd_slope(ds, ds.n_cycles - 9),
        ),
        Feature("tmax_max", "최고 온도의 최댓값 (°C)", lambda ds: summary_matrix(ds, "Tmax").max(axis=1).to_numpy()),
    )
}


def build_feature_table(
    dataset: Dataset,
    n_cycles: int = config.EARLY_CYCLES,
    names: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """셀당 한 행의 피처 표. index=cell_key. 초기 n_cycles 사이클만 사용한다."""
    early = dataset.early_window(n_cycles)
    names = names or tuple(FEATURES)
    return pd.DataFrame({name: FEATURES[name].compute(early) for name in names}, index=early.cells.index)


def available_features(table: pd.DataFrame) -> tuple[str, ...]:
    """모든 셀에서 값이 있는 피처만 고른다. 일부 배치에서 측정이 없는 피처는 모델에 쓸 수 없다."""
    return tuple(name for name in table.columns if table[name].notna().all())
