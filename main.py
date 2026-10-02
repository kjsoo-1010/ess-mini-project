"""전체 파이프라인 실행: 데이터 로딩 -> 피처 계산 -> 후보 모델 비교 -> 모델 선택 -> 평가 -> 결과 저장.

실행
    python main.py              공식 실험 (최종 모델의 학습과 평가)
    python main.py --all        추가 분석까지 (오류 분석, 원논문 방법과의 비교, 단수명 셀 선별)
    python main.py --seed 0 --out results    각 단계에 그대로 전달되는 옵션

단계별로 따로 실행하려면 python -m src.train 처럼 모듈을 직접 실행한다.
"""

from __future__ import annotations

import argparse

from src import analysis, replication, screening, train, zeroshot

EXTRA_STAGES = {
    "오류 분석": analysis,
    "원논문 방법과의 비교": replication,
    "단수명 셀 선별 : 판정 규칙": screening,
    "단수명 셀 선별 : zero-shot 분류기": zeroshot,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="ESS 배터리 수명 예측 파이프라인")
    parser.add_argument("--all", action="store_true", help="공식 실험 뒤에 추가 분석도 실행한다")
    args, stage_options = parser.parse_known_args()  # --seed, --out 은 각 단계가 해석한다

    print("===== 공식 실험 =====")
    train.main(stage_options)
    if args.all:
        for title, stage in EXTRA_STAGES.items():
            print(f"\n===== {title} =====")
            stage.main(stage_options)


if __name__ == "__main__":
    main()
