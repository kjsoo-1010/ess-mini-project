"""결과 표와 그림을 만든다. 표의 형식은 가이드의 리포팅 포맷을 따른다."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config
from src.evaluation import classification_metrics, mape

SPLIT_COLORS = {"valid": "steelblue", "test_b2": "tomato", "test_b3": "seagreen"}
BATCH_COLORS = {config.TRAIN_BATCH: "steelblue", config.TEST_BATCH: "tomato", config.EXTRA_TEST_BATCH: "seagreen"}
SPLIT_LABELS = {"valid": "Valid (Batch 1 Hold-out)", "test_b2": "Test (Batch 2)", "test_b3": "Test (Batch 3)"}


def performance_table(cv_mape: float, predictions: pd.DataFrame) -> pd.DataFrame:
    """가이드의 Regression 리포팅 포맷. Gap 은 양수일수록 뒤 단계에서 성능이 나빠졌다는 뜻이다."""
    score = {split: mape(g["cycle_life"], g["predicted"]) for split, g in predictions.groupby("split")}
    valid, test_b2, test_b3 = score["valid"], score["test_b2"], score["test_b3"]
    rows = [
        ("Train (Batch 1 CV)", cv_mape, "Train 셀의 반복 5-fold 교차검증 평균"),
        ("Valid (Batch 1 Hold-out)", valid, "Train 셀로 학습"),
        ("Test (Batch 2)", test_b2, "Batch 1 전체로 학습"),
        ("Gap (Train-Valid)", valid - cv_mape, "(+) : 과적합 의심"),
        ("Gap (Valid-Test)", test_b2 - valid, "(+) : 배치간 일반화 저하 의심"),
        ("Gap (Target-Test)", test_b2 - config.TARGET_MAPE, f"Target : 원논문 {config.TARGET_MAPE}%"),
        ("Test (Batch 3)", test_b3, "Batch 1 전체로 학습"),
        ("Gap (Batch2-Batch3)", test_b3 - test_b2, "Test 성능 간 비교"),
        ("Gap (Target-Test, Batch 3)", test_b3 - config.TARGET_MAPE, "Batch 3 기준, 원논문 성능 비교"),
    ]
    return pd.DataFrame(rows, columns=["구분", "MAPE (%)", "비고"])


def classification_table(predictions: pd.DataFrame) -> pd.DataFrame:
    """예측 수명을 550 사이클 기준으로 나눈 장/단수명 분류 성능 (우회 분류)."""
    groups = dict(tuple(predictions.groupby("split")))
    groups["test_b2+b3"] = predictions[predictions["split"].isin(["test_b2", "test_b3"])]
    rows = [{"split": split, **classification_metrics(g["cycle_life"], g["predicted"])} for split, g in groups.items()]
    return pd.DataFrame(rows)


def worst_cells(predictions: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """분할별로 오차가 가장 큰 셀. 오류 분석의 출발점."""
    return (
        predictions.sort_values("ape", ascending=False)
        .groupby("split", sort=False)
        .head(n)
        .sort_values(["split", "ape"], ascending=[True, False])
    )


def plot_predictions(predictions: pd.DataFrame, path: Path) -> None:
    """실제 수명과 예측 수명. 대각선에 가까울수록 정확하다."""
    fig, ax = plt.subplots(figsize=(7, 7))
    for split, g in predictions.groupby("split"):
        label = f"{SPLIT_LABELS[split]} : MAPE {mape(g['cycle_life'], g['predicted']):.1f}%"
        ax.scatter(
            g["cycle_life"],
            g["predicted"],
            color=SPLIT_COLORS[split],
            s=45,
            alpha=0.75,
            edgecolors="white",
            label=label,
        )
    lim = [
        predictions[["cycle_life", "predicted"]].min().min() * 0.9,
        predictions[["cycle_life", "predicted"]].max().max() * 1.1,
    ]
    ax.plot(lim, lim, color="gray", linestyle="--", linewidth=1)
    for axis_line in (ax.axvline, ax.axhline):
        axis_line(config.SHORT_LIFE_THRESHOLD, color="gray", linestyle=":", linewidth=1)
    ax.set(
        xscale="log",
        yscale="log",
        xlim=lim,
        ylim=lim,
        xlabel="Observed Cycle Life",
        ylabel="Predicted Cycle Life",
        title="Observed vs Predicted",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_feature_fit(features: pd.DataFrame, cells: pd.DataFrame, feature: str, path: Path) -> None:
    """핵심 피처와 수명의 관계를 배치별로 그린다. 직선은 Batch 1 에 맞춘 회귀선이다."""
    data = features[[feature]].join(cells[["batch", "cycle_life"]])
    train = data[data["batch"] == config.TRAIN_BATCH]
    slope, intercept = np.polyfit(train[feature], np.log10(train["cycle_life"]), 1)
    fig, ax = plt.subplots(figsize=(8, 6))
    for batch, g in data.groupby("batch"):
        ax.scatter(
            g[feature], g["cycle_life"], color=BATCH_COLORS[batch], s=45, alpha=0.75, edgecolors="white", label=batch
        )
    xs = np.linspace(data[feature].min(), data[feature].max(), 50)
    ax.plot(xs, 10 ** (slope * xs + intercept), color="steelblue", linewidth=1.5, label=f"{config.TRAIN_BATCH} fit")
    ax.set(yscale="log", xlabel=feature, ylabel="Cycle Life", title=f"{feature} vs Cycle Life")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
