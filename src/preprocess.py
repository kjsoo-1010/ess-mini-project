"""원본 .mat 파일을 읽어 정제된 Dataset 으로 만든다.

MATLAB v7.3(HDF5) 파일에서 필요한 부분만 h5py 로 직접 읽는다.
읽는 범위는 summary 전체와 초기 사이클의 Qdlin(전압 축으로 보간한 방전 용량)이다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from src import config
from src.config import BatchSpec

# 원본 summary 필드명 -> 사용하는 컬럼명
SUMMARY_FIELDS = {
    "QDischarge": "QD",
    "QCharge": "QC",
    "IR": "IR",
    "Tavg": "Tavg",
    "Tmax": "Tmax",
    "Tmin": "Tmin",
    "chargetime": "chargetime",
}


@dataclass(frozen=True)
class Dataset:
    """셀 단위로 정렬된 데이터 묶음.

    cells   : index=cell_key, columns=[batch, cell_id, policy, cycle_life]
    summary : 사이클당 한 행. columns=[cell_key, cycle, QD, QC, IR, Tavg, Tmax, Tmin, chargetime, T_integral]
              T_integral 은 사이클 내부 시계열에서 계산한 온도의 시간 적분이며 초기 사이클에만 값이 있다
    qdlin   : (셀 수, 사이클 수, 전압 지점 수). 셀 순서는 cells.index 와 같고 cycle n 은 [:, n - 1, :]
    vdlin   : qdlin 의 전압 축
    """

    cells: pd.DataFrame
    summary: pd.DataFrame
    qdlin: np.ndarray
    vdlin: np.ndarray

    @property
    def n_cycles(self) -> int:
        return self.qdlin.shape[1]

    def select(self, mask: pd.Series) -> Dataset:
        """cells 에 대한 불리언 마스크로 셀을 고른다."""
        keys = self.cells.index[mask.to_numpy()]
        return replace(
            self,
            cells=self.cells.loc[keys],
            summary=self.summary[self.summary["cell_key"].isin(keys)].reset_index(drop=True),
            qdlin=self.qdlin[mask.to_numpy()],
        )

    def early_window(self, n_cycles: int) -> Dataset:
        """초기 n_cycles 사이클만 남긴다. 피처 계산은 이 결과만 입력으로 받는다."""
        if n_cycles > self.n_cycles:
            raise ValueError(f"qdlin 은 {self.n_cycles} 사이클까지만 로딩되어 있다 (요청: {n_cycles})")
        return replace(
            self,
            summary=self.summary[self.summary["cycle"] <= n_cycles].reset_index(drop=True),
            qdlin=self.qdlin[:, :n_cycles],
        )


def resolve_data_dir() -> Path:
    """.mat 파일이 있는 폴더를 찾는다. 환경변수가 없으면 kagglehub 캐시를 쓴다."""
    override = os.environ.get(config.DATA_DIR_ENV)
    if override:
        return Path(override)
    import kagglehub  # 다운로드가 필요할 때만 불러온다

    return Path(kagglehub.dataset_download(config.KAGGLE_DATASET))


def _read_string(f: h5py.File, ref: h5py.Reference) -> str:
    return np.array(f[ref]).tobytes()[::2].decode()


def _read_qdlin(f: h5py.File, cycles: h5py.Group, n_cycles: int, n_points: int) -> np.ndarray:
    """초기 n_cycles 의 Qdlin. 측정값이 없는 사이클은 NaN 으로 채운다."""
    out = np.full((n_cycles, n_points), np.nan)
    for j in range(min(n_cycles, cycles["Qdlin"].shape[0])):
        curve = np.array(f[cycles["Qdlin"][j, 0]]).ravel()
        if curve.size == n_points:
            out[j] = curve
    return out


def _read_temperature_integral(f: h5py.File, cycles: h5py.Group, n_cycles: int) -> np.ndarray:
    """초기 n_cycles 의 사이클별 온도 시간 적분 (°C·분). 측정값이 없는 사이클은 NaN."""
    out = np.full(n_cycles, np.nan)
    for j in range(min(n_cycles, cycles["T"].shape[0])):
        temperature = np.array(f[cycles["T"][j, 0]]).ravel()
        time = np.array(f[cycles["t"][j, 0]]).ravel()
        if temperature.size > 2 and temperature.size == time.size:
            out[j] = np.trapezoid(temperature, time)
    return out


def clean_summary(summary: pd.DataFrame) -> pd.DataFrame:
    """측정값으로 볼 수 없는 값을 제거한다. 세 배치에 같은 규칙을 적용한다."""
    out = summary[summary["QD"] > 0].copy()  # 측정값 없이 0 으로 채워진 사이클 (Batch 1 의 cycle 1)
    spike = out["QD"] > config.MAX_VALID_CAPACITY_AH
    out.loc[spike, ["QD", "QC"]] = np.nan  # 공칭 1.1 Ah 셀에서 나올 수 없는 용량
    out.loc[out["IR"] <= 0, "IR"] = np.nan  # 내부저항 측정 누락
    return out.reset_index(drop=True)


def load_batch(spec: BatchSpec, data_dir: Path, n_cycles: int = config.EARLY_CYCLES) -> Dataset:
    """배치 하나를 읽는다. 수명을 알 수 없는 셀과 spec.drop_cells 는 제외한다."""
    cells, summaries, curves = [], [], []
    with h5py.File(data_dir / spec.filename, "r") as f:
        batch = f["batch"]
        vdlin = np.array(f[batch["Vdlin"][0, 0]]).ravel()
        for cell_id in range(batch["summary"].shape[0]):
            cycle_life = float(np.array(f[batch["cycle_life"][cell_id, 0]]).ravel()[0])
            if cell_id in spec.drop_cells or np.isnan(cycle_life):
                continue
            cell_key = f"{spec.tag}c{cell_id}"
            cells.append(
                {
                    "cell_key": cell_key,
                    "batch": spec.name,
                    "cell_id": cell_id,
                    "policy": _read_string(f, batch["policy_readable"][cell_id, 0]),
                    "cycle_life": int(cycle_life) + spec.life_offsets.get(cell_id, 0),
                }
            )
            raw = f[batch["summary"][cell_id, 0]]
            frame = pd.DataFrame({name: np.array(raw[field]).ravel() for field, name in SUMMARY_FIELDS.items()})
            frame.insert(0, "cycle", np.array(raw["cycle"]).ravel().astype(int))
            frame.insert(0, "cell_key", cell_key)
            cycles = f[batch["cycles"][cell_id, 0]]
            integral = _read_temperature_integral(f, cycles, n_cycles)
            frame["T_integral"] = np.nan
            frame.loc[: min(n_cycles, len(frame)) - 1, "T_integral"] = integral[: len(frame)]
            summaries.append(frame)
            curves.append(_read_qdlin(f, cycles, n_cycles, vdlin.size))
    return Dataset(
        cells=pd.DataFrame(cells).set_index("cell_key"),
        summary=clean_summary(pd.concat(summaries, ignore_index=True)),
        qdlin=np.stack(curves),
        vdlin=vdlin,
    )


def load_dataset(
    batches: tuple[BatchSpec, ...] = config.BATCHES,
    data_dir: Path | None = None,
    n_cycles: int = config.EARLY_CYCLES,
) -> Dataset:
    """여러 배치를 읽어 하나의 Dataset 으로 합친다."""
    data_dir = data_dir or resolve_data_dir()
    parts = [load_batch(spec, data_dir, n_cycles) for spec in batches]
    return Dataset(
        cells=pd.concat([p.cells for p in parts]),
        summary=pd.concat([p.summary for p in parts], ignore_index=True),
        qdlin=np.concatenate([p.qdlin for p in parts]),
        vdlin=parts[0].vdlin,
    )
