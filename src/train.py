"""실험 파이프라인: 로딩 -> 피처 -> 후보 비교 -> 모델 선택 -> 평가 -> 결과 저장.

실행: python -m src.train
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src import config, models, report
from src.evaluation import EvalCase, Split, compare_models, fit_predict, mape, select_model, split_train_valid
from src.features import available_features, build_feature_table
from src.models import ModelSpec
from src.preprocess import load_dataset

# DAY 1 전략에서 정한 후보 구성. 테스트 결과를 본 뒤에는 바꾸지 않는다
INCUMBENT = "linear[core]"  # 기준 모델
CORE_ALTERNATIVES = ("log_dq_var_smooth",)
AUX_FEATURES = ("qd_fade", "chargetime_median", "tavg_mean", "ir_diff")  # 보조 후보 피처
TEST_SPLITS = {"test_b2": config.TEST_BATCH, "test_b3": config.EXTRA_TEST_BATCH}


@dataclass(frozen=True)
class ExperimentData:
    features: pd.DataFrame  # index=cell_key, 세 배치 전체
    cells: pd.DataFrame  # index=cell_key, columns=[batch, cell_id, policy, cycle_life]
    split: Split  # Batch 1 의 Train / Valid 셀

    @property
    def train_batch_keys(self) -> pd.Index:
        return self.cells.index[self.cells["batch"] == config.TRAIN_BATCH]


@dataclass(frozen=True)
class ExperimentResult:
    comparison: pd.DataFrame  # 후보별 CV / Valid / Test MAPE
    selected: str
    predictions: pd.DataFrame  # 선택된 모델의 셀별 예측
    performance: pd.DataFrame  # 가이드 리포팅 포맷
    classification: pd.DataFrame  # 550 사이클 기준 우회 분류


def prepare_data(seed: int = config.SEED) -> ExperimentData:
    dataset = load_dataset()
    cells = dataset.cells
    train_life = cells.loc[cells["batch"] == config.TRAIN_BATCH, "cycle_life"]
    return ExperimentData(
        features=build_feature_table(dataset),
        cells=cells,
        split=split_train_valid(train_life, seed=seed),
    )


def build_candidates(features: pd.DataFrame) -> list[ModelSpec]:
    """모든 배치에서 계산 가능한 피처만으로 후보 모델을 구성한다."""
    usable = available_features(features)
    aux = tuple(f for f in AUX_FEATURES if f in usable)
    return (
        models.baseline_models()
        + models.single_feature_swaps(CORE_ALTERNATIVES)
        + models.auxiliary_feature_models(aux)
        + models.multi_feature_models((models.CORE_FEATURE, *aux))
    )


def evaluation_cases(data: ExperimentData) -> list[EvalCase]:
    """Valid 는 Train 셀로, 테스트 배치는 Batch 1 전체로 학습해 평가한다."""
    cells = data.cells
    tests = [
        EvalCase(name, data.train_batch_keys, cells.index[cells["batch"] == batch])
        for name, batch in TEST_SPLITS.items()
    ]
    return [EvalCase("valid", data.split.train, data.split.valid), *tests]


def predict_splits(spec: ModelSpec, data: ExperimentData) -> pd.DataFrame:
    """평가 건마다 학습과 예측을 수행해 셀별 예측 표를 만든다."""
    X, cells = data.features, data.cells
    y = cells["cycle_life"]
    frames = []
    for case in evaluation_cases(data):
        predicted = fit_predict(spec, X.loc[case.fit_keys], y[case.fit_keys], X.loc[case.eval_keys])
        frame = cells.loc[case.eval_keys, ["batch", "policy", "cycle_life"]].assign(
            split=case.name, predicted=predicted
        )
        frames.append(frame.join(X.loc[case.eval_keys, list(spec.features)]))
    out = pd.concat(frames)
    out["ape"] = (out["predicted"] - out["cycle_life"]).abs() / out["cycle_life"] * 100
    return out


def evaluate_candidates(specs: list[ModelSpec], data: ExperimentData, seed: int = config.SEED) -> pd.DataFrame:
    """후보별 CV 점수에 Valid / Test MAPE 를 붙인다. 모델 선택에는 CV 점수만 쓴다."""
    train = data.split.train
    comparison = compare_models(specs, data.features.loc[train], data.cells.loc[train, "cycle_life"], seed=seed)
    scores = {}
    for spec in specs:
        predictions = predict_splits(spec, data)
        scores[spec.name] = {
            f"{name}_mape": mape(g["cycle_life"], g["predicted"]) for name, g in predictions.groupby("split")
        }
    return comparison.join(pd.DataFrame(scores).T, on="model")


def run_experiment(data: ExperimentData, seed: int = config.SEED) -> ExperimentResult:
    specs = build_candidates(data.features)
    comparison = evaluate_candidates(specs, data, seed)
    selected = select_model(comparison, incumbent=INCUMBENT)
    predictions = predict_splits(next(s for s in specs if s.name == selected), data)
    cv_mape = comparison.set_index("model").loc[selected, "cv_mape"]
    return ExperimentResult(
        comparison=comparison,
        selected=selected,
        predictions=predictions,
        performance=report.performance_table(cv_mape, predictions),
        classification=report.classification_table(predictions),
    )


def save_results(result: ExperimentResult, data: ExperimentData, out_dir: Path) -> None:
    figures = out_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    result.performance.round(2).to_csv(out_dir / "model_performance.csv", index=False)
    result.comparison.round(2).to_csv(out_dir / "model_comparison.csv", index=False)
    result.classification.round(3).to_csv(out_dir / "classification.csv", index=False)
    result.predictions.round(4).to_csv(out_dir / "predictions.csv")
    report.plot_predictions(result.predictions, figures / "observed_vs_predicted.png")
    report.plot_feature_fit(data.features, data.cells, models.CORE_FEATURE, figures / "core_feature_fit.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="ESS 배터리 수명 예측 모델 학습 및 평가")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--out", type=Path, default=config.RESULTS_DIR)
    args = parser.parse_args()

    data = prepare_data(args.seed)
    result = run_experiment(data, args.seed)
    save_results(result, data, args.out)

    pd.set_option("display.width", 200)
    print("[후보 모델 비교]\n", result.comparison.round(2).to_string(index=False))
    print(f"\n[선택된 모델] {result.selected}")
    print("\n[성능]\n", result.performance.round(2).to_string(index=False))
    print("\n[우회 분류 : 550 사이클 기준]\n", result.classification.round(3).to_string(index=False))
    print("\n[오차가 큰 셀]\n", report.worst_cells(result.predictions).round(2).to_string())


if __name__ == "__main__":
    main()
