# 데이터

원본 데이터는 저장소에 올리지 않는다. 실행하면 kagglehub 가 자동으로 내려받아 캐시에 둔다.

- 출처 : <https://www.kaggle.com/datasets/itshpark/data-driven-prediction-of-battery-cycle> (약 5 GB)
- 원논문 : Severson et al. (2019), *Data-driven prediction of battery cycle life before capacity degradation*, Nature Energy 4, 383–391

| 파일 | 구분 | 용도 |
|---|---|---|
| `2017-05-12_batchdata_updated_struct_errorcorrect.mat` | Batch 1 | 학습 |
| `2018-02-20_batchdata_updated_struct_errorcorrect.mat` | Batch 2 | 테스트 |
| `2018-04-12_batchdata_updated_struct_errorcorrect.mat` | Batch 3 | 추가 테스트 |
| `2018-04-03_varcharge_batchdata_updated_struct_errorcorrect.mat` | - | 사용하지 않음 |

이미 내려받은 파일이 다른 폴더에 있으면 환경변수로 위치를 지정한다.

```bash
export ESS_DATA_DIR=/path/to/mat/files
```

배치별 제외 셀과 값 보정 규칙은 `src/config.py` 와 `src/preprocess.py` 에 정의되어 있다.
