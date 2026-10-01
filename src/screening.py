"""단수명 셀 선별: 단수명 예시 없이 수명이 기준선(550 사이클) 미만인 셀을 가려낸다.

테스트 결과를 본 뒤에 추가한 실험이므로 공식 성능 표에는 반영하지 않는다.

방법
- threshold   : 예측 수명이 기준선 미만이면 단수명 (기존 방식)
- lower_bound : 예측 수명의 하한이 기준선 미만이면 단수명. 하한의 여유는 학습 셀의
                leave-one-out 잔차 분위수로 정한다 (conformal prediction)
- one-class   : Batch 1 장수명 셀의 분포에서 벗어나면 단수명 (이상 탐지)
- cluster     : 평가할 배치의 예측 수명을 군집으로 나눠 군집 단위로 판정한다.
                평가 대상의 피처를 함께 쓰는 transductive 설정이다

실행: python -m src.screening
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.covariance import EmpiricalCovariance
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import LeaveOneOut
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from src import config, models, report
from src.evaluation import EvalCase, fit_predict, screening_metrics
from src.features import delta_q
from src.models import ModelSpec
from src.preprocess import Dataset, load_dataset
from src.train import INCUMBENT, ExperimentData, build_candidates, evaluation_cases, prepare_data

THRESHOLD = config.SHORT_LIFE_THRESHOLD
SENSITIVITY_ALPHAS = (0.2, 0.1, 0.05)
SUMMARY_FEATURES = (models.CORE_FEATURE, "qd_rise", "qd_initial", "chargetime_median", "tavg_mean")
NORMAL_ACCEPT_RATE = 0.95  # 탐지기의 판정 기준: 학습한 정상 셀의 95% 를 정상으로 받아들이는 점수


@dataclass(frozen=True)
class Verdict:
    flagged: np.ndarray  # 단수명으로 판정했는가
    risk_score: np.ndarray  # 클수록 단수명일 가능성이 높다고 본 점수


Screen = Callable[[EvalCase], Verdict]


# --------------------------------------------------------------------------- #
# 예측 하한 (conformal prediction)
# --------------------------------------------------------------------------- #
def loo_log_ratios(spec: ModelSpec, X: pd.DataFrame, y: pd.Series) -> np.ndarray:
    """leave-one-out 예측의 log10(예측 / 실제). 양수면 수명을 길게 예측한 것이다."""
    out = np.empty(len(y))
    for train_idx, test_idx in LeaveOneOut().split(X):
        predicted = fit_predict(spec, X.iloc[train_idx], y.iloc[train_idx], X.iloc[test_idx])
        out[test_idx] = np.log10(predicted / y.iloc[test_idx].to_numpy())
    return out


def conformal_margin(log_ratios: np.ndarray, alpha: float) -> float:
    """과대 예측 폭의 (1 - alpha) 분위수. 표본이 n 개일 때 ceil((n + 1)(1 - alpha)) 번째로 작은 값을 쓴다."""
    n = len(log_ratios)
    rank = min(math.ceil((n + 1) * (1 - alpha)), n)
    return float(np.sort(log_ratios)[rank - 1])


def lower_bound(predicted: np.ndarray, margin: float) -> np.ndarray:
    """예측 수명을 여유만큼 낮춘 하한 (사이클)."""
    return predicted / 10**margin


class Predictor:
    """평가 건마다 예측 수명과 학습 셀의 leave-one-out 잔차를 한 번만 계산해 둔다."""

    def __init__(self, data: ExperimentData, spec: ModelSpec) -> None:
        self._data, self._spec = data, spec
        self._cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}

    def __call__(self, case: EvalCase) -> tuple[np.ndarray, np.ndarray]:
        """(평가 셀의 예측 수명, 학습 셀의 leave-one-out log10(예측 / 실제))."""
        key = (tuple(case.fit_keys), tuple(case.eval_keys))
        if key not in self._cache:
            X = self._data.features.loc[case.fit_keys]
            y = self._data.cells.loc[case.fit_keys, "cycle_life"]
            predicted = fit_predict(self._spec, X, y, self._data.features.loc[case.eval_keys])
            self._cache[key] = (predicted, loo_log_ratios(self._spec, X, y))
        return self._cache[key]


def threshold_screen(predict: Predictor) -> Screen:
    def screen(case: EvalCase) -> Verdict:
        predicted, _ = predict(case)
        return Verdict(predicted < THRESHOLD, -predicted)

    return screen


def lower_bound_screen(predict: Predictor, alpha: float) -> Screen:
    def screen(case: EvalCase) -> Verdict:
        predicted, log_ratios = predict(case)
        return Verdict(lower_bound(predicted, conformal_margin(log_ratios, alpha)) < THRESHOLD, -predicted)

    return screen


def cluster_screen(predict: Predictor, alpha: float) -> Screen:
    """평가 셀들의 예측 수명을 1개 또는 2개 군집으로 나누고, 군집 평균의 하한으로 군집 전체를 판정한다."""

    def screen(case: EvalCase) -> Verdict:
        predicted, log_ratios = predict(case)
        log_predicted = np.log10(predicted)
        labels = _cluster_labels(log_predicted)
        cluster_mean = pd.Series(log_predicted).groupby(labels).transform("mean").to_numpy()
        bound = lower_bound(10**cluster_mean, conformal_margin(log_ratios, alpha))
        return Verdict(bound < THRESHOLD, -predicted)

    return screen


def _cluster_labels(values: np.ndarray) -> np.ndarray:
    """BIC 가 더 낮은 쪽(군집 1개 또는 2개)의 군집 번호."""
    column = values.reshape(-1, 1)
    fits = [GaussianMixture(k, random_state=config.SEED).fit(column) for k in (1, 2)]
    return min(fits, key=lambda g: g.bic(column)).predict(column)


# --------------------------------------------------------------------------- #
# One-class 탐지기 (이상 탐지)
# --------------------------------------------------------------------------- #
class MahalanobisDetector(BaseEstimator):
    """정상 셀의 평균과 공분산에서 얼마나 떨어져 있는가."""

    def fit(self, X: np.ndarray, y: None = None) -> MahalanobisDetector:
        self.covariance_ = EmpiricalCovariance().fit(X)
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        return -self.covariance_.mahalanobis(X)


DETECTORS: dict[str, Callable[[], BaseEstimator]] = {
    "mahalanobis": MahalanobisDetector,
    "isolation_forest": lambda: IsolationForest(n_estimators=300, random_state=config.SEED),
    "one_class_svm": lambda: OneClassSVM(nu=0.05, gamma="scale"),
    "local_outlier_factor": lambda: LocalOutlierFactor(n_neighbors=10, novelty=True),
}


@dataclass(frozen=True)
class FeatureSet:
    name: str
    table: pd.DataFrame  # index=cell_key
    n_components: int | None = None  # 지정하면 PCA 로 줄인 뒤 탐지기에 넣는다


def detector_feature_sets(data: ExperimentData, dataset: Dataset) -> list[FeatureSet]:
    early = dataset.early_window(config.EARLY_CYCLES)
    curves = pd.DataFrame(delta_q(early, late=early.n_cycles, early=10), index=early.cells.index)
    return [
        FeatureSet("dq_var", data.features[[models.CORE_FEATURE]]),
        FeatureSet("summary", data.features[list(SUMMARY_FEATURES)]),
        FeatureSet("dq_curve_pca", curves, n_components=5),
    ]


def detector_screen(
    data: ExperimentData, feature_set: FeatureSet, make_detector: Callable[[], BaseEstimator]
) -> Screen:
    """학습 셀 중 장수명 셀만 정상으로 학습한다. 스케일러와 PCA 도 그 셀들로만 맞춘다."""

    def screen(case: EvalCase) -> Verdict:
        is_long = data.cells.loc[case.fit_keys, "cycle_life"] >= THRESHOLD
        normal = feature_set.table.loc[case.fit_keys[is_long.to_numpy()]]
        reducer = [PCA(feature_set.n_components)] if feature_set.n_components else []
        pipeline = make_pipeline(*reducer, StandardScaler(), make_detector()).fit(normal)
        cutoff = np.quantile(-pipeline.score_samples(normal), NORMAL_ACCEPT_RATE)
        anomaly = -pipeline.score_samples(feature_set.table.loc[case.eval_keys])
        return Verdict(anomaly > cutoff, anomaly)

    return screen


# --------------------------------------------------------------------------- #
# 평가
# --------------------------------------------------------------------------- #
def leave_one_out_cases(data: ExperimentData) -> list[EvalCase]:
    """Train 셀을 하나씩 빼고 나머지로 학습해 그 셀을 평가한다."""
    train = data.split.train
    return [EvalCase("train_loo", train.drop(key), pd.Index([key])) for key in train]


def evaluate_screen(screen: Screen, cases: list[EvalCase], cycle_life: pd.Series) -> dict:
    """여러 평가 건의 판정을 모아 성능을 구한다."""
    verdicts = [screen(case) for case in cases]
    keys = np.concatenate([case.eval_keys for case in cases])
    return screening_metrics(
        true_short=cycle_life.loc[keys].to_numpy() < THRESHOLD,
        flagged=np.concatenate([v.flagged for v in verdicts]),
        risk_score=np.concatenate([v.risk_score for v in verdicts]),
    )


def performance_table(
    data: ExperimentData, dataset: Dataset, predict: Predictor, alpha: float = config.SCREENING_ALPHA
) -> pd.DataFrame:
    """방법별 선별 성능. train_loo 는 예측 수명을 쓰는 방법에만 계산한다."""
    held_out = {case.name: [case] for case in evaluation_cases(data)}
    with_train = {"train_loo": leave_one_out_cases(data), **held_out}
    level = f"{1 - alpha:.0%}"
    methods: list[tuple[str, Screen, dict[str, list[EvalCase]]]] = [
        ("threshold", threshold_screen(predict), with_train),
        (f"lower_bound[{level}]", lower_bound_screen(predict, alpha), with_train),
        (f"cluster+lower_bound[{level}]", cluster_screen(predict, alpha), held_out),
    ]
    methods += [
        (f"{detector}[{feature_set.name}]", detector_screen(data, feature_set, make_detector), held_out)
        for feature_set in detector_feature_sets(data, dataset)
        for detector, make_detector in DETECTORS.items()
    ]
    cycle_life = data.cells["cycle_life"]
    return pd.DataFrame(
        [
            {"method": name, "split": split, **evaluate_screen(screen, cases, cycle_life)}
            for name, screen, splits in methods
            for split, cases in splits.items()
        ]
    )


def sensitivity_table(
    data: ExperimentData, predict: Predictor, alphas: tuple[float, ...] = SENSITIVITY_ALPHAS
) -> pd.DataFrame:
    """하한의 수준을 바꿨을 때의 성능. margin_factor 는 예측 수명을 나누는 배율이다."""
    splits = {"train_loo": leave_one_out_cases(data), **{case.name: [case] for case in evaluation_cases(data)}}
    cycle_life = data.cells["cycle_life"]
    rows = []
    for alpha in alphas:
        screen = lower_bound_screen(predict, alpha)
        for split, cases in splits.items():
            margin = np.mean([conformal_margin(predict(case)[1], alpha) for case in cases])
            rows.append(
                {"level": 1 - alpha, "split": split, "margin_factor": 10**margin}
                | evaluate_screen(screen, cases, cycle_life)
            )
    return pd.DataFrame(rows)


def lower_bound_predictions(
    data: ExperimentData, predict: Predictor, alpha: float = config.SCREENING_ALPHA
) -> pd.DataFrame:
    """Valid 와 테스트 셀의 예측 수명, 하한, 판정."""
    frames = []
    for case in evaluation_cases(data):
        predicted, log_ratios = predict(case)
        bound = lower_bound(predicted, conformal_margin(log_ratios, alpha))
        frame = data.cells.loc[case.eval_keys, ["batch", "policy", "cycle_life"]]
        frames.append(frame.assign(split=case.name, predicted=predicted, lower_bound=bound, flagged=bound < THRESHOLD))
    return pd.concat(frames)


def main() -> None:
    parser = argparse.ArgumentParser(description="단수명 셀 선별 실험 (사후 추가 실험)")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--out", type=Path, default=config.RESULTS_DIR)
    args = parser.parse_args()

    data = prepare_data(args.seed)
    predict = Predictor(data, next(s for s in build_candidates(data.features) if s.name == INCUMBENT))
    tables = {
        "screening_performance": performance_table(data, load_dataset(), predict),
        "screening_sensitivity": sensitivity_table(data, predict),
    }
    predictions = lower_bound_predictions(data, predict)

    (args.out / "figures").mkdir(parents=True, exist_ok=True)
    predictions.round(2).to_csv(args.out / "screening_predictions.csv")
    report.plot_lower_bounds(predictions, args.out / "figures" / "screening_lower_bound.png")
    pd.set_option("display.width", 220)
    for name, table in tables.items():
        table.round(3).to_csv(args.out / f"{name}.csv", index=False)
        print(f"\n[{name}]\n", table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
