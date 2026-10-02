"""Zero-shot 분류: 학습에서 본 적 없는 단수명 클래스를 가려내는 이진 분류기.

테스트 결과를 본 뒤에 추가한 실험이므로 공식 성능 표에는 반영하지 않는다.

방법 (생성형 zero-shot. Xian et al., 2018 의 구조를 작은 데이터에 맞게 단순화)
1. 본 클래스(장수명) 셀로 조건부 분포 p(피처 | 수명) 을 학습한다.
2. 본 적 없는 클래스의 정의("수명이 150 이상 550 미만")에서 수명을 뽑아 그 클래스의 피처를 합성한다.
3. 실제 장수명 셀과 합성한 단수명 셀로 이진 분류기를 학습한다.

피처 묶음과 판정 기준은 Batch 1 안에서만 고른다. 수명이 짧은 쪽 일부를 학습에서 숨겨
"가짜 미관측 클래스"로 삼고, 그 셀들을 얼마나 가려내는지로 평가한다 (zero-shot 의 표준 검증 방식).

실행: python -m src.zeroshot
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config, models
from src.evaluation import EvalCase, split_train_valid
from src.screening import Screen, Verdict, all_splits, evaluate_screen
from src.train import ExperimentData, prepare_data

THRESHOLD = config.SHORT_LIFE_THRESHOLD
SHORT_LIFE_FLOOR = 150  # 단수명 클래스의 수명 하한. 가이드가 제시한 수명 범위(150 ~ 2,300)의 하한
N_SYNTHETIC = 2000
# 핵심 피처에 하나씩 더해 볼 후보. 원논문의 후보 피처 중 용량의 절대 수준과 내부저항을 뺀 것이다
CANDIDATE_FEATURES = (
    "log_dq_min",
    "log_dq_mean",
    "log_dq_skew",
    "log_dq_kurt",
    "log_dq_at_2v",
    "qd_fade",
    "qd_rise",
    "qd_slope",
    "qd_slope_late",
    "chargetime_median",
    "tavg_mean",
    "tmax_max",
)
PSEUDO_QUANTILES = (0.25, 0.35, 0.45)  # 가짜 미관측 클래스의 경계: Train 셀 수명의 분위수
DECISIONS = tuple(np.round(np.arange(0.1, 0.91, 0.1), 1))  # 단수명 확률의 판정 기준 후보


@dataclass(frozen=True)
class LinearGaussianGenerator:
    """p(피처 | 수명): 피처를 log10(수명)의 선형 함수에 정규 잡음을 더한 것으로 본다."""

    coef: np.ndarray  # (2, 피처 수). 절편과 기울기
    cov: np.ndarray  # (피처 수, 피처 수). 잔차의 공분산

    @classmethod
    def fit(cls, X: np.ndarray, life: np.ndarray) -> LinearGaussianGenerator:
        design = np.column_stack([np.ones(len(life)), np.log10(life)])
        coef, *_ = np.linalg.lstsq(design, X, rcond=None)
        residual = X - design @ coef
        return cls(coef=coef, cov=np.atleast_2d(np.cov(residual, rowvar=False, ddof=2)))

    def sample(self, life_range: tuple[float, float], n: int, rng: np.random.Generator) -> np.ndarray:
        """수명을 life_range 에서 로그 균등으로 뽑고, 그 수명에서의 피처를 합성한다."""
        log_life = rng.uniform(np.log10(life_range[0]), np.log10(life_range[1]), n)
        mean = np.column_stack([np.ones(n), log_life]) @ self.coef
        return mean + rng.multivariate_normal(np.zeros(self.cov.shape[0]), self.cov, n)


@dataclass(frozen=True)
class ZeroShotSpec:
    features: tuple[str, ...]
    decision: float = 0.5  # 단수명 확률이 이 값 이상이면 단수명으로 판정

    @property
    def name(self) -> str:
        return "+".join(self.features)


class ZeroShotClassifier:
    """실제 본 클래스 셀과 합성한 미관측 클래스 셀로 학습하는 이진 분류기."""

    def __init__(self, features: tuple[str, ...], boundary: float = THRESHOLD, seed: int = config.SEED) -> None:
        self.features, self.boundary, self.seed = list(features), boundary, seed

    def fit(self, X: pd.DataFrame, life: pd.Series) -> ZeroShotClassifier:
        """수명이 boundary 이상인 셀만 사용한다. 그보다 짧은 셀은 학습에 쓰지 않는다."""
        seen = (life >= self.boundary).to_numpy()
        real = X.loc[seen, self.features].to_numpy()
        generator = LinearGaussianGenerator.fit(real, life[seen].to_numpy())
        # 미관측 클래스의 정의: 수명이 boundary 미만. 하한은 기준선 대비 같은 비율로 둔다
        unseen_range = (self.boundary * SHORT_LIFE_FLOOR / THRESHOLD, self.boundary)
        synthetic = generator.sample(unseen_range, N_SYNTHETIC, np.random.default_rng(self.seed))
        features = np.vstack([real, synthetic])
        is_unseen = np.r_[np.zeros(len(real)), np.ones(len(synthetic))]
        classifier = LogisticRegression(class_weight="balanced", max_iter=2000)
        self.model_ = make_pipeline(StandardScaler(), classifier).fit(features, is_unseen)
        return self

    def short_probability(self, X: pd.DataFrame) -> np.ndarray:
        return self.model_.predict_proba(X[self.features].to_numpy())[:, 1]


# --------------------------------------------------------------------------- #
# 가짜 미관측 클래스 검증: 피처 묶음과 판정 기준을 Batch 1 Train 셀만으로 고른다
# --------------------------------------------------------------------------- #
def pseudo_unseen_probabilities(
    X: pd.DataFrame, life: pd.Series, features: tuple[str, ...], boundary: float, seed: int = config.SEED
) -> tuple[np.ndarray, np.ndarray]:
    """수명이 boundary 미만인 셀을 숨기고 학습했을 때의 (숨긴 셀의 단수명 확률, 본 셀의 교차검증 단수명 확률)."""
    hidden = (life < boundary).to_numpy()
    X_seen, life_seen = X[~hidden], life[~hidden]
    hidden_prob = ZeroShotClassifier(features, boundary, seed).fit(X_seen, life_seen).short_probability(X[hidden])
    seen_prob = np.empty(len(life_seen))
    for fit_idx, eval_idx in KFold(n_splits=5, shuffle=True, random_state=seed).split(X_seen):
        model = ZeroShotClassifier(features, boundary, seed).fit(X_seen.iloc[fit_idx], life_seen.iloc[fit_idx])
        seen_prob[eval_idx] = model.short_probability(X_seen.iloc[eval_idx])
    return hidden_prob, seen_prob


def validate_candidates(
    X: pd.DataFrame, life: pd.Series, feature_sets: list[tuple[str, ...]], seed: int = config.SEED
) -> pd.DataFrame:
    """피처 묶음과 판정 기준마다 미관측 검출률, 본 클래스 정확도, 둘의 조화평균(H)을 구한다. 경계 여러 개의 평균이다."""
    rows = []
    for features in feature_sets:
        scores = []
        for quantile in PSEUDO_QUANTILES:
            hidden_prob, seen_prob = pseudo_unseen_probabilities(X, life, features, life.quantile(quantile), seed)
            for decision in DECISIONS:
                recall, accuracy = (hidden_prob >= decision).mean(), (seen_prob < decision).mean()
                harmonic = 2 * recall * accuracy / (recall + accuracy) if recall + accuracy > 0 else 0.0
                scores.append({"decision": decision, "unseen_recall": recall, "seen_accuracy": accuracy, "h": harmonic})
        mean = pd.DataFrame(scores).groupby("decision", as_index=False).mean()
        rows.append(mean.assign(features="+".join(features), n_features=len(features)))
    return pd.concat(rows, ignore_index=True)[
        ["features", "n_features", "decision", "unseen_recall", "seen_accuracy", "h"]
    ]


def best_decisions(validation: pd.DataFrame) -> pd.DataFrame:
    """피처 묶음마다 H 가 가장 높은 판정 기준. 동률이면 0.5 에 가까운 쪽."""
    ranked = validation.assign(distance=(validation["decision"] - 0.5).abs()).sort_values(
        ["h", "distance"], ascending=[False, True]
    )
    return ranked.groupby("features", sort=False).head(1).drop(columns="distance").reset_index(drop=True)


def select_spec(validation: pd.DataFrame) -> ZeroShotSpec:
    """H 가 가장 높은 조합. 동률이면 피처가 적은 쪽."""
    best = best_decisions(validation).sort_values(["h", "n_features"], ascending=[False, True]).iloc[0]
    return ZeroShotSpec(tuple(best["features"].split("+")), float(best["decision"]))


# --------------------------------------------------------------------------- #
# 평가
# --------------------------------------------------------------------------- #
def zero_shot_screen(data: ExperimentData, spec: ZeroShotSpec, seed: int = config.SEED) -> Screen:
    def screen(case: EvalCase) -> Verdict:
        X, life = data.features.loc[case.fit_keys], data.cells.loc[case.fit_keys, "cycle_life"]
        probability = (
            ZeroShotClassifier(spec.features, seed=seed)
            .fit(X, life)
            .short_probability(data.features.loc[case.eval_keys])
        )
        return Verdict(probability >= spec.decision, probability)

    return screen


def performance_table(data: ExperimentData, specs: dict[str, ZeroShotSpec], seed: int = config.SEED) -> pd.DataFrame:
    """구성별 선별 성능. Train 은 leave-one-out, Valid 는 Train 셀로, 테스트는 Batch 1 전체로 학습한다."""
    cycle_life = data.cells["cycle_life"]
    splits = all_splits(data)
    return pd.DataFrame(
        [
            {"config": label, "features": spec.name, "decision": spec.decision, "split": split}
            | evaluate_screen(zero_shot_screen(data, spec, seed), cases, cycle_life)
            for label, spec in specs.items()
            for split, cases in splits.items()
        ]
    )


def candidate_feature_sets() -> list[tuple[str, ...]]:
    """핵심 피처 하나, 그리고 핵심 피처에 후보를 하나씩 더한 묶음."""
    core = (models.CORE_FEATURE,)
    return [core] + [(*core, extra) for extra in CANDIDATE_FEATURES]


def validate_on_train(data: ExperimentData, seed: int = config.SEED) -> pd.DataFrame:
    """Batch 1 의 Train 셀만으로 가짜 미관측 클래스 검증을 수행한다."""
    train = data.split.train
    return validate_candidates(
        data.features.loc[train], data.cells.loc[train, "cycle_life"], candidate_feature_sets(), seed
    )


def selection_stability(data: ExperimentData, seeds: range = range(10)) -> pd.DataFrame:
    """Train / Valid 분할과 난수를 바꿔 가며 어떤 조합이 선택되고 성능이 얼마나 달라지는지 본다."""
    train_life = data.cells.loc[data.train_batch_keys, "cycle_life"]
    rows = []
    for seed in seeds:
        trial = replace(data, split=split_train_valid(train_life, seed=seed))
        spec = select_spec(validate_on_train(trial, seed))
        accuracy = performance_table(trial, {"selected": spec}, seed).set_index("split")["accuracy"]
        rows.append({"seed": seed, "features": spec.name, "decision": spec.decision} | accuracy.to_dict())
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Zero-shot 분류 실험 (사후 추가 실험)")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--out", type=Path, default=config.RESULTS_DIR)
    args = parser.parse_args()

    data = prepare_data(args.seed)
    validation = validate_on_train(data, args.seed)
    selected = select_spec(validation)

    best = best_decisions(validation).set_index("features")
    specs = {"core, decision 0.5": ZeroShotSpec((models.CORE_FEATURE,)), "selected": selected}
    specs |= {  # 선택되지 않은 조합도 같은 방식으로 평가해 공개한다. 선택에는 쓰지 않는다
        f"candidate: {name}": ZeroShotSpec(tuple(name.split("+")), float(row["decision"]))
        for name, row in best.iterrows()
        if name != selected.name
    }
    performance = performance_table(data, specs, args.seed)
    stability = selection_stability(data)

    args.out.mkdir(parents=True, exist_ok=True)
    validation.round(3).to_csv(args.out / "zeroshot_validation.csv", index=False)
    performance.round(3).to_csv(args.out / "zeroshot_performance.csv", index=False)
    stability.round(3).to_csv(args.out / "zeroshot_stability.csv", index=False)
    pd.set_option("display.width", 220)
    print(
        "[가짜 미관측 클래스 검증 : 피처 묶음별 최선의 판정 기준]\n",
        best.round(3).sort_values("h", ascending=False).to_string(),
    )
    print(f"\n[선택] 피처 = {selected.name}, 판정 기준 = {selected.decision}")
    shown = performance[performance["config"].isin(["core, decision 0.5", "selected"])]
    print("\n[성능]\n", shown.round(3).to_string(index=False))
    print("\n[분할을 바꿨을 때의 선택과 Accuracy]\n", stability.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
