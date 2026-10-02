"""원논문(Severson et al., 2019)의 세 모델 구성을 이 데이터셋에서 다시 만들어 비교한다.

원논문의 성능은 학습·평가 데이터가 달라 이 프로젝트의 수치와 직접 비교할 수 없다.
그래서 원논문의 피처 정의와 모델 구성을 따라 구현하고, 같은 데이터(Batch 1 학습)에서 평가한다.
원논문의 모델링 코드는 공개되어 있지 않으므로 세부 설정까지 같다고 볼 수는 없다.
테스트 결과를 본 뒤에 추가한 비교이며 공식 성능 표에는 반영하지 않는다.

실행: python -m src.replication
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config, models
from src.evaluation import EvalCase, split_train_valid
from src.features import build_feature_table
from src.models import ModelSpec
from src.preprocess import load_dataset
from src.screening import Screen, Verdict, evaluate_screen
from src.train import ExperimentData, evaluate_candidates, evaluation_cases, prepare_data

# 원논문 Supplementary Table 1 의 후보 피처 20개
DELTA_Q = ("log_dq_min", "log_dq_mean", "log_dq_var", "log_dq_skew", "log_dq_kurt", "log_dq_at_2v")
FADE_CURVE = (
    "qd_slope",
    "qd_intercept",
    "qd_slope_late",
    "qd_intercept_late",
    "qd_initial",
    "qd_rise",
    "qd_last",
)
TEMPERATURE_AND_TIME = ("chargetime_first5", "tmax_max", "tmin_min", "temp_integral")
RESISTANCE = ("ir_initial", "ir_min", "ir_diff")

PAPER_MODELS = (
    ModelSpec("Variance", "linear", (models.CORE_FEATURE,), LinearRegression),
    ModelSpec("Discharge", "regularized", DELTA_Q + FADE_CURVE, models.elastic_net),
    ModelSpec("Full", "regularized", DELTA_Q + FADE_CURVE + TEMPERATURE_AND_TIME + RESISTANCE, models.elastic_net),
    # 내부저항은 Batch 2 의 일부 셀에 측정값이 없다. 모든 셀을 평가할 수 있도록 뺀 구성도 함께 본다
    ModelSpec("Full (IR 제외)", "regularized", DELTA_Q + FADE_CURVE + TEMPERATURE_AND_TIME, models.elastic_net),
)
# 원논문 Table 1 의 평균 백분율 오차 (%): Train, 1차 테스트, 2차 테스트. 2차 테스트가 이 데이터셋의 Batch 3 다
PAPER_REPORTED = {
    "Variance": (14.1, 14.7, 11.4),
    "Discharge": (9.8, 13.0, 8.6),
    "Full": (5.6, 14.1, 10.7),
}


# 원논문의 분류 실험: 초기 5 사이클, 로지스틱 회귀, 기준선 550 사이클 (Supplementary Note 4)
CLASSIFIER_CYCLES = 5
# 후보 20개 중 "마지막 10 사이클의 추세" 두 개는 5 사이클에서 정의되지 않아 원논문도 뺐다
_NO_LATE_TREND = tuple(f for f in FADE_CURVE if not f.endswith("_late"))
PAPER_CLASSIFIERS = {
    "Variance classifier": (models.CORE_FEATURE,),
    "Full classifier": DELTA_Q + _NO_LATE_TREND + TEMPERATURE_AND_TIME + RESISTANCE,
    "Full classifier (IR 제외)": DELTA_Q + _NO_LATE_TREND + TEMPERATURE_AND_TIME,
}
# 원논문 Table 2 의 2차 테스트 정확도. Train 은 82.1% / 97.4%, 1차 테스트는 78.6% / 92.7% 였다
PAPER_SECONDARY_TEST_ACCURACY = {"Variance classifier": 0.975, "Full classifier": 0.975}


def with_complete_cells(data: ExperimentData, features: tuple[str, ...], seed: int) -> ExperimentData:
    """features 가 모두 있는 셀만 남긴다. Batch 1 의 Train / Valid 분할은 남은 셀로 다시 만든다."""
    complete = data.features[list(features)].notna().all(axis=1)
    cells = data.cells[complete]
    train_life = cells.loc[cells["batch"] == config.TRAIN_BATCH, "cycle_life"]
    return replace(data, features=data.features[complete], cells=cells, split=split_train_valid(train_life, seed=seed))


def selected_features(spec: ModelSpec, data: ExperimentData) -> tuple[str, ...]:
    """Batch 1 전체로 학습했을 때 계수가 0 이 아닌 피처."""
    keys = data.train_batch_keys
    model = spec.build().fit(data.features.loc[keys, list(spec.features)], data.cells.loc[keys, "cycle_life"])
    coefficients = model.regressor_[-1].coef_
    return tuple(name for name, value in zip(spec.features, coefficients, strict=True) if value != 0)


def comparison_table(data: ExperimentData, seed: int = config.SEED) -> pd.DataFrame:
    """모델 구성별 CV / Valid / Test MAPE 와 원논문이 보고한 값."""
    rows = []
    for spec in PAPER_MODELS:
        usable = with_complete_cells(data, spec.features, seed)
        scores = evaluate_candidates([spec], usable, seed).iloc[0]
        chosen = selected_features(spec, usable)
        reported = PAPER_REPORTED.get(spec.name, (None, None, None))
        rows.append(
            {
                "model": spec.name,
                "n_candidates": len(spec.features),
                "n_selected": len(chosen),
                "cv_mape": scores["cv_mape"],
                "valid_mape": scores["valid_mape"],
                "test_b2_mape": scores["test_b2_mape"],
                "test_b3_mape": scores["test_b3_mape"],
                "n_test_b2": int((usable.cells["batch"] == config.TEST_BATCH).sum()),
                "n_test_b3": int((usable.cells["batch"] == config.EXTRA_TEST_BATCH).sum()),
                "paper_train": reported[0],
                "paper_primary_test": reported[1],
                "paper_secondary_test": reported[2],
                "selected_features": ", ".join(chosen),
            }
        )
    return pd.DataFrame(rows)


def logistic_screen(data: ExperimentData, features: tuple[str, ...]) -> Screen:
    """l1 규제 로지스틱 회귀. 단수명 확률이 0.5 이상이면 단수명으로 판정한다 (원논문과 같은 판정 기준).

    학습 셀에 단수명이 1개뿐이라 규제 강도를 교차검증으로 정할 수 없다. 기본값(C = 1)을 쓴다.
    """

    def screen(case: EvalCase) -> Verdict:
        X = data.features.loc[case.fit_keys, list(features)]
        is_short = data.cells.loc[case.fit_keys, "cycle_life"] < config.SHORT_LIFE_THRESHOLD
        classifier = LogisticRegression(l1_ratio=1.0, solver="liblinear", random_state=config.SEED)  # l1 규제
        model = make_pipeline(StandardScaler(), classifier).fit(X, is_short)
        probability = model.predict_proba(data.features.loc[case.eval_keys, list(features)])[:, 1]
        return Verdict(probability >= 0.5, probability)

    return screen


def classifier_table(data: ExperimentData, seed: int = config.SEED) -> pd.DataFrame:
    """원논문 분류기 구성별 성능. 피처는 초기 5 사이클로 다시 계산한다."""
    names = tuple(dict.fromkeys(f for features in PAPER_CLASSIFIERS.values() for f in features))
    early = replace(data, features=build_feature_table(load_dataset(), CLASSIFIER_CYCLES, names))
    rows = []
    for name, features in PAPER_CLASSIFIERS.items():
        usable = with_complete_cells(early, features, seed)
        screen = logistic_screen(usable, features)
        for case in evaluation_cases(usable):
            metrics = evaluate_screen(screen, [case], usable.cells["cycle_life"])
            # 원논문의 2차 테스트가 이 데이터셋의 Batch 3 다. 다른 분할에는 대응하는 원논문 수치가 없다
            reported = PAPER_SECONDARY_TEST_ACCURACY.get(name) if case.name == "test_b3" else None
            rows.append(
                {"model": name, "n_features": len(features), "split": case.name}
                | metrics
                | {"paper_accuracy": reported}
            )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="원논문 모델 구성의 재구현과 비교")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--out", type=Path, default=config.RESULTS_DIR)
    args = parser.parse_args(argv)

    data = prepare_data(args.seed)
    table = comparison_table(data, args.seed)
    classifiers = classifier_table(data, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    table.round(2).to_csv(args.out / "paper_models.csv", index=False)
    classifiers.round(3).to_csv(args.out / "paper_classifiers.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 200)
    print(table.drop(columns="selected_features").round(2).to_string(index=False))
    for _, row in table.iterrows():
        print(f"\n[{row['model']}] 선택된 피처 {row['n_selected']}개 : {row['selected_features']}")
    print("\n[원논문 분류기 구성 : 초기 5 사이클]\n", classifiers.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
