"""핵심 규칙에 대한 테스트. 원본 데이터 없이 합성 데이터로 실행된다."""

import numpy as np
import pandas as pd
import pytest

from src.evaluation import (
    EvalCase,
    Split,
    classification_metrics,
    mape,
    screening_metrics,
    select_model,
    split_train_valid,
)
from src.features import build_feature_table
from src.preprocess import Dataset, clean_summary
from src.screening import FeatureSet, MahalanobisDetector, conformal_margin, detector_screen, lower_bound
from src.train import ExperimentData
from src.zeroshot import LinearGaussianGenerator, ZeroShotClassifier, select_spec

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


def test_conformal_margin_uses_finite_sample_rank() -> None:
    ratios = np.arange(1, 11) / 100  # 0.01 ~ 0.10, 표본 10개
    assert conformal_margin(ratios, alpha=0.2) == pytest.approx(0.09)  # ceil(11 * 0.8) = 9번째
    assert conformal_margin(ratios, alpha=0.05) == pytest.approx(0.10)  # 순위가 표본 수를 넘으면 최댓값


def test_lower_bound_flags_cells_near_threshold() -> None:
    predicted = np.array([500.0, 600.0, 700.0])
    bound = lower_bound(predicted, margin=np.log10(1.2))
    assert bound == pytest.approx(predicted / 1.2)
    assert (bound < 550).tolist() == [True, True, False]  # 600 은 하한이 500 이라 단수명으로 판정


def test_screening_metrics_report_recall_and_false_alarm() -> None:
    result = screening_metrics(
        true_short=[True, True, False, False], flagged=[True, False, True, False], risk_score=[3, 2, 1, 0]
    )
    assert result["recall_short"] == pytest.approx(0.5)
    assert result["false_alarm"] == pytest.approx(0.5)
    assert result["auc"] == pytest.approx(1.0)


def test_detector_is_fit_on_long_cells_of_the_training_side_only() -> None:
    """평가 셀의 값을 바꿔도 탐지 기준(정상 셀의 분포)이 달라지지 않아야 한다."""
    rng = np.random.default_rng(0)
    keys = pd.Index([f"c{i}" for i in range(30)])
    table = pd.DataFrame({"x": rng.normal(size=30)}, index=keys)
    cells = pd.DataFrame({"cycle_life": 800}, index=keys)
    data = ExperimentData(features=table, cells=cells, split=Split(train=keys[:20], valid=keys[20:]))
    case = EvalCase("valid", keys[:20], keys[20:])

    def flags(eval_value: float) -> np.ndarray:
        changed = table.copy()
        changed.loc[keys[21:], "x"] = eval_value  # 첫 평가 셀(c20)만 그대로 둔다
        return detector_screen(data, FeatureSet("x", changed), MahalanobisDetector)(case).flagged

    assert flags(0.0)[0] == flags(50.0)[0]  # 다른 평가 셀이 달라져도 c20 의 판정은 같다
    assert flags(50.0)[1:].all()  # 정상 범위를 크게 벗어난 값은 이상으로 판정


def _linear_cells(n: int = 40, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    """피처가 log10(수명)에 선형으로 비례하는 합성 셀. 수명은 600 ~ 2000."""
    rng = np.random.default_rng(seed)
    life = pd.Series(np.linspace(600, 2000, n), index=[f"c{i}" for i in range(n)])
    feature = -2.0 * np.log10(life) + rng.normal(0, 0.02, n)
    return pd.DataFrame({"x": feature}), life


def test_generator_recovers_linear_relation_and_extrapolates() -> None:
    X, life = _linear_cells()
    generator = LinearGaussianGenerator.fit(X.to_numpy(), life.to_numpy())
    assert generator.coef[1, 0] == pytest.approx(-2.0, abs=0.1)
    synthetic = generator.sample((150, 550), 500, np.random.default_rng(0))
    assert synthetic.min() > X["x"].max()  # 더 짧은 수명의 피처는 본 셀들의 범위 밖에 만들어진다


def test_zero_shot_classifier_flags_cells_shorter_than_any_training_cell() -> None:
    X, life = _linear_cells()
    model = ZeroShotClassifier(("x",)).fit(X, life)
    unseen = pd.DataFrame({"x": -2.0 * np.log10([300.0, 400.0])})
    seen = pd.DataFrame({"x": -2.0 * np.log10([900.0, 1500.0])})
    assert (model.short_probability(unseen) > 0.5).all()
    assert (model.short_probability(seen) < 0.5).all()


def test_zero_shot_classifier_ignores_cells_below_boundary_when_fitting() -> None:
    """기준선보다 짧은 셀은 학습에 쓰지 않으므로, 그 셀의 값이 달라져도 모델이 같아야 한다."""
    X, life = _linear_cells()
    life.iloc[0] = 400  # 단수명 셀 하나
    tampered = X.copy()
    tampered.iloc[0, 0] = 99.0
    probe = pd.DataFrame({"x": -2.0 * np.log10([500.0, 700.0])})
    original = ZeroShotClassifier(("x",)).fit(X, life).short_probability(probe)
    changed = ZeroShotClassifier(("x",)).fit(tampered, life).short_probability(probe)
    assert original == pytest.approx(changed)


def test_select_spec_prefers_higher_h_then_fewer_features() -> None:
    validation = pd.DataFrame(
        {
            "features": ["a", "a+b", "a+c"],
            "n_features": [1, 2, 2],
            "decision": [0.2, 0.1, 0.3],
            "unseen_recall": [0.8, 0.8, 0.9],
            "seen_accuracy": [0.8, 0.8, 0.9],
            "h": [0.8, 0.8, 0.9],
        }
    )
    assert select_spec(validation).name == "a+c"
    assert select_spec(validation[validation["features"] != "a+c"]).name == "a"  # 동률이면 피처가 적은 쪽
