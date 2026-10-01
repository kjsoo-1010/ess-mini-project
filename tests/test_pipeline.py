"""핵심 규칙에 대한 테스트. 원본 데이터 없이 합성 데이터로 실행된다."""

import numpy as np
import pandas as pd
import pytest

from src.evaluation import classification_metrics, mape, select_model, split_train_valid
from src.features import build_feature_table
from src.preprocess import Dataset, clean_summary

N_CELLS, N_CYCLES, N_POINTS = 6, 120, 50


@pytest.fixture
def dataset() -> Dataset:
    """셀마다 열화 속도가 다른 합성 데이터. 곡선은 사이클이 지날수록 일정 비율로 줄어든다."""
    rng = np.random.default_rng(0)
    keys = [f"b1c{i}" for i in range(N_CELLS)]
    rates = np.linspace(1e-4, 6e-4, N_CELLS)
    base = np.linspace(0.0, 1.1, N_POINTS)
    cycles = np.arange(1, N_CYCLES + 1)
    qdlin = base[None, None, :] * (1 - rates[:, None, None] * cycles[None, :, None])
    summary = pd.DataFrame(
        {
            "cell_key": np.repeat(keys, N_CYCLES),
            "cycle": np.tile(cycles, N_CELLS),
            "QD": qdlin[:, :, -1].ravel(),
            "QC": qdlin[:, :, -1].ravel(),
            "IR": 0.017,
            "Tavg": 32.0,
            "Tmax": 36.0,
            "Tmin": 30.0,
            "chargetime": rng.normal(10.0, 0.1, N_CELLS * N_CYCLES),
        }
    )
    cells = pd.DataFrame(
        {
            "batch": "Batch 1",
            "cell_id": range(N_CELLS),
            "policy": "4C(80%)-4C",
            "cycle_life": (0.2 / rates).astype(int),
        },
        index=pd.Index(keys, name="cell_key"),
    )
    return Dataset(cells=cells, summary=summary, qdlin=qdlin, vdlin=np.linspace(3.5, 2.0, N_POINTS))


def test_features_ignore_cycles_after_input_window(dataset: Dataset) -> None:
    """입력 범위 이후의 값을 바꿔도 피처가 달라지지 않아야 한다 (누수 방지)."""
    tampered_curves = dataset.qdlin.copy()
    tampered_curves[:, 100:] = 999.0
    tampered_summary = dataset.summary.copy()
    tampered_summary.loc[tampered_summary["cycle"] > 100, ["QD", "IR", "Tavg", "chargetime"]] = 999.0
    tampered = Dataset(dataset.cells, tampered_summary, tampered_curves, dataset.vdlin)

    pd.testing.assert_frame_equal(build_feature_table(dataset, 100), build_feature_table(tampered, 100))


def test_faster_fading_cell_has_larger_dq_variance(dataset: Dataset) -> None:
    features = build_feature_table(dataset, 100, names=("log_dq_var",))
    assert features["log_dq_var"].is_monotonic_increasing  # 열화 속도 순으로 정렬된 합성 데이터


def test_early_window_rejects_range_beyond_loaded_cycles(dataset: Dataset) -> None:
    with pytest.raises(ValueError):
        dataset.early_window(N_CYCLES + 1)


def test_clean_summary_removes_unmeasured_and_impossible_values() -> None:
    raw = pd.DataFrame(
        {
            "cell_key": "b1c0",
            "cycle": [1, 2, 3, 4],
            "QD": [0.0, 1.07, 2.88, 1.06],
            "QC": [0.0, 1.07, 2.97, 1.06],
            "IR": [0.0, 0.017, 0.017, 0.0],
            "Tavg": 32.0,
            "Tmax": 36.0,
            "Tmin": 30.0,
            "chargetime": 10.0,
        }
    )
    cleaned = clean_summary(raw)
    assert cleaned["cycle"].tolist() == [2, 3, 4]  # 측정값이 없는 cycle 1 은 제거
    assert np.isnan(cleaned.loc[cleaned["cycle"] == 3, "QD"]).all()  # 2.88 Ah 는 결측 처리
    assert np.isnan(cleaned.loc[cleaned["cycle"] == 4, "IR"]).all()  # IR 0 은 결측 처리


def test_mape() -> None:
    assert mape([100, 200], [110, 180]) == pytest.approx(10.0)


def test_split_is_disjoint_and_complete() -> None:
    life = pd.Series(np.linspace(500, 2200, 40), index=[f"c{i}" for i in range(40)])
    split = split_train_valid(life, valid_size=0.2, seed=0)
    assert set(split.train).isdisjoint(split.valid)
    assert set(split.train) | set(split.valid) == set(life.index)
    assert len(split.valid) == 8


def test_select_model_keeps_incumbent_unless_clearly_beaten() -> None:
    table = pd.DataFrame({"model": ["base", "close", "better"], "cv_mape": [9.0, 8.8, 7.0], "cv_se": [0.5, 0.5, 0.5]})
    assert select_model(table[table["model"] != "better"], incumbent="base") == "base"  # 표준오차 이내
    assert select_model(table, incumbent="base") == "better"


def test_classification_metrics_use_threshold_on_predicted_life() -> None:
    result = classification_metrics(y_true=[400, 450, 900, 1000], y_pred=[500, 600, 800, 1200])
    assert result["accuracy"] == pytest.approx(0.75)  # 450 을 600 으로 예측해 장수명으로 오분류
    assert result["auc"] == pytest.approx(1.0)  # 순위는 완전히 맞음
