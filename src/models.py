"""후보 모델 정의.

모든 모델은 log10(cycle_life) 를 학습하고, 예측값은 원래 단위(사이클)로 되돌려 반환한다.
스케일링은 파이프라인 안에 있어 학습 데이터에서만 기준을 구한다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from sklearn.base import RegressorMixin
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNetCV, LinearRegression, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config

CORE_FEATURE = "log_dq_var"


def _power10(x: np.ndarray) -> np.ndarray:
    return np.power(10.0, x)


@dataclass(frozen=True)
class ModelSpec:
    """후보 모델 하나. 어떤 피처를 어떤 추정기에 넣는지를 정의한다."""

    name: str
    family: str  # baseline / linear / regularized / tree
    features: tuple[str, ...]
    make_regressor: Callable[[], RegressorMixin]

    def build(self) -> TransformedTargetRegressor:
        return TransformedTargetRegressor(
            regressor=make_pipeline(StandardScaler(), self.make_regressor()),
            func=np.log10,
            inverse_func=_power10,
        )


def _ridge() -> RegressorMixin:
    return RidgeCV(alphas=np.logspace(-3, 3, 25))


def _elastic_net() -> RegressorMixin:
    return ElasticNetCV(l1_ratio=[0.1, 0.5, 0.9], cv=5, max_iter=50_000, random_state=config.SEED)


def _random_forest() -> RegressorMixin:
    return RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=config.SEED)


def _gradient_boosting() -> RegressorMixin:
    return GradientBoostingRegressor(
        n_estimators=200, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=config.SEED
    )


def baseline_models() -> list[ModelSpec]:
    """비교 기준: 평균 예측과 핵심 피처 하나만 쓴 선형 회귀."""
    return [
        ModelSpec("mean", "baseline", (CORE_FEATURE,), lambda: DummyRegressor(strategy="mean")),
        ModelSpec("linear[core]", "linear", (CORE_FEATURE,), LinearRegression),
    ]


def single_feature_swaps(alternatives: tuple[str, ...]) -> list[ModelSpec]:
    """핵심 피처를 다른 정의로 바꾼 선형 회귀."""
    return [ModelSpec(f"linear[{alt}]", "linear", (alt,), LinearRegression) for alt in alternatives]


def auxiliary_feature_models(aux_features: tuple[str, ...]) -> list[ModelSpec]:
    """핵심 피처에 보조 피처를 하나씩 더한 선형 회귀. 보조 피처의 효과를 따로 확인한다."""
    return [ModelSpec(f"linear[core+{aux}]", "linear", (CORE_FEATURE, aux), LinearRegression) for aux in aux_features]


def multi_feature_models(features: tuple[str, ...]) -> list[ModelSpec]:
    """같은 피처 묶음에 대한 규제 선형 모델과 트리 모델."""
    return [
        ModelSpec("ridge[all]", "regularized", features, _ridge),
        ModelSpec("elastic_net[all]", "regularized", features, _elastic_net),
        ModelSpec("random_forest[all]", "tree", features, _random_forest),
        ModelSpec("gradient_boosting[all]", "tree", features, _gradient_boosting),
    ]
