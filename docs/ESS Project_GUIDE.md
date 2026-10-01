# ESS 배터리 수명 예측 — 프로젝트 수행 가이드

> 원본: [[ESS Project GUIDE (Origin)]]
> 원본에서 도메인 배경지식(ESS 개념, 리튬이온 구조, 시장 전망 등)을 걷어내고, 개발·제출에 필요한 요구사항만 재구성한 문서.
> 원본에 없던 내용이나 원본의 오류를 고친 부분은 `[정리 메모]`로 표시했다.

---

## 1. 한눈에 보기

| 항목 | 내용 |
|---|---|
| 목표 | 배터리 **초기 사이클 데이터만으로** 수명(`cycle_life`)을 예측하는 모델 개발 |
| 기준 논문 | Severson et al. (2019), *Data-driven prediction of battery cycle life before capacity degradation*, Nature Energy 4, 383–391 — <https://www.nature.com/articles/s41560-019-0356-8> |
| 태스크 | Regression **또는** Classification 중 **택 1** |
| 학습 / 평가 | Batch 1 학습 → Batch 2 테스트 (필수), Batch 3 테스트 (선택) |
| 목표 성능 | Regression MAPE 9.1% / Classification Accuracy 95.1% (원논문) |
| 산출물 | DAY 1: 전략 PDF (17시) / DAY 2: 공개 GitHub 저장소 (16시) |

---

## 2. 문제 정의

### 2.1 Target

- `cycle_life` : EOL(용량이 초기의 80%, 즉 SOH 80%에 도달)까지의 총 사이클 수

### 2.2 태스크 옵션 (택 1)

| | Regression | Classification (Binary) |
|---|---|---|
| 예측 대상 | `cycle_life` (사이클 수) | 장수명(1) / 단수명(0) |
| 입력 범위 | 초기 **100** 사이클 | 초기 **5** 사이클 |
| Target 정의 | `cycle_life` 그대로 | `(cycle_life >= 550).astype(int)` |
| 지표 | MAPE (%) | F1-Score, Accuracy |
| 원논문 성능 | 오차 9.1% | 오차 4.9% (= Accuracy 95.1%) |

```python
# Classification 레이블: 1 = 장수명(Long-life), 0 = 단수명(Short-life)
df['label'] = (df['cycle_life'] >= 550).astype(int)
```

선택한 태스크와 그 Target Variable을 고른 이유를 설명할 수 있어야 한다.

### 2.3 누수(leakage) 제약

- 피처는 **입력 범위 안의 사이클에서만** 계산한다 (Regression ≤ 100, Classification ≤ 5).
- 그 이후 사이클의 값이나 `cycle_life`에서 파생된 값은 피처에 들어가면 안 된다.

---

## 3. 데이터

- Kaggle: <https://www.kaggle.com/datasets/itshpark/data-driven-prediction-of-battery-cycle>

| 파일 | Batch | 용도 |
|---|---|---|
| 2017-05-12 (2.8GB) | Batch 1 | **학습** (원논문 학습셋) |
| 2018-02-20 (1.9GB) | Batch 2 | **테스트** (원논문 1차 테스트셋) |
| 2018-04-12 (3.0GB) | Batch 3 | 추가 테스트, 선택 (원논문 2차 테스트셋) |
| 2018-04-03 varcharge (0.1GB) | extra | **사용 안 함** — 다른 논문(Attia 2020)의 충전 최적화 실험 데이터 |

### 3.1 데이터 구조 (셀 1개 기준, 3계층)

**Descriptors — 셀 단위 스칼라**

| 변수 | 설명 |
|---|---|
| `cycle_life` | EOL까지 총 사이클 수 → **Target** |
| `charging_policy` | 충전 프로토콜. 예: `"4.8C(80%)-3.6C"` = 용량 80%까지 4.8C로 충전, 이후 3.6C로 충전 |

**Summary — 사이클별 요약 스칼라 (사이클 수 길이의 배열)**

| 변수 | 설명 |
|---|---|
| `QD` | 방전 용량 (Ah) |
| `Qc` | 충전 용량 (Ah) |
| `IR` | 내부 저항 (Ohm) |
| `Tmax` / `Tavg` / `Tmin` | 사이클 내 최고 / 평균 / 최저 온도 |
| `chargetime` | 충전 소요 시간 |
| `discharge_time` | 방전 소요 시간 |

**Cycles — 사이클 내부 시계열**

| 변수 | 설명 |
|---|---|
| `t` | 시간 (분) |
| `V` | 전압 (V) |
| `I` | 전류 (A) |
| `T` | 온도 (°C) |
| `Qc` / `Qd` | 충전 / 방전 용량 |
| `Qdlin` | 전압 축(2.0V~3.6V)으로 선형 보간한 방전 용량, 1,000포인트. **ΔQ(V) 계산의 기반** |
| `Tdlin` | 전압 축으로 선형 보간한 온도, 1,000포인트 |
| `discharge_dQdV` | 방전 dQ/dV 곡선 (파생) |

### 3.2 핵심 파생 피처: ΔQ(V)

- `ΔQ(V) = Qdlin(cycle 100) − Qdlin(cycle 10)` — 원본 가이드의 정의. 모델 피처로는 Regression에만 해당한다 (Classification은 9장 3번 참고).
- 1,000포인트 곡선이므로 통계값(분산, 최솟값, 평균 등)으로 요약해 피처로 쓴다.
- 장수명 셀과 단수명 셀에서 곡선 형태가 달라지는지가 EDA의 핵심 확인 사항.

### 3.3 배치 간 주의사항

- **수명 분포** : Batch 1·2는 유사, Batch 3는 분포가 다르다.
- **충전 커브 시작 시점이 배치별로 다르다** : `Qdlin`을 배치 간에 단순 비교하면 왜곡된다.
- **이상치 제거 고려** : 배치 수집 시기 사이에 수개월 공백이 있고, 일부 셀은 데이터 품질 문제로 원논문에서도 제거됐다.
- 따라서 Batch 3 성능은 Batch 2보다 떨어질 수 있다.

---

## 4. DAY 1 — EDA와 모델 전략 수립

대상은 Batch 1 + 2 + 3. 아래 5개 질문에 대해 **배치별로 EDA를 수행하고 배치 간 특징을 비교**한 뒤, 그 결과로 모델 설계 전략을 세운다.

### 4.1 EDA 질문

| # | 질문 | 확인할 것 |
|---|---|---|
| 1 | Cycle Life 분포는 어떻게 생겼는가? | 150~2,300 사이클 히스토그램 / 장수명(>1,000)·단수명(<500) 비율 / 이상치 셀 식별과 유독 짧은 이유 |
| 2 | 방전 용량은 어떻게 감소하는가? (열화 곡선) | 사이클별 `Qd` 추이 / 열화 속도가 일정한지 가속되는지 / Knee point(급격한 열화 시작점) |
| 3 | ΔQ(V) 곡선은 초기 사이클에서 차이를 보이는가? | cycle 100 − cycle 10의 Q(V) 차이 / 장수명 vs 단수명 셀의 형태 비교 / 구분 가능한 통계값을 피처로 추출 |
| 4 | 충전 조건(C-rate)과 수명의 관계는? | 충전 프로토콜별 평균 수명 / 고속 충전 셀이 실제로 수명이 짧은지 / 충전 전류 패턴과 열화 속도의 상관 |
| 5 | 어떤 신호가 수명과 연관되는가? | 초기 사이클 피처와 `cycle_life`의 상관계수 / 가장 강한 관계 / 다중공선성 |

### 4.2 모델 설계 전략에 담을 것

1. **Feature Engineering** — EDA에서 발견한 내용을 근거로 유의미한 변수 선별
2. **Regression vs Classification** — 하나를 선택하고 Target Variable 선정
3. **Modeling Strategy** — 확인한 데이터 특성에 근거한 데이터 처리 방식과 후보 모델 목록. 후보 모델은 EDA 시사점과 연결되게 쓴다.

### 4.3 작성 원칙

- 그래프 나열식은 안 된다.
- 질문마다 **핵심 내용(그래프 + 해석) → 시사점** 순으로 정리한다.
- 흐름은 `EDA 발견 → 시사점 → 피처/모델 전략`이 논리적으로 이어져야 한다.

### 4.4 참고 스타일: EDA에서 모델 전략까지 잇는 법

원본에 참고용으로 실린 예시(주제: 시계열 데이터를 활용한 배달 매출 예측). 주제는 다르지만 **평가자가 궁금해하는 질문에 답하는 순서로 쓰는 방식**을 따르면 된다. 본인이 말하고 싶은 것보다 평가자가 듣고 싶은 것을 먼저, 평가 기준에 맞춰 정리한다.

**① 입력 데이터 / 피처 설명** — 평가자가 궁금해하는 것

- 데이터 수집·정리 과정 : 도메인 관점에서 정의했는가, 가설 기반으로 정의했는가, 누락된 데이터는 없는가
- Target이 무엇인가 (도메인 관점의 정의), X변수·Y변수가 무엇인가
- 각 피처를 **왜 골랐는가** — 예시에서는 날씨 피처에 실측이 아닌 "예보" 데이터를 쓴 이유를 누수 방지로 설명
- 데이터의 특징이 무엇인가

![[e4dba816210255ae796ad24c33f916b4df2ab639320ea17097cb0176789caa1c.png]]

**② EDA 한 장의 구성** — 이슈 하나당 4단계

1. 데이터 탐색의 목적 (어떤 ISSUE를 확인하려는가)
2. 어떻게 해결했는가 (처리 방법)
3. 변경 전/후 차이 (그래프로 대비)
4. 시사점 한 줄 요약 — 모델링에 무엇을 요구하는가

예시: target 분포가 왼쪽으로 skew → 로그 변환 → Tweedie 분포 형태 확인 → "모델링 시 Tweedie 분포를 고려한 파라미터 설정 필요"

![[43eed08db4d0a4a90363481a2ee499d38ba0989fb7d62ff0919708450bfc58ed.png]]

**③ 분포 차이를 봤다면 "그래서 무엇을 할 것인가"까지**

- 분포의 차이를 알아서 무엇을 하려는지가 나와야 한다.
- 데이터 특징이 도메인(비즈니스) 관점에서 해석되어야 한다. **뻔한 특징은 특징이 아니다.**

예시: 시도별·카테고리별로 매출 분포가 다름 → 예측의 중요한 기준이 됨 → 계층적 구조로 모델링

![[15a44ccf2022c71ae18801152a6507fcbc0d6cd1a18bd0d0241a2bb117e77a5d.png]]

**④ 모델 선택 근거** — EDA 시사점을 그대로 받아서 쓴다

- 예측 목적을 한 문장으로 (누구 단위로, 어떤 입력으로, 무엇을 예측)
- 그 모델을 고른 이유를 **알고리즘 관점**과 **데이터 특징 관점** 양쪽에서 설명
- 더 복잡한 모델(최신 딥러닝 등)을 쓰지 않는 이유도 답할 수 있어야 한다
- 예상되는 위험과 대응 (예: 과적합 방지를 위한 파라미터 튜닝)

예시: 요일별 패턴이 명확 → tree 기반으로 충분 / ②에서 확인한 Tweedie 분포 → LightGBM의 `objective: tweedie` 옵션으로 반영

![[c49a2c189b5cd1e2180287b65cc85659127a5f15dc53f8e4f905f9bf7e3e46b1.png]]

**이 프로젝트에 적용하면**

| EDA 질문 | 발견 (그래프 + 해석) | 시사점 | 전략에 반영 |
|---|---|---|---|
| 1. Cycle Life 분포 | 예: 분포가 치우쳐 있는가 | 예: target 변환 필요 여부 | target 변환, 손실 함수·지표 선택 |
| 2. 열화 곡선 | 예: 초기 100 사이클에선 용량 차이가 거의 안 보이는가 | 예: 용량 값 자체는 약한 신호 | 어떤 요약 피처를 쓸지 |
| 3. ΔQ(V) | 예: 장·단수명 셀의 곡선 형태 차이 | 예: 어떤 통계값이 구분력을 갖는가 | 핵심 피처 정의 |
| 4. C-rate | 예: 프로토콜별 수명 차이 | 예: 프로토콜을 피처·분할 기준으로 쓸지 | 피처 인코딩, Hold-out 분할 방식 |
| 5. 상관관계 | 예: 피처 간 다중공선성 | 예: 피처 수 대비 셀 수가 적음 | 규제 선형 모델 vs tree 계열 등 후보 선정 근거 |

표의 "예"는 채워야 할 칸의 성격을 보여 주는 것이고, 실제 내용은 EDA 결과로 채운다.

---

## 5. DAY 2 — 모델 개발 및 평가

### 5.1 데이터 분할

| 구분 | 데이터 | 의미 |
|---|---|---|
| Train | Batch 1, Cross-Validation 평균 | 학습 성능 |
| Valid | Batch 1, **Hold-out** | 검증 성능 |
| Test | Batch 2 | 최종 평가 (필수) |
| Test (추가) | Batch 3 | 추가 일반화 검증 (선택) |

Valid를 CV가 아닌 Hold-out으로 두는 이유:

- 셀은 서로 독립이고, 각 셀은 서로 다른 충전 프로토콜(C-rate)로 실험됐다.
- CV에서는 같은 프로토콜의 셀이 train/valid로 갈라져 누수 위험이 남는다.
- Hold-out은 **셀 단위 분리**를 명확히 보장하고, 배치 간 일반화를 보는 프로젝트 구조에 더 맞다.

분할은 반드시 **셀 단위**로 한다 (한 셀의 사이클이 train과 valid에 나뉘어 들어가면 안 된다).

### 5.2 성능 지표

- Regression : **MAPE (%)**
- Classification : **F1-Score, Accuracy**

`[정리 메모]` 원본에는 지표 항목이 "Regression : MAPE / Regression : F1-Score, Accuracy"로 적혀 있다. 두 번째 줄은 Classification의 오기로 보고 고쳤다.

### 5.3 Gap 정의

| Gap | 보는 것 |
|---|---|
| Train − Valid | 과적합 여부. (+)면 과적합 의심 |
| Valid − Test | 배치 간 일반화 차이. (+)면 일반화 저하 의심 |
| Target − Test | 원논문 대비 차이 (Regression 9.1% / Classification Accuracy 95.1%) |
| Batch 2 − Batch 3 | (선택) 테스트 배치 간 성능 차이 |

`[정리 메모]` 원본은 Gap의 부호 계산식을 명시하지 않았다. "(+) = 나빠짐"이 되려면 지표 방향에 따라 빼는 순서가 달라진다(MAPE는 낮을수록 좋고, F1·Accuracy는 높을수록 좋음). 코드에서는 **"(+) = 뒤 단계에서 성능이 나빠짐"** 으로 통일하는 것을 권장한다:

- MAPE : `Valid − Train`, `Test − Valid`
- F1 / Accuracy : `Train − Valid`, `Valid − Test`

어떤 규칙을 썼는지 README 표 아래에 한 줄로 적어 둔다.

### 5.4 리포팅 포맷 (필수 — Batch 2까지)

**Regression**

| 구분 | MAPE (%) | 비고 |
|---|---|---|
| Train (Batch 1 CV) | | |
| Valid (Batch 1 Hold-out) | | |
| Test (Batch 2) | | |
| Gap (Train-Valid) | | (+) : 과적합 의심 |
| Gap (Valid-Test) | | (+) : 배치간 일반화 저하 의심 |
| Gap (Target-Test) | | Target : 원논문 9.1% |

**Classification**

| 구분 | F1-Score | Accuracy | 비고 |
|---|---|---|---|
| Train (Batch 1 CV) | | | |
| Valid (Batch 1 Hold-out) | | | |
| Test (Batch 2) | | | |
| Gap (Train-Valid) | | | (+) : 과적합 의심 |
| Gap (Valid-Test) | | | (+) : 배치간 일반화 저하 의심 |
| Gap (Target-Test) | | | Target : Accuracy 95.1% |

### 5.5 리포팅 포맷 (선택 — Batch 3까지)

Batch 2 결과와 나란히 놓고 배치 간 일반화 수준을 평가한다. Gap (Batch 2 − Batch 3)이 크면 **피처가 특정 배치에 과적합됐을 가능성을 분석하고 원인을 제시**한다.

**Regression**

| 구분 | Gap | MAPE (%) | 비고 |
|---|---|---|---|
| Train (Batch 1 CV) | | | |
| Valid (Batch 1 Hold-out) | | | |
| Test (Batch 2) | | | |
| | Gap (Train-Valid) | | (+) : 과적합 의심 |
| | Gap (Valid-Test) | | (+) : 배치간 일반화 저하 의심 |
| | Gap (Target-Test) | | Target : 원논문 9.1% |
| Test (Batch 3) | | | |
| | Gap (Batch2-Batch3) | | Test 성능 간 비교 |
| | Gap (Target-Test) | | Batch 3 기준, 원논문 성능 비교 |

**Classification**

| 구분 | Gap | F1-Score | Accuracy | 비고 |
|---|---|---|---|---|
| Train (Batch 1 CV) | | | | |
| Valid (Batch 1 Hold-out) | | | | |
| Test (Batch 2) | | | | |
| | Gap (Train-Valid) | | | (+) : 과적합 의심 |
| | Gap (Valid-Test) | | | (+) : 배치간 일반화 저하 의심 |
| | Gap (Target-Test) | | | Target : Accuracy 95.1% |
| Test (Batch 3) | | | | |
| | Gap (Batch2-Batch3) | | | Test 성능 간 비교 |
| | Gap (Target-Test) | | | Batch 3 기준, 원논문 성능 비교 |

---

## 6. 산출물

모든 산출물은 반별 채널의 Slack thread로 제출한다.

| | DAY 1 — 모델 전략 수립 | DAY 2 — 모델 개발 및 평가 |
|---|---|---|
| 형태 | PDF | 공개(public) GitHub 저장소 링크 |
| 파일명 | `DS-MINI-Design-{캠퍼스_X반}-{이름1+이름2}.pdf` | — |
| 마감 | DAY 1, 17시 | DAY 2, 16시 |
| 내용 | EDA 질문별 핵심 내용·시사점, 모델 설계 전략 | 코드, `README.md`, 성능 결과 |
| 필수 | EDA → 전략 연결 | Gap (Target−Test)을 Batch 2 기준으로 반영 |

### 6.1 저장소 구조 (샘플)

```text
├── data/
│   └── README.md
├── notebooks/
│   ├── 01_EDA.ipynb
│   ├── 02_feature_engineering.ipynb
│   └── 03_modeling.ipynb
├── src/
│   ├── preprocess.py
│   ├── features.py
│   └── train.py
├── results/
│   └── model_performance.csv
├── requirements.txt
└── README.md
```

### 6.2 README 템플릿

간결하고 명확하게 작성한다. 아래는 원본 샘플의 깨진 형식을 복원한 것.

````markdown
# ESS 배터리 수명 예측

(목적 작성)

## 프로젝트 개요

- 데이터셋 : MIT-Stanford Battery Dataset (Severson et al., Nature Energy 2019)
- 학습 데이터 : Batch 1 (2017-05-12)
- 평가 데이터 : Batch 2 (2018-02-20)
- 태스크 : Regression (Cycle Life 예측) / Classification (장단수명 분류)  ← 택 1

## 파일 구조

```text
├── data/
│   └── README.md
├── notebooks/
│   ├── 01_EDA.ipynb
│   ├── 02_feature_engineering.ipynb
│   └── 03_modeling.ipynb
├── src/
│   ├── preprocess.py
│   ├── features.py
│   └── train.py
├── results/
│   └── model_performance.csv
├── requirements.txt
└── README.md
```

## 환경 설정

```bash
git clone https://github.com/팀명/ess-battery-project
cd ess-battery-project
pip install -r requirements.txt
```

## EDA

### Cycle Life 분포
- 분포 형태 및 장단수명 비율 요약
- 핵심 발견 : (팀이 발견한 인사이트를 한 줄로)

### 열화 곡선 분석
- 장수명 vs 단수명 셀의 열화 속도 차이
- Knee point 존재 여부 및 발생 시점
- 핵심 발견 :

### ΔQ(V) 곡선 분석
- Cycle 100 - Cycle 10 차이 곡선 형태
- 장단수명 셀 간 ΔQ 형태 비교
- 핵심 발견 :

### 충전 속도(C-rate)와 수명의 관계
- 충전 프로토콜별 평균 수명 비교 결과
- 핵심 발견 :

### (추가 확인한 내용)

## Modeling

### 피처 엔지니어링 전략
EDA 결과를 바탕으로 선택한 피처와 그 근거를 기술

### 모델 선택 및 근거
- 후보 모델 :
- 최종 모델 :
- 선택 이유 :

## 성능 결과

(리포팅 포맷에 맞춰 작성)

## 오류 분석

- 모델이 가장 크게 틀린 셀의 공통점
- 원인 가설 및 개선 방향

## ESS 도메인 해석

분석 결과를 실제 ESS 운영 관점에서 해석

- 이 모델을 실제 BESS에 적용한다면 어떤 의사결정에 활용 가능한가?
- 어떤 한계가 있으며, 실 배포를 위해 추가로 필요한 것은 무엇인가?

## 참고문헌

- Severson et al. (2019). Data-driven prediction of battery cycle life before capacity degradation. *Nature Energy*, 4, 383–391.

## 팀 구성

- 김영희 : EDA, 피처 엔지니어링, 모델 개발, 성능 평가(Batch 2)
- 박철수 : EDA, 피처 엔지니어링, 모델 개발, 성능 평가(Batch 3)
````

---

## 7. 평가 기준

`[정리 메모]` 원본 표가 깨져 있어 행·배점을 맞춰 복원했다.

**모델 전략 수립 (DAY 1) — 100점**

| 평가항목 | 평가 내용 | 배점 |
|---|---|---|
| EDA | 핵심 변수 분포 탐색 / 통계량 확인 및 해석 / Feature Selection & Engineering | 50 |
| EDA → 전략 연결성 | EDA 기반 시사점 도출 / 연결 논리의 일관성 | 30 |
| 모델링 전략 수립 | Feature 설계 논리 / 모델 선택 논리 | 20 |

**모델 개발 및 평가 (DAY 2) — 100점**

| 평가항목 | 평가 내용 | 배점 |
|---|---|---|
| 전략 → 구현 반영 | 전략 기반으로 Feature 및 모델 구현 | 20 |
| Pipeline 개발 | 개발 파이프라인 / 데이터 분할 적절성 / 핵심 변수 구현 | 40 |
| 성능 리포팅 및 해석 | 성능 정리(포맷 기반) / 목표 성능 대비 Gap 해석력 | 20 |
| 분석 결과 해석 | 분석 결과의 도메인 관점 해석 / 개발 한계점 도출 | 20 |

배점이 가장 큰 항목은 DAY 1의 EDA(50)와 DAY 2의 Pipeline(40)이다.

---

## 8. Baseline 코드가 충족해야 할 요구사항

위 내용을 구현 관점으로 다시 묶은 체크리스트.

- [ ] **로딩** : Batch 1·2·(3) 원본 파일 → 셀 단위 구조(descriptors / summary / cycles)로 파싱
- [ ] **전처리** : 이상치·품질 불량 셀 처리 기준을 정하고 근거를 기록
- [ ] **피처** : 입력 범위 내 사이클만 사용 (Regression ≤ 100, Classification ≤ 5)
- [ ] **ΔQ(V) 피처** : Regression은 `Qdlin(100) − Qdlin(10)`의 요약 통계, Classification은 5 사이클 이내의 차이로 정의
- [ ] **Target** : `cycle_life` 또는 `cycle_life >= 550` 이진 레이블
- [ ] **분할** : Batch 1을 셀 단위로 Train / Hold-out 분리, Train 내부에서 CV
- [ ] **평가** : Train(CV 평균) · Valid(Hold-out) · Test(Batch 2) · (Batch 3) 지표 산출
- [ ] **Gap 계산** : Train-Valid, Valid-Test, Target-Test, (Batch2-Batch3)
- [ ] **결과 저장** : 리포팅 포맷 그대로 `results/model_performance.csv` 출력
- [ ] **오류 분석** : 가장 크게 틀린 셀 목록과 공통점을 뽑을 수 있는 출력
- [ ] **재현성** : `requirements.txt`, 실행 순서, 시드 고정

---

## 9. 코드 작성 전 확인이 필요한 것

`[정리 메모]` 원본 가이드에 없거나 불명확해서, 실제 데이터를 열어 보고 확정해야 하는 항목.

1. **파일 형식과 실제 키 이름** — 원본은 변수명만 나열한다(`QD`, `chargetime`, `discharge_time` 등 표기가 일관되지 않음). 실제 파일의 키 이름과 형식을 먼저 확인한다.
2. **Scratch 노트북** — 원본에 `30-ESSHealth-scratch.ipynb`가 첨부로 언급되지만 링크가 깨져 볼트에 없다. 로딩 코드가 들어 있을 가능성이 높으니 별도로 받아 두면 좋다.
3. **Classification을 고를 경우의 ΔQ(V)** — 원본은 ΔQ(V)를 태스크 구분 없이 `cycle 100 − cycle 10`으로만 설명한다. 이 정의는 Regression(입력 ≤ 100 사이클)용이고, Classification(입력 ≤ 5 사이클)의 모델 피처로 쓰면 누수다. Classification에서는 5 사이클 안의 차이(예: cycle 5 − cycle 4)로 정의해야 하며, 원논문이 실제로 쓴 정의는 논문에서 확인한다. EDA 단계에서 `100 − 10`으로 장·단수명 셀을 비교하는 것은 태스크와 무관하게 가능하다.
4. **제거 대상 셀** — 원본은 "원논문에서도 일부 셀이 제거됐다"고만 한다. 어떤 셀인지는 논문/공식 코드에서 확인해야 한다.
5. **Hold-out 비율과 CV fold 수** — 지정돼 있지 않다. 셀 수가 적으므로(배치당 수십 개) 분할 방식에 따라 수치 변동이 크다는 점을 감안해 정한다.
6. **원논문 수치와의 직접 비교** — 목표 성능(9.1% / 95.1%)은 원논문의 분할 기준 수치다. 이 과제의 분할(Batch 1 학습 / Batch 2 테스트)과 동일한 조건인지는 논문에서 확인하고, 다르면 Gap 해석에 그 점을 적는다.

---

## 부록 — 용어 (README의 "ESS 도메인 해석" 작성용)

| 용어 | 뜻 |
|---|---|
| ESS / BESS | (Battery) Energy Storage System. 전기를 저장했다가 필요한 시점에 공급하는 시스템 |
| SOC | State of Charge. 현재 충전량 / 최대 충전 가능 용량 × 100 (%) |
| SOH | State of Health. 현재 용량 / 초기 용량 × 100 (%). **80% 이하가 교체 기준** |
| SOP | State of Power. 현재 출력 가능한 최대 전력 (W) |
| EOL | End of Life. SOH 80% 도달 시점 |
| RUL | Remaining Useful Life. EOL까지 남은 사이클 수. 예지 보전(PdM)의 핵심 타겟 |
| C-rate | 충전 속도. 1C = 1시간에 완충하는 전류 |
| Knee point | 열화가 급격히 빨라지기 시작하는 지점 |
| BMS / PCS / EMS | 배터리 상태 감시·보호 / DC↔AC 전력 변환 / 충방전 전략 결정 |

도메인 해석에 쓸 수 있는 원본의 근거:

- 배터리 교체 비용은 ESS CAPEX의 30~40%. 1MWh 기준 셀 교체 비용 $30,000~$80,000.
- 예측 없이 운영할 때의 문제: 예기치 못한 설비 중단 / 과도한 예방 교체로 인한 불필요한 비용 / 용량 저하 예측 실패로 피크 대응 불가 및 계약 위약금.
- 수명 예측의 효과: 교체 시점 사전 계획(운영 비용 20~35% 절감) / 열화 속도 예측 기반 충방전 전략 최적화 / 제조 직후 셀 선별(스크리닝)로 팩 구성 최적화.
- 열화 메커니즘: 리튬 손실, SEI 막 성장(내부 저항 증가), 양극 구조 붕괴, 전극의 물리적 균열 → 용량 감소 → SOH 하락 → EOL.
