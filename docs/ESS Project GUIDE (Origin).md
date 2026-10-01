# 🔋 Domain

## ESS - 전력망의 배터리

### Introduction

#### 개념

- ESS, Energy Storage System
- 전기를 필요한 시점에 저장했다가 필요한 시점에 공급하는 시스템
- 발전소처럼 전기를 만드는 것이 아니라, 이미 만들어진 전기를 필요한 시점에 공급하는 역할
    - 발전소 하나를 지을때 리소스가 많이 든다. 그런데 한국이 가장 많이 짓고 있음. 미국은 하나의 도시에 준하는 규모로 짓고 있음.
    - 근데 ESS가 일단 차선? 최선? 인 거 같음.

#### 핵심 역할

- Balancing
    - 전기는 생산과 소비가 실시간으로 일치해야 함
    - 태양광, 풍력은 날씨에 따라 출력이 들쭉날쭉하기 때문에, ESS가 남을 때 저장하고 부족할 때 방출하여 균형을 잡을 수 있게 함
- Peak Shaving
    - 전력 수요는 특정 시간대에 급격히 올라감
    - ESS는 피크 구간에 저장된 전력을 공급하여 비싼 피크 요금과 설비 과부하를 방지할 수 있게 함
- Backup / UPS
    - 정전이나 계통 불안정 시 즉각적으로 전력을 공급해 시스템 연속성을 보장할 수 있음
    - Data Center에서 특히 중요

⇒ 전력 인프라 투자 비용 절감 효과

- 지역 수요 증가로 인해 추가적인 전력 인프라(변전소, 송배전선 등) 확충이 필요한 경우, ESS를 전략적으로 배치하면 인프라 투자 비용을 낮출 수 있음
- ESS는 비상 전력 공급이 가능해 기업이나 산업 현장에 안정성 제공
- [https://x.com/teslaownersSV/status/1977607763779100859](https://x.com/teslaownersSV/status/1977607763779100859)
- [https://www.newsspace.kr/news/article.html?no=13072](https://www.newsspace.kr/news/article.html?no=13072)

### 작동 원리

![Screenshot 2026-03-25 at 10.24.40 AM.png](attachment:747540a1-de87-4545-9655-6d2f5505f0bc:Screenshot_2026-03-25_at_10.24.40_AM.png)

- 충전 시에는 외부 전력(e.g., 태양광)을 받아 인버터가 교류(AC)를 직류(DC)로 변환하여 배터리에 저장
- 방전 시에는 저장된 DC를 다시 AC로 변환해 전력 공급
    - 송전 효율 : 높은 전압으로 송전하면 전력 손실이 줄어들기 때문에 장거리 전력망은 역사적으로 AC 체계로 구축
    - 기존 전력망(Grid) 호환 : 대부분의 가전제품은 모두 AC(한국 기준 220V/60Hz) 전제로 설계
    - 배터리 특성 : 화학 반응 기반으로 전기를 저장하므로 DC로만 충/방전 처리됨. 방전된 DC를 부하에 맞게 AC로 변환하는 과정이 필수적

#### 주요 구성 요소

> Battery Cell → BMS → PCS → EMS

- Battery Cell : 에너지를 실제 저장하는 핵심
    - (참고) 배터리 층위구조 : Cell → Module → Pack/Rack → Container
- BMS, Battery Management System : 배터리 상태 감시 및 보호
    - Cell Voltage Monitoring, 전압 모니터링
    - Temperature Monitoring
    - State 측정
        - SOC, State of Charge : 배터리의 현재 충전량 비율(0~100%). 잔여 용량 파악에 활용
        - SOH, State of Health : 초기 설계 용량 대비 현재 성능 유지율. 배터리 노화 또는 열화 정도를 나타내는 지표
        - SOP, State of Power : 현재 상태에서 즉시 입출력 가능한 최대 전력량. 급격한 충방전 시 과부하 방지에 활용
    - 충전/방전 제어 및 Balancing
    - 이상 발생 시 차단 및 긴급 정지 명령
- PCS, Power Conversion System : 직류(DC)-교류(AC) 변환 처리 시스템 (전력변환 인터페이스 → 전력 품질 유지)
    - ESS 충전 (AC → DC)
    - ESS 방전 (DC → AC)
    - 전력 품질 제어 : 무효전력 보상, 전압 유지, 주파수 조정
    - Grid-tied Operation, 계통 연계
- EMS, Energy Management System : ESS 운영 최적화 및 제어 (충방전 전략 결정)
    - 배터리 SOC 기반 충방전 스케쥴 계획
    - 전력 시장 가격(계통 요금) 분석
    - 피크 관리 알고리즘 설정
    - 계통 연계 시 제한 조건 준수
    - 발전량 예측 (태양광, 풍력 연계 ESS)
    - BMS - PCS 와의 보호 연동 및 비상 운전 전략 관리
    - 긴급 상황 시 차단/정지 명령

### WHY ESS?

- AIDC 전력 수요 폭증 : 2023 → 2030 데이터센터 소비 4배+ (전체 데이터센터는 2배)
- 재생에너지 변동성 대응 : 태양광/풍력 간헐성 해결 → ESS 필수 인프라
- 글로벌 BESS 시장 급팽창 : 2025년 설치량 300GWh 돌파, 전년 대비 +51%
- **배터리 수명 관리** = 핵심 경쟁력 : 교체 비용이 ESS CAPEX 30~40%

Reference :

- AIDC 전력 수요 : [https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai](https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai)
- DC 165% 증가 전망 : [https://www.goldmansachs.com/insights/articles/ai-to-drive-165-increase-in-data-center-power-demand-by-2030](https://www.goldmansachs.com/insights/articles/ai-to-drive-165-increase-in-data-center-power-demand-by-2030)
- BESS 2025년 315GWh/+51% : [https://www.ess-news.com/2026/01/20/global-bess-demand-jumps-51-in-2025-as-installations-top-300-gwh/](https://www.ess-news.com/2026/01/20/global-bess-demand-jumps-51-in-2025-as-installations-top-300-gwh/)
- BESS 시장 전망 2025-2030 : [https://www.marketsandmarkets.com/Market-Reports/battery-energy-storage-system-market-112809494.html](https://www.marketsandmarkets.com/Market-Reports/battery-energy-storage-system-market-112809494.html)
- BESS 심층 분석 : [https://climatedrift.substack.com/p/the-battery-energy-storage-system](https://climatedrift.substack.com/p/the-battery-energy-storage-system)
- [https://n.news.naver.com/mnews/article/277/0005816959](https://n.news.naver.com/mnews/article/277/0005816959)

### 리튬이온 배터리

![Screenshot 2026-03-24 at 3.43.30 PM.png](attachment:d5fdf424-47c2-48f8-b2c2-2d6e338f39b0:Screenshot_2026-03-24_at_3.43.30_PM.png)

- 구성 요소
    - 양극 : 배터리 성능과 스펙을 결정짓는 요소
        - 배터리 전압 : 양극과 음극의 전위차에 의해 결정, 양극 구조에 따른 전위값이 전압에 큰 영향을 미침
        - 업계에서는 양극 성능 향상 위해 양극 활물질을 개선하는데 주력하고 있음
        - 활물질 (Active Material) : 에너지가 들어있는 물질. 리튬이온 배터리는 리튬금속산화물 사용
            - 알루미늄은 전류(전자)를 수집하는 역할 담당
            - 수집된 전류는 탭(전지의 극과 닿는 부분)을 통해 흐름
            - 충전 시에는 전자를 내주는 산화 반응이 일어나고, 방전 시에는 전자를 받는 환원 반응이 일어남
            - 이 때 산화와 환원 반응에 참여하는 것이 리튬금속산화물 ⇒ 배터리의 용량과 전압 결정
    - 음극 : 충전 시 양극에서 방출된 리튬이온을 저장했다가, 방전 시 다시 양극으로 방출하는 역할 (전류 공급원)
        - 구리 : 음극에서 전자를 수집하는 역할을 담당
        - 흑연 : 음극 활물질. 전자와 이온을 받았다가 내보내는 과정에서 물리적인 팽창과 수축 반복 ⇒ 배터리 수명에 영향 미침
    - 분리막 : 양극과 음극의 물리적인 접촉 막는 역할
        - 리튬이온 배터리는 양극과 음극이 닿게 되면 단락(Short) 발생하여 화재로 이어짐
        - 분리막은 이러한 상황을 막아주어 배터리의 안전성을 높이는데 중요한 역할 담당
    - 전해질 : 이온은 통과시키고, 전자는 출입하지 못하게 하여 외부 도선으로 이동 시킴
        - 리튬염을 유기 용매에 녹인 액체 형태가 일반적
        - 최근 고체 전해일(전고체 배터리) 연구 활발
- Lithium-ion : 가장 작고 가벼우면서 강력한 에너지를 오래낼 수 있는 효율성. 하지만 구조적으로 화재에 취약
    - 압도적인 에너지 밀도
        - 리튬은 금속 중 가장 가볍고 전자를 잃기 쉬운 성질을 가지고 있음
        - 이 덕분에 같은 무게나 부피 대비 훨씬 많은 에너지를 저장할 수 있음 ⇒ 경량화 & 고전압
    - 긴 수명과 관리의 편의성
        - 메모리 효과 없음 : 언제든 충전해도 용량 손실이 거의 없음
        - 긴 사이클 수명 : 보통 500회, 많게는 수천번까지 충방전 가능
        - 낮은 자가 방전율 : 사용하지 않을 때 배터리가 자연적으로 소모되는 비율이 한 달에 1.5~2% 미만으로 매우 낮음
    - 생태계와 기술 성숙도
        - 시장 지배력 : 현재 전기차 배터리 수요의 90% 이상 점유, 부품 수급이나 재활용 인프라가 리튬이온 중심으로 짜여져 있음
        - 다양한 변주 : 에너지 밀도가 높은 NCM(니켈, 코발트, 망간) 방식과, 가격이 저렴하고 안전한 LFP(리튬인산, 철) 방식 등으로 분화되어 용도에 맞게 선택할 수 있음
    - 구조적으로 화재와 폭발에 취약
        - 배터리 내부에서 이온이 이동하는 통로인 전해질은 주로 가연성 액체(유기 용매)로 이루어져 있음
        - 해당 전해질은 다음과 같은 상황에서 위험함 :
            - Thermal Runaway : 배터리가 과충전되거나 외부 충격을 받아 내부 온도가 일정 수준(약 130~150도)를 넘어서면 전해질이 기화하며 가스가 발생하고 내부 압력이 급증. 이 때 발생한 열이 주변 셀로 번지면 순식간에 폭발하는 화재
            - Dendrite 현상 : 충방전을 반복하다 보면 음격 표면에 리튬이 나뭇가지 모양의 결정(Dendrite)가 쌓임. 이 결정이 분리막을 뜷으면 단락이 발생해 화제 발생
- Next Generation
    - 전고체 배터리, All-Solid-State Battery
        - 원리 : 가연성 액체 전해질을 불에 타지 않는 고체 전해질로 교체
        - 안전성 : 고체 자체가 분리막 역할까지 담당. Dendrite 의한 단락 위험이 낮고, 열에 강해 폭발 위험이 거의 없음 (So called, 꿈의 배터리)
        - 상태 : 아직 제조 공정이 까다롭고 대당 단가가 너무 높아 양산화 단계에 머물러 있음
    - 나트륨 이온 배터리, Sodium-ion Battery
        - 원리 : 리튬 대신 나트륨 사용
        - 안전성 : 리튬 보다 화학적 반응성이 낮아 열적 안정성 높음. 방전 상태로 운송이 가능해 이동 중 화재 위험이 리튬이온 보다 현저히 낮음
        - 상태 : 리튬 보다 무겁고 에너지 밀도가 낮아 주행 거리가 중요한 장거리 전기차에는 부적합

![Screenshot 2026-03-24 at 3.56.15 PM.png](attachment:81fb9700-2cf5-4987-b0c9-8e1fdced5d59:Screenshot_2026-03-24_at_3.56.15_PM.png)

- 충방전
    - 충전, Charge
        
        - 외부 전원이 에너지를 공급하면 반응이 시작됨
        - 양극의 리튬 이온이 전해질을 통해 음극으로 이동
        - 전자는 외부 회로 통해 음극으로 이동 : 리튬과 전자가 음극에 저장됨 ⇒ 음극에 에너지가 축적된 상태
    - 방전, Discharge
        
        - 부하(전구, 모터 등)에 연결되면 저장된 에너지가 방출됨
        - 음극의 리튬이온이 전해질 통해 다시 양극으로 복귀
        - 전자는 외부 회로를 흘러 부하에 전력 공급
        - 양극과 음극의 리튬 농도 차이가 전압을 만들어냄 ⇒ 농도가 줄수록 전압 하락
    - 열화, Degradation
        
        - 리튬 손실 : 충방전이 반복될수록 리튬이온이 전극에 영구 흡착되어 순환 가능한 리튬 감소(손실)
        - SEI 성장 : 음극 표현에 SEI(Solid Electrolyte Interphase, 고체 전해질 계면) 막이 두꺼워지며 내부 저항 증가
        - 양극 구조 붕괴 : 반복 충방전으로 결정 구조가 무너지며 용량 감소
        - 물리적 열화 : 전극 소재의 물리적 균열, 수축, 팽창이 누적되어 활물질 손실 발생
        
        ⇒ 결과적으로 용량(Capacity) 감소 → SOH 하락 → 결국 EOL(End of Life, 수명 종료) 도달
        

### Battery Index

- State
    - SOC, State of Charge
        - SOC = 현재 충전량 / 최대 충전 가능 용량 * 100 (%)
        - 배터리에 지금 얼마나 충전되어 있는지 (스마트폰 배터리 잔량과 동일한 개념)
        - BMS가 SOC를 기반으로 충방전 제어 및 과충방전 방지
    - SOH, State of Health
        - SOH = 현재 용량 / 초기 용량 * 100 (%)
        - 배터리가 얼마나 건강한지, SOH 80% 이하 → ESS 교체 기준
        - 100 사이클 후 SOH=95% → 아직 5% 열화
    - SOP, State of Power
        - SOP = 현재 출력 가능한 최대 전력 (W)
        - 지금 ESS가 얼마나 빠르게 충방전할 수 있는가
        - SOP 감소 → 피크 대응 능력 저하 신호
- Derived
    - RUL, Remaining Useful Life
        - RUL = EOL 도달까지 남은 사이클 수
        - 언제 교체해야 하는가? → **예지 보전 (PdM)**의 핵심 타겟

### 배터리 교체 비용 = CAPEX 30~40%

- 예측 없이 운영하면
    - 갑자기 배터리 수명 종료 → 예기치 못한 설비 중단
    - 과도한 예방적 교체 → 불필요한 비용 발생
    - 용량 저하 예측 실패 → 피크 대응 불가 → 계약 위약금
    - ESS 1MWh 기준, 셀 교체 비용 $30,000 ~ $80,000
- 데이터 기반 수명 에측
    - 초기 100 사이클만으로 전체 수명 예측 가능
    - 최적 교체 시점을 사전 계획 가능 → 운영 비용 20~35% 절감
    - 열화 속도 예측 → 충방전 전략 최적화
    - 배터리 제조사 수율 선별 → 팩 구성 최적화

## MIT and Stanford Research

- _Data-driven prediction of battery cycle life before capacity degradation_ (Nature Energy, 2019)
    
    [https://www.nature.com/articles/s41560-019-0356-8](https://www.nature.com/articles/s41560-019-0356-8)
    
    ![Screenshot 2026-03-24 at 4.16.32 PM.png](attachment:a7015690-3b18-43b8-a53c-9826cb19284a:Screenshot_2026-03-24_at_4.16.32_PM.png)
    

### Regression - 배터리 수명 예측

- 초기 100 사이클 데이터만으로 배터리의 총 잔여 수명 충전(사이클 수) 예측
- 데이터 : 초기 100 사이클
- Target : `cycle_life` - EOL(80% SOH 도달)까지의 총 사이클 수
- 성능 : 테스트 오차 9.1%

### Classification - 배터리 수명 분류 (Binary)

- 단 5 사이클만으로 배터리의 장/단 수명을 즉시 선별 → 제조 직후 빠른 스크리닝 목표
    
- 데이터 : 초기 5 사이클
    
- Target : `cycle_life` 이진화한 파생 변수로 정의
    
    ```python
    # cycle_life 기준 550사이클로 이진 레이블 생성
    df['label'] = (df['cycle_life'] >= 550).astype(int)
    # 1 = 장수명(Long-life), 0 = 단수명(Short-life)
    ```
    
- 성능 : 테스트 오차 4.9% (1-Accuracy)
    

### Features

- Descriptors : 배터리 수준 스칼라
    - `cycle_life` : EOL(80% 용량)까지 총 사이클 수 ⇒ Target Variable
    - `charging_policy` : 충전 프로토콜 (e.g. : `"4.8C(80%)-3.6C"`- 용량의 80%까지 4.8C 속도로 빠르게 충전하고, 이후 나머지는 3.6C로 천천히 충전한다)
- Summary : 사이클별 요약 스칼라
    - `QD` : 방전 용량 (Ah)
    - `Qc` : 충전 용량 (Ah)
    - `IR` : 내부 저항 (Ohm)
    - `Tmax` / `Tavg` / `Tmin` : 사이클 내 최고, 평균, 최저 온도
    - `chargetime` : 충전 소요 시간
    - `discharge_time` : 방전 소요 시간
- Cycles : 사이클 내부 시계열
    - `t` : 시간 (분)
    - `V` : 전압 (V)
    - `I` : 전류 (A)
    - `T` : 온도 (°C)
    - `Qc`/ `Qd` : 충전/방전 용량
    - `Qdlin` : `ΔQ(V)` 곡선 계산의 기반 데이터, 전압 축으로 선형 보간된 방전 용량 (1,000포인트, 2V ~ 3.6V)
    - `Tdlin` : 전압 축으로 선형 보간된 온도 (1,000 포인트)
    - `discharge_dQdV` : 방전 dQ/dV 곡선 (파생변수)

---

# 🧑‍💻 TASK

- Dataset : [https://www.kaggle.com/datasets/itshpark/data-driven-prediction-of-battery-cycle](https://www.kaggle.com/datasets/itshpark/data-driven-prediction-of-battery-cycle)
    
    |File|Batch|활용|
    |---|---|---|
    |2017-05-12 (2.8GB)|Batch 1|원논문의 학습 데이터셋|
    |2018-02-20 (1.9GB)|Batch 2|원논문의 1차 테스트셋|
    |2018-04-03 varcharge (0.1GB)|extra|충전 최적화 실험용 - 다른 논문 (Attia 2020) 데이터셋|
    |2018-04-12 (3.0GB)|Batch 3|원논문의 2차 테스트셋|
    
- Scratch :
    
    [30-ESSHealth-scratch.ipynb](attachment:59ca0eee-e2b8-4e6a-a82b-01bfc125bdc1:30-ESSHealth-scratch.ipynb)
    

## DAY 1 - 모델 전략 수립

- 대상 Dataset = Batch 1 + Batch 2 + Batch 3
- 아래 5개 질문에 대하여 각 Batch Set에 대한 EDA를 수행하고 Batch간 특징을 비교함
- EDA insight를 토대로 모델 설계 전략 수립

### Question

1. Cycle Life 분포는 어떻게 생겼는가?
    - 150 ~ 2,300 사이클 Histogram
    - 장수명(>1,000)/단수명(<500) 비율 확인
    - 이상치 셀 식별 - 왜 유독 짧은가?
2. 열화 곡선 - 방전 용량이 어떻게 감소하는가?
    - 사이클 별 Qd 추이 시각화
    - 열화 속도가 일정한가, 가속되는가?
    - Knee point - 급격한 열화 시작점 탐색
3. ΔQ(V) ****곡선 - 초기 사이클에서 차이가 보이는가?
    - 사이클 100번 - 사이클 10번의 Q(V) 차이 계산
    - 장수명 셀 vs 단수명 셀의 ΔQ 형태 비교
    - 이를 구분할 수 있는 통계값으로 피쳐 추출
4. 충전 조건 (C-rate)과 수명의 관계는?
    - 충전 프로토콜별 평균 수명 비교
    - 고속 충전 셀이 정말 수명이 짧은가?
    - 충전 전류 패턴과 열화 속도 상관 분석
5. 상관관계 - 어떤 신호가 수명과 연관되어 있는가?
    - 초기 사이클 피켜들과 Cycle Life 상관 계수 확인
    - 가장 강한 관계 식별
    - 멀티클리니어리티 문제 확인

### 모델 설계 전략

1. Feature Engineering : EDA에서 발견한 내용 토대로 유의미한 변수 선별
2. Regression vs Classification
    - 논문에서는 두 가지 모델링 모두 진행
    - 과제에서는 하나의 방법만 선택하고, 이를 설명하는 Target Variable 선정
3. Modeling Strategy : **확인된 데이터 특성 기반으로** 모델링 전략(데이터 처리, 후보 모델 선정 등)을 제시

## DAY 2 - 모델 개발 및 평가

모델 설계 전략을 기반으로 **최적의 모델을 개발**하고, 논문에서 제시한 성능(Target)과 비교

- Modeling (mandatory)
    - Batch 1을 학습 데이터셋으로, Batch 2를 테스트 데이터셋
- additional (not mandatory)
    - 개발한 최적 모델로 Batch 3 테스트 데이터셋으로 추가 성능 검증
    - 단 Batch 3 데이터셋은 배치 간 차이 있어 성능이 떨어질 수 있음
    - Batch 3 :
        - Cycle Life 분포가 배치 별로 상이 : Batch 1/2는 유사하지만, Batch 3는 분포 차이 있음
        - 충전 커브 시작 시점이 배치별로 상이 : `Qdlin` 변수를 단순 비교하면 왜곡 발생
        - 이상치 제거 고려 : 배치 수집 시기 사이에 수개월 공백이 있어, 일부 셀은 데이터 품질 문제로 원논문에서도 제거됨

### Performance Reporting

모델 성능은 아래 항목으로 구분하며, Format 맞춰 작성함

- Index :
    - Train (Batch 1 CV) : Batch 1 내 Cross-Validation 평균 성능
    - Valid (Batch 1 Hold-out) : Batch 1 내 Hold-out 검증 성능
        - Valid를 CV가 아닌 Hold-out으로 사용하는 이유 :
            - 배터리 데이터는 셀 단위로 독립적이며, 각 셀이 서로 다른 충전 프로토콜(C-rate)로 실험됨
            - 이 경우 CV를 적용하면 동일 프로토콜 셀이 train/valid에 나뉘어 들어가 데이터 누수(leakage) 위험 잔존
            - Hold-out은 셀 단위 분리를 명확히 보장하며, 배치 간 일반화를 평가하는 이번 프로젝트 구조에서 더 적합
    - Test (Batch 2) : Batch 2 최종 평가 성능
    - Gap (Train-Valid) : Train 과적합 확인
    - Gap (Valid-Test) : 배치 간 일반화 차이 확인
    - Gap (Target-Test) : 원논문 성능 대비 차이
        - 원논문 성능 : Regression 9.1%(MAPE), Classification 4.9%(1-Accuracy)
        - Performace Metric
            - Regression : MAPE
            - Regression : F1-Score, Accuracy
- Format :
    - Reporting format (for Regression)
        
        |구분|MAPE (%)|비고|
        |---|---|---|
        |Train (Batch 1 CV)|||
        |Valid (Batch 1 Hold-out)|||
        |Test (Batch 2)|||
        |Gap (Train-Valid)||(+) : 과적합 의심|
        |Gap (Valid-Test)||(+) : 배치간 일반화 저하 의심|
        |Gap (Target-Test)||Target : 원논문 9.1%|
        
    - Reporting format (for Classification)
        
        |구분|F1-Score|Accuracy|비고|
        |---|---|---|---|
        |Train (Batch 1 CV)||||
        |Valid (Batch 1 Hold-out)||||
        |Test (Batch 2)||||
        |Gap (Train-Valid)|||(+) : 과적합 의심|
        |Gap (Valid-Test)|||(+) : 배치간 일반화 저하 의심|
        |Gap (Target-Test)|||Target : Accuracy 95.1%|
        
    - Reporting format (for Batch 3 — additional, not mandatory)
        
        - Batch 3까지 진행한 팀은 아래 항목을 추가로 작성
            
        - Batch 2 결과와 나란히 비교하여 모델의 배치 간 일반화 수준을 입체적으로 평가함
            
            - Batch 3은 원논문의 2차 테스트셋으로, Batch 2 대비 수명 분포가 다름
            - Gap (Batch 2 - Batch 3)이 크게 벌어진다면 피처가 특정 배치에 과적합되었을 가능성을 분석하고 원인을 제시
        - for Regression
            
            |구분||MAPE (%)|비고|
            |---|---|---|---|
            |Train (Batch 1 CV)||||
            |Valid (Batch 1 Hold-out)||||
            |Test (Batch 2)||||
            ||Gap (Train-Valid)||(+) : 과적합 의심|
            ||Gap (Valid-Test)||(+) : 배치간 일반화 저하 의심|
            ||Gap (Target-Test)||Target : 원논문 9.1%|
            |Test (Batch 3)||||
            ||Gap (Batch2-Batch3)||Test 성능 간 비교|
            ||Gap (Target-Test)||Batch 3 기준, 원논문 성능 비교|
            
        - for Classification
            
            |구분||F1-Score|Accuracy|비고|
            |---|---|---|---|---|
            |Train (Batch 1 CV)|||||
            |Valid (Batch 1 Hold-out)|||||
            |Test (Batch 2)|||||
            ||Gap (Train-Valid)|||(+) : 과적합 의심|
            ||Gap (Valid-Test)|||(+) : 배치간 일반화 저하 의심|
            ||Gap (Target-Test)|||Target : Accuracy 95.1%|
            |Test (Batch 3)|||||
            ||Gap (Batch2-Batch3)|||Test 성능 간 비교|
            ||Gap (Target-Test)|||Batch 3 기준, 원논문 성능 비교|
            

---

# ✍️ Deliverables

- 모든 산출물은 반별 채널, slack thread로 제출
    
- [모델 전략 수립 (DAY 1)](https://app.notion.com/p/32d7f4c8669380338a27f90c471c1fcb?pvs=21)
    
    - EDA Question에 대하여 확인한 내용에 대하여 정리
        
        - 그래프 나열식 안됨 ❌
        - 확인한 핵심 내용(그래프 + 해석) & 시사점 도출❗
    - 모델 설계 전략 중
        
        - Modeling Strategy는 후보 모델을 list-up 하되, EDA 시사점과 연결되도록 작성
    - (참고) EDA to Model Strategy :
        
        - 주제 : 시계열 데이터를 활용한 배달 매출 예측 분석
            
        - INPUT
            ![[e4dba816210255ae796ad24c33f916b4df2ab639320ea17097cb0176789caa1c.png]]
            
            
        - EDA
            ![[43eed08db4d0a4a90363481a2ee499d38ba0989fb7d62ff0919708450bfc58ed.png]]
            ![[15a44ccf2022c71ae18801152a6507fcbc0d6cd1a18bd0d0241a2bb117e77a5d.png]]
            
        
            
        - 데이터 기반의 모델링 전략 수립
            ![[c49a2c189b5cd1e2180287b65cc85659127a5f15dc53f8e4f905f9bf7e3e46b1.png]]
            
            
    - 제출 :
        
        - `DS-MINI-Design-{캠퍼스_X반}-{이름1+이름2}.pdf`
        - 마감 : DAY1, 17시
- [모델 개발 및 평가 (DAY 2)](https://app.notion.com/p/32d7f4c8669380338a27f90c471c1fcb?pvs=21)
    
    - Github
        
        - `README.md`는 아래 샘플 참고하여 간결하고 명확하게 작성
            
        - README (sample) :
            
            ```markdown
            # ESS 배터리 수명 예측 
            목적 작성 
            
            ## 프로젝트 개요
            - 데이터셋 : MIT-Stanford Battery Dataset (Severson et al., Nature Energy 2019)
            - 학습 데이터 : Batch 1 (2017-05-12)
            - 평가 데이터 : Batch 2 (2018-02-20)
            - 태스크 : Regression (Cycle Life 예측) / Classification (장단수명 분류)  ← 택1 
            
            ## 파일 구조 (sample) 
            ```
            
            ├── data/  
            │ └── [README.md](http://README.md)  
            ├── notebooks/  
            │ ├── 01_EDA.ipynb  
            │ ├── 02_feature_engineering.ipynb  
            │ └── 03_modeling.ipynb  
            ├── src/  
            │ ├── [preprocess.py](http://preprocess.py)  
            │ ├── [features.py](http://features.py)  
            │ └── [train.py](http://train.py)  
            ├── results/  
            │ └── model_performance.csv  
            ├── requirements.txt  
            └── [README.md](http://README.md)
            
            ````
            
            ## 환경 설정 (sample) 
            ```bash
            git clone <https://github.com/팀명/ess-battery-project>
            cd ess-battery-project
            pip install -r requirements.txt
            ````
            
            ## EDA
            
            - Cycle Life 분포
                
                - 분포 형태 및 장단수명 비율 요약
                - 핵심 발견 : (팀이 발견한 인사이트를 한 줄로)
            - 열화 곡선 분석
                
                - 장수명 vs 단수명 셀의 열화 속도 차이
                - Knee point 존재 여부 및 발생 시점
                - 핵심 발견 :
            - ΔQ(V) 곡선 분석
                
                - Cycle 100 - Cycle 10 차이 곡선 형태
                - 장단수명 셀 간 ΔQ 형태 비교
                - 핵심 발견 :
            - 충전 속도(C-rate)와 수명의 관계
                
                - 충전 프로토콜별 평균 수명 비교 결과
                - 핵심 발견 :
            - (추가 확인한 내용 작성)
                
            
            ## Modeling
            
            ### 피처 엔지니어링 전략
            
            EDA 결과를 바탕으로 선택한 피처와 그 근거를 기술
            
            ### 모델 선택 및 근거
            
            - 후보 모델 :
            - 최종 모델 :
            - 선택 이유 :
            
            ## 성능 결과
            
            Format에 맞춰 작성
            
            ## 오류 분석
            
            - 모델이 가장 크게 틀린 셀의 공통점
            - 원인 가설 및 개선 방향
            
            ## ESS 도메인 해석
            
            분석 결과를 실제 ESS 운영 관점에서 해석
            
            - 이 모델을 실제 BESS에 적용한다면 어떤 의사결정에 활용 가능한가?
            - 어떤 한계가 있으며, 실 배포를 위해 추가로 필요한 것은 무엇인가?
            
            ## 참고문헌
            
            - Severson et al. (2019). Data-driven prediction of battery cycle life before capacity degradation. _Nature Energy_, 4, 383–391.
            
            ## 팀 구성
            
            - 김영희 : EDA, 피처 엔지니어링, 모델 개발, 성능 평가(Batch2)
            - 박철수 : EDA, 피처 엔지니어링, 모델 개발, 성능 평가(Batch3)
            
    - 원논문과 비교한 성능 지표 반영 - GAP(Target-Test) : Batch 2 대상
        
    - 제출 :
        
        - Github Link (public)
        - 마감 : DAY2, 16시
- (참고) 산출물 평가 항목 :
    
    |구분|평가항목|평가 내용|배점|총점|
    |---|---|---|---|---|
    |모델 전략 수립|EDA|• 핵심 변수 분포 탐색|||
    
    ```
    • 통계량 확인 및 해석
    • Feature Selection & Engineering | 50 |  |
    ```
    
    | | EDA → 전략 연결성 | • EDA 기반으로 시사점 도출  
    • 연결 논리의 일관성 | 30 | |  
    | | 모델링 전략 수립 | • Feature 설계 논리  
    • 모델 선택 논리 | 20 | 100 |  
    | 모델 개발 및 평가 | 전략 → 구현 반영 | • 전략 기반으로 Feature 및 모델 구현 | 20 | |  
    | | Pipeline 개발 | • 개발 파이프라인  
    • 데이터 분할 적절성  
    • 핵심 변수 구현 | 40 | |  
    | | 성능 리포팅 및 해석 | • 성능 정리 (포맷 기반)  
    • 목표 성능 대비 Gap 해석력 | 20 | |  
    | | 분석 결과 해석 | • 분석 결과의 도메인 관점 해석  
    • 개발 한계점 도출 | 20 | 100 |