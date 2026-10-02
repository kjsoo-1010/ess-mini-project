# 데이터

원본 데이터는 저장소에 올리지 않는다. 실행하면 kagglehub 가 자동으로 내려받아 캐시에 둔다.

- 출처 : <https://www.kaggle.com/datasets/itshpark/data-driven-prediction-of-battery-cycle> (약 5 GB)
- 원논문 : Severson et al. (2019), *Data-driven prediction of battery cycle life before capacity degradation*, Nature Energy 4, 383–391

이미 내려받은 파일이 다른 폴더에 있으면 환경변수로 위치를 지정한다.

```bash
export ESS_DATA_DIR=/path/to/mat/files
```

## 배치 구성

| 구분 | 파일 | 원본 셀 수 | 사용 셀 수 | 수명 범위 | 용도 |
|---|---|---|---|---|---|
| Batch 1 | `2017-05-12_batchdata_updated_struct_errorcorrect.mat` | 46 | 41 | 534 ~ 2237 | 학습 |
| Batch 2 | `2018-02-20_batchdata_updated_struct_errorcorrect.mat` | 47 | 39 | 392 ~ 1186 | 테스트 |
| Batch 3 | `2018-04-12_batchdata_updated_struct_errorcorrect.mat` | 46 | 40 | 541 ~ 1935 | 추가 테스트 |
| - | `2018-04-03_varcharge_batchdata_updated_struct_errorcorrect.mat` | - | - | - | 사용하지 않음 |

## 원논문이 사용한 데이터와의 차이

이 데이터셋의 Batch 2 는 원논문에 없는 배치다. 원논문의 수치와 비교할 때 이 점을 고려해야 한다.

| 배치 파일 | 이 프로젝트 | 원논문 |
|---|---|---|
| 2017-05-12 | Batch 1. 전체를 학습에 사용 | 절반은 학습, 절반은 1차 테스트 |
| 2017-06-30 | 데이터셋에 없음 | 절반은 학습, 절반은 1차 테스트. 수명 148 ~ 713인 배치 |
| 2018-02-20 | Batch 2. 테스트 | 사용하지 않음 |
| 2018-04-12 | Batch 3. 추가 테스트 | 2차 테스트 |

근거는 다음과 같다.

- 원논문 Supplementary Table 9 의 셀 124개는 2017-05-12 배치 41개, 2017-06-30 배치 43개, 2018-04-12 배치 40개다. 2018-02-20 은 본문과 보충자료에 나오지 않는다.
- 저자들의 공식 코드도 위 세 파일을 읽는다.
- 이 프로젝트의 Batch 1 과 Batch 3 는 정제 후 셀 수(41, 40)와 수명 범위가 Table 9 와 일치한다.

이 차이의 영향은 두 가지다.

- **학습 데이터의 수명 범위.** 원논문의 학습 셀 41개 중 21개가 수명 550 미만이고, 모두 2017-06-30 배치의 셀이다. 이 프로젝트의 학습 데이터(Batch 1)에는 550 미만이 1개뿐이다.
- **비교 가능한 범위.** 원논문의 수치와 직접 비교할 수 있는 것은 Batch 3(원논문의 2차 테스트) 하나다.

## 품질 처리

| 대상 | 처리 | 근거 |
|---|---|---|
| Batch 1 의 셀 8, 10, 12, 13, 22 | 제외. 0.88 Ah 에 도달하기 전에 실험이 끝나 수명을 알 수 없음 | 원논문 공식 코드 |
| Batch 2 의 8개 셀 | 제외. `cycle_life` 값이 없는 실험용 셀 | 자체 판단 |
| Batch 3 의 셀 2, 23, 32, 37, 42, 43 | 제외. 측정 노이즈, EOL 미도달 | 원논문 공식 코드 |
| Batch 1 의 셀 0 ~ 4 수명 | 662, 981, 1060, 208, 482 사이클을 더함. 실험이 다음 배치로 이어짐 | 원논문 공식 코드. 보정 후 Table 9 와 일치 |
| Batch 1 의 cycle 1 | 제외. 측정값 없이 0 으로 채워져 있음 | 원논문이 모든 피처를 cycle 2 부터 정의 |
| 방전 용량 1.3 Ah 초과, 내부저항 0 | 결측 처리. 공칭 용량 1.1 Ah 인 셀에서 나올 수 없는 값 | 자체 판단 |

규칙은 `src/config.py` 와 `src/preprocess.py` 에 정의되어 있다. 수명 종료(EOL)는 공칭 용량 1.1 Ah 의 80%인 0.88 Ah 다.
