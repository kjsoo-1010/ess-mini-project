"""분할, 교차검증, 지표 계산.

평가 절차
1. Batch 1 을 셀 단위로 Train / Valid(Hold-out) 로 나눈다.
2. Train 안에서 반복 교차검증으로 후보 모델을 비교하고 하나를 고른다.
3. Train 으로 학습한 모델을 Valid 에서 확인한다.
4. Batch 1 전체로 다시 학습한 모델을 테스트 배치에서 평가한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedShuffleSplit

from src import config
from src.models import ModelSpec


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """평균 절대 백분율 오차 (%)."""
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_pred - y_true) / y_true) * 100)


def life_strata(cycle_life: pd.Series, n_bins: int = 4) -> np.ndarray:
    """수명 구간(분위수) 번호. 분할할 때 장수 셀이 한쪽에 몰리지 않게 하는 데 쓴다."""
    return pd.qcut(cycle_life, q=n_bins, labels=False).to_numpy()


@dataclass(frozen=True)
class Split:
    train: pd.Index
    valid: pd.Index


@dataclass(frozen=True)
class EvalCase:
    """평가 한 건: fit_keys 셀로 학습해 eval_keys 셀을 평가한다."""

    name: str
    fit_keys: pd.Index
    eval_keys: pd.Index


def split_train_valid(cycle_life: pd.Series, valid_size: float = 0.2, seed: int = config.SEED) -> Split:
    """셀 단위 Hold-out 분할. 수명 구간별 비율을 유지한다."""
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=valid_size, random_state=seed)
    train_idx, valid_idx = next(splitter.split(cycle_life, life_strata(cycle_life)))
    return Split(train=cycle_life.index[train_idx], valid=cycle_life.index[valid_idx])


def fit_predict(spec: ModelSpec, X_train: pd.DataFrame, y_train: pd.Series, X_eval: pd.DataFrame) -> np.ndarray:
    """spec 의 피처만 골라 학습하고 X_eval 의 수명(사이클)을 예측한다."""
    model = spec.build().fit(X_train[list(spec.features)], y_train)
    return model.predict(X_eval[list(spec.features)])


Folds = list[tuple[np.ndarray, np.ndarray]]


def stratified_folds(y: pd.Series, n_splits: int = 5, n_repeats: int = 10, seed: int = config.SEED) -> Folds:
    """반복 층화 K-fold. 셀이 적어 분할에 따른 변동이 크므로 여러 번 반복한다."""
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    return list(cv.split(y, life_strata(y)))


def fold_scores(spec: ModelSpec, X: pd.DataFrame, y: pd.Series, folds: Folds) -> np.ndarray:
    """fold 별 검증 MAPE."""
    return np.array(
        [
            mape(y.iloc[valid_idx], fit_predict(spec, X.iloc[train_idx], y.iloc[train_idx], X.iloc[valid_idx]))
            for train_idx, valid_idx in folds
        ]
    )


def compare_models(specs: list[ModelSpec], X: pd.DataFrame, y: pd.Series, seed: int = config.SEED) -> pd.DataFrame:
    """후보 모델의 교차검증 결과 표. cv_mape 오름차순. 모든 후보가 같은 fold 를 쓴다."""
    folds = stratified_folds(y, seed=seed)
    rows = []
    for spec in specs:
        scores = fold_scores(spec, X, y, folds)
        rows.append(
            {
                "model": spec.name,
                "family": spec.family,
                "n_features": len(spec.features),
                "cv_mape": scores.mean(),
                "cv_std": scores.std(ddof=1),
                # 반복 CV 의 fold 는 서로 독립이 아니므로 표준오차는 참고용이다
                "cv_se": scores.std(ddof=1) / np.sqrt(len(scores)),
            }
        )
    return pd.DataFrame(rows).sort_values("cv_mape", ignore_index=True)


def select_model(comparison: pd.DataFrame, incumbent: str) -> str:
    """기준 모델(incumbent)을 유지하되, 표준오차보다 크게 앞서는 후보가 있으면 그중 최선으로 바꾼다.

    셀이 적어 CV 점수의 작은 차이는 우연일 수 있다. 차이가 분명할 때만 더 복잡한 모델을 채택한다.
    """
    table = comparison.set_index("model")
    bar = table.loc[incumbent, "cv_mape"] - table.loc[incumbent, "cv_se"]
    challengers = table[table["cv_mape"] < bar].drop(index=incumbent, errors="ignore")
    return incumbent if challengers.empty else str(challengers["cv_mape"].idxmin())


def screening_metrics(true_short: np.ndarray, flagged: np.ndarray, risk_score: np.ndarray) -> dict:
    """단수명 선별 성능.

    flagged    : 단수명으로 판정했는가
    risk_score : 클수록 단수명일 가능성이 높다고 본 점수. AUC 에만 쓰며 판정 기준선의 위치와 무관하다
    """
    true_short, flagged = np.asarray(true_short, dtype=bool), np.asarray(flagged, dtype=bool)
    has_both = true_short.any() and not true_short.all()
    return {
        "n_long": int((~true_short).sum()),
        "n_short": int(true_short.sum()),
        "accuracy": accuracy_score(true_short, flagged),
        "f1_long": f1_score(~true_short, ~flagged, zero_division=0),
        "f1_short": f1_score(true_short, flagged, zero_division=0),
        "recall_short": flagged[true_short].mean() if true_short.any() else np.nan,  # 단수명 검출률
        "false_alarm": flagged[~true_short].mean() if (~true_short).any() else np.nan,  # 장수명을 단수명으로 판정
        "auc": roc_auc_score(true_short, risk_score) if has_both else np.nan,
    }


def classification_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, threshold: int = config.SHORT_LIFE_THRESHOLD
) -> dict:
    """예측 수명을 기준선으로 나눠 장/단수명 분류 성능을 구한다."""
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    return screening_metrics(y_true < threshold, y_pred < threshold, risk_score=-y_pred)
