"""테스트 결과를 본 뒤의 사후 분석.

여기서 나온 수치는 테스트 라벨을 보고 세운 가설의 검증이므로 공식 성능 표
(results/model_performance.csv)에는 반영하지 않는다.

실행: python -m src.analysis
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold

from src import config, models
from src.evaluation import classification_metrics, fold_scores, mape, split_train_valid, stratified_folds
from src.features import delta_q
from src.models import ModelSpec
from src.preprocess import Dataset, load_dataset
from src.train import INCUMBENT, ExperimentData, build_candidates, evaluate_candidates, predict_splits, prepare_data

POSTHOC_FEATURES = ("qd_rise", "qd_initial")  # 오차 진단 후에 떠올린 피처
CALIBRATION_SIZES = (1, 3, 5, 10)
REFERENCE_CYCLES = (3, 5, 10, 20, 30, 40)  # ΔQ(V) = Q_100 - Q_early 의 early 후보


def _incumbent(data: ExperimentData) -> ModelSpec:
    return next(s for s in build_candidates(data.features) if s.name == INCUMBENT)


def batch_bias(predictions: pd.DataFrame) -> pd.DataFrame:
    """그룹별 예측 편향. bias 는 log10(예측 / 실제)의 평균이고, 양수면 수명을 길게 예측한 것이다."""
    log_ratio = np.log10(predictions["predicted"] / predictions["cycle_life"])
    structure = np.where(predictions["policy"].str.contains("newstructure"), "newstructure", "general")
    group = predictions["split"] + " / " + structure
    rows = []
    for name, idx in predictions.groupby(group).groups.items():
        g, bias = predictions.loc[idx], log_ratio[idx].mean()
        rows.append(
            {
                "group": name,
                "n": len(g),
                "bias_log10": bias,
                "predicted_over_actual": 10**bias,
                "mape": mape(g["cycle_life"], g["predicted"]),
                # 편향을 정확히 안다고 가정하고 제거했을 때의 오차. 남는 것은 셀 간 변동이다
                "mape_bias_removed": mape(g["cycle_life"], g["predicted"] / 10**bias),
            }
        )
    return pd.DataFrame(rows)


def reference_cycle_scan(dataset: Dataset, early_cycles: tuple[int, ...] = REFERENCE_CYCLES) -> pd.DataFrame:
    """ΔQ(V) 의 기준 사이클을 바꿔도 테스트 배치의 편향이 남는지 본다.

    정의마다 Batch 1 전체에 log-log 직선을 맞추고, 테스트 배치의 평균 log10(예측 / 실제)를 구한다.
    """
    cells = dataset.cells
    log_life = np.log10(cells["cycle_life"].to_numpy())
    train = (cells["batch"] == config.TRAIN_BATCH).to_numpy()
    rows = []
    for early in early_cycles:
        x = np.log10(np.var(delta_q(dataset, late=dataset.n_cycles, early=early), axis=1))
        slope, intercept = np.polyfit(x[train], log_life[train], 1)
        log_ratio = slope * x + intercept - log_life
        row = {"early_cycle": early}
        for batch in (config.TEST_BATCH, config.EXTRA_TEST_BATCH):
            in_batch = (cells["batch"] == batch).to_numpy()
            row[f"bias_log10 ({batch})"] = log_ratio[in_batch].mean()
            row[f"mape ({batch})"] = mape(10 ** log_life[in_batch], 10 ** (log_life + log_ratio)[in_batch])
        rows.append(row)
    return pd.DataFrame(rows)


def posthoc_feature_models(data: ExperimentData, seed: int = config.SEED) -> pd.DataFrame:
    """사후 피처를 핵심 피처에 더했을 때의 CV / Valid / Test MAPE."""
    specs = [_incumbent(data)] + [
        ModelSpec(f"linear[core+{f}]", "linear", (models.CORE_FEATURE, f), LinearRegression) for f in POSTHOC_FEATURES
    ]
    return evaluate_candidates(specs, data, seed)


def few_shot_calibration(
    predictions: pd.DataFrame, sizes: tuple[int, ...] = CALIBRATION_SIZES, n_draws: int = 500, seed: int = config.SEED
) -> pd.DataFrame:
    """새 배치에서 수명이 확인된 셀 k 개로 예측의 기준선(절편)만 보정했을 때의 성능.

    보정에 쓴 k 개를 뺀 나머지 셀로 평가하고, 무작위 추출을 n_draws 번 반복해 평균한다.
    테스트 라벨을 쓰는 분석이므로 테스트 성능이 아니라 현장 적용 시나리오의 추정치다.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for split, g in predictions[predictions["split"] != "valid"].groupby("split"):
        y, log_ratio = g["cycle_life"].to_numpy(), np.log10(g["predicted"] / g["cycle_life"]).to_numpy()
        rows.append({"split": split, "k": 0, "mape": mape(y, g["predicted"]), **_accuracy(y, g["predicted"])})
        for k in sizes:
            scores = []
            for _ in range(n_draws):
                picked = rng.choice(len(g), size=k, replace=False)
                rest = np.setdiff1d(np.arange(len(g)), picked)
                calibrated = g["predicted"].to_numpy()[rest] / 10 ** log_ratio[picked].mean()
                scores.append({"mape": mape(y[rest], calibrated), **_accuracy(y[rest], calibrated)})
            rows.append({"split": split, "k": k, **pd.DataFrame(scores).mean().to_dict()})
    return pd.DataFrame(rows)


def _accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {"accuracy": classification_metrics(y_true, y_pred)["accuracy"]}


def split_sensitivity(data: ExperimentData, seeds: range = range(20)) -> pd.DataFrame:
    """Hold-out 분할을 바꿔 가며 기준 모델의 CV / Valid MAPE 가 얼마나 흔들리는지 본다."""
    spec = _incumbent(data)
    train_life = data.cells.loc[data.train_batch_keys, "cycle_life"]
    rows = []
    for seed in seeds:
        trial = replace(data, split=split_train_valid(train_life, seed=seed))
        X, y = trial.features.loc[trial.split.train], trial.cells.loc[trial.split.train, "cycle_life"]
        valid = predict_splits(spec, trial).query("split == 'valid'")
        rows.append(
            {
                "seed": seed,
                "cv_mape": fold_scores(spec, X, y, stratified_folds(y, seed=seed)).mean(),
                "valid_mape": mape(valid["cycle_life"], valid["predicted"]),
            }
        )
    return pd.DataFrame(rows)


def policy_grouped_cv(data: ExperimentData, n_splits: int = 5) -> float:
    """같은 충전 정책의 셀이 학습과 검증에 나뉘지 않게 묶은 CV 의 MAPE (기준 모델)."""
    train = data.split.train
    X, y = data.features.loc[train], data.cells.loc[train, "cycle_life"]
    folds = list(GroupKFold(n_splits=n_splits).split(X, y, groups=data.cells.loc[train, "policy"]))
    return float(fold_scores(_incumbent(data), X, y, folds).mean())


def main() -> None:
    parser = argparse.ArgumentParser(description="사후 분석: 오차 진단과 새 가설 검증")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--out", type=Path, default=config.RESULTS_DIR)
    args = parser.parse_args()

    data = prepare_data(args.seed)
    predictions = predict_splits(_incumbent(data), data)
    tables = {
        "posthoc_batch_bias": batch_bias(predictions),
        "posthoc_reference_cycle": reference_cycle_scan(load_dataset()),
        "posthoc_feature_models": posthoc_feature_models(data, args.seed),
        "posthoc_calibration": few_shot_calibration(predictions, seed=args.seed),
        "posthoc_split_sensitivity": split_sensitivity(data),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    for name, table in tables.items():
        table.round(3).to_csv(args.out / f"{name}.csv", index=False)
        print(f"\n[{name}]\n", table.round(3).to_string(index=False))
    sens = tables["posthoc_split_sensitivity"]
    print(
        f"\n분할 20회 : CV {sens['cv_mape'].mean():.2f} ± {sens['cv_mape'].std():.2f}, "
        f"Valid {sens['valid_mape'].mean():.2f} ± {sens['valid_mape'].std():.2f}"
    )
    print(f"정책 단위로 묶은 CV MAPE : {policy_grouped_cv(data):.2f}")


if __name__ == "__main__":
    main()
