# 심사관 인용 문헌 기반 자율형 선행기술 조사 연구: 데이터셋 평가 및 실험 방법론 제안

## 1. 데이터셋 적합성 평가 (Dataset Suitability Evaluation)

본 평가는 `/home/arkwith/Dev/paper_data/notebooks/` 경로의 `02_kipris_dataset_builder.ipynb` 및 `03_kipris_fulltext_collector.ipynb` 코드를 통해 수집된 데이터가 **"심사관 인용 문헌 기반의 자율형 선행기술 조사 연구"**에 적합한지를 분석한 결과입니다.

### 1.1 연구 목적과의 부합성 (Alignment)
- **연구의 핵심**: 심사관이 특허 심사 과정에서 공식적으로 인용한 문헌(Examiner Citation)을 정답(Ground Truth, GT)으로 설정하고, AI 에이전트가 이를 얼마나 자율적으로 찾아낼 수 있는지 검증하는 것.
- **데이터셋(02번 코드)의 강점**:
    - **심사관 인용 필터링**: `examinerQuotationFlag='Y'` 조건을 적용하여, 단순 유사 특허가 아닌 **특허의 등록 여부를 결정지은 결정적 선행기술(Killer Prior Art)**만을 GT로 확보했습니다. 이는 선행조사 에이전트의 성능을 평가하는 가장 객관적이고 엄격한 기준이 됩니다.
    - **전략 메타데이터**: `meta.search_strategy`를 기록함으로써, 해당 특허가 어떤 검색 전략(키워드, IPC 등) 하에서 수집되었는지 역추적할 수 있어, 에이전트의 검색 전략 학습이나 비교 실험에 유용합니다.

### 1.2 모집단 선정의 타당성 (Cohort Selection)
- **거절(Reject-Only) 코호트의 가치 (03번 코드)**:
    - 선행기술조사 연구에서는 '등록된 특허'보다 **'거절된 특허'**가 더 가치 있는 테스트베드입니다.
    - 거절된 특허는 심사관이 제시한 선행기술(X, Y 문헌)에 의해 신규성/진보성이 부정된 케이스이므로, **"이 선행기술 때문에 거절되었다"**는 인과관계가 명확합니다.
    - 03번 코드에서 `register_status` 등을 기반으로 거절 건을 선별 수집하는 방식은 에이전트에게 **"거절 근거를 찾아라"**는 명확한 미션을 부여할 수 있게 합니다.

### 1.3 데이터 완결성 (Completeness)
- **Full-text 확보**: 단순 서지정보(Title/Abstract)만으로는 정밀한 선행조사(청구항 대비 구성요소 비교)가 불가능합니다. 03번 코드는 타겟과 선행기술의 **청구항(Claims), 상세설명(Description)** 원문을 수집하므로, LLM 기반의 RAG(Retrieval-Augmented Generation) 실험에 필수적인 데이터를 제공합니다.
- **비특허문헌(NPL) 포함**: 반도체/AI 분야는 기술 변화가 빨라 논문 등 비특허문헌이 중요한 선행기술이 됩니다. 03번 코드가 NPL의 웹 텍스트 수집을 시도하는 것은 실전 선행조사 환경을 잘 반영하고 있습니다.

### 1.4 한계 및 보완점
- **해외 특허/NPL 접근성**: KIPRIS 외의 해외 특허나 NPL은 크롤링에 의존하므로 일부 누락이 발생할 수 있습니다. (현재 코드는 캐싱 및 예외처리로 이를 보완 중)
- **텍스트 품질**: PDF 파싱 텍스트는 표/수식 등이 깨질 수 있으므로, 에이전트 실험 시 이를 감안한 전처리나 멀티모달 접근이 고려될 수 있습니다.

---

## 2. AI Agent 기반 선행기술조사 자동화 실험 방안 (Proposed Methodology)

수집된 데이터셋을 활용하여 수행할 수 있는 구체적인 실험 방법론을 수식과 논리적 기호로 정의합니다.

### 2.1 Problem Formulation

Let $T$ be a target patent application, defined as a tuple of its textual components:
$$ T = (C_{claims}, C_{abstract}, C_{desc}) $$
where $C_{claims}$ denotes the claims, $C_{abstract}$ the abstract, and $C_{desc}$ the description.

Let $\mathcal{D}$ be the universe of all available prior art documents (patents and NPLs).
Let $GT(T) \subset \mathcal{D}$ be the set of **Ground Truth** prior arts cited by the examiner for $T$, specifically those that contributed to the rejection (e.g., X/Y citations).

The objective of the AI Agent $\mathcal{A}$ is to approximate the examiner's search process and output a ranked list $R_K$:
$$ R_K = \mathcal{A}(T; \mathcal{D}) = [d_1, d_2, \dots, d_K] $$
such that the recall of $GT(T)$ within $R_K$ is maximized.

### 2.2 Agent Workflow ($\mathcal{A}$)

The agent process $\mathcal{A}$ is modeled as a sequential decision process:

**Step 1: Query Formulation ($f_{query}$)**
The agent extracts key components $k_i$ from claims and expands them into a set of search queries $Q$:
$$ K = \text{Extract}(C_{claims}) = \{k_1, k_2, \dots, k_m\} $$
$$ Q = f_{query}(K) = \{q_1, q_2, \dots, q_n\} $$
where $q_i$ consists of keywords and IPC/CPC classification codes.

**Step 2: Retrieval ($f_{retrieve}$)**
The agent retrieves a candidate set $\mathcal{C}_{cand}$ from the environment (Search API or Vector DB):
$$ \mathcal{C}_{cand} = \bigcup_{q \in Q} \text{Search}(q, \mathcal{D}) $$
where $|\mathcal{C}_{cand}| \gg K$ (e.g., 100~500 documents).

**Step 3: Relevance Scoring & Ranking ($f_{rank}$)**
For each candidate $d \in \mathcal{C}_{cand}$, the agent computes a relevance score $S(d, T)$ based on semantic similarity and logical entailment:
$$ S(d, T) = \alpha \cdot \text{Sim}_{vec}(E(d), E(T)) + \beta \cdot \text{LLM}_{eval}(d, C_{claims}) $$
where:
*   $\text{Sim}_{vec}$: Cosine similarity of embeddings.
*   $\text{LLM}_{eval}$: A function returning a score $[0, 1]$ indicating if $d$ invalidates elements of $C_{claims}$.

The final ranked list is:
$$ R_K = \text{Top}_K(\mathcal{C}_{cand}, S) $$

**Step 4: Feedback Loop (Optional)**
If $\max_{d \in R_K} S(d, T) < \tau$ (threshold), the agent refines queries:
$$ Q' = f_{refine}(Q, R_K) $$
and repeats Step 2.

### 2.3 Experimental Design

*   **Dataset Split**:
    *   $\mathcal{T}_{total} = \{T_1, \dots, T_N\}$ (Collected Dataset)
    *   $\mathcal{T}_{train} \subset \mathcal{T}_{total}$ (20%): Used for few-shot prompting of $f_{query}$ and $f_{rank}$.
    *   $\mathcal{T}_{test} \subset \mathcal{T}_{total}$ (80%): Used for evaluation, specifically focusing on $T$ where $Status(T) = \text{Rejected}$.

*   **Baselines**:
    *   $\mathcal{B}_{keyword}(T)$: TF-IDF / BM25 based retrieval.
    *   $\mathcal{B}_{dense}(T)$: Embedding-based dense retrieval ($E(T) \cdot E(d)$).

### 2.4 Evaluation Metrics

For a given test set $\mathcal{T}_{test}$:

1.  **Recall@K (Relevance)**
    $$ \text{Recall}@K = \frac{1}{|\mathcal{T}_{test}|} \sum_{T \in \mathcal{T}_{test}} \frac{|R_K(T) \cap GT(T)|}{|GT(T)|} $$
    *   *Goal*: $\text{Recall}@10 \ge 0.7$

2.  **Precision@K (Efficiency)**
    $$ \text{Precision}@K = \frac{1}{|\mathcal{T}_{test}|} \sum_{T \in \mathcal{T}_{test}} \frac{|R_K(T) \cap GT(T)|}{K} $$

3.  **Mean Reciprocal Rank (MRR)**
    $$ \text{MRR} = \frac{1}{|\mathcal{T}_{test}|} \sum_{T \in \mathcal{T}_{test}} \frac{1}{\text{rank}_i} $$
    where $\text{rank}_i$ is the rank of the first relevant document in $R_K(T)$.

## 3. AI Agent 프레임워크 및 워크플로 상세 (Framework Description)

앞서 수식으로 정의된 모델을 실제 시스템으로 구현하기 위한 에이전트 프레임워크의 구성요소와 동작 흐름을 서술합니다.

### 3.1 프레임워크 구성요소 (Components)
본 연구의 AI 에이전트는 단순한 검색기가 아닌, 인간 조사관의 사고 과정을 모사하는 **Cognitive Agent**로 설계됩니다.

1.  **Query Planner (전략 수립 모듈)**
    *   **역할**: 타겟 특허의 청구항을 분석하여 검색 전략을 수립합니다.
    *   **기능**:
        *   청구항의 구성요소(Element) 분해.
        *   각 구성요소에 대한 동의어/유의어 확장 (Synonym Expansion).
        *   기술 분야에 맞는 IPC/CPC 분류 코드 예측.

2.  **Search Executor (검색 실행 모듈)**
    *   **역할**: 실제 검색 엔진(KIPRIS, Google Patents, Vector DB)과 상호작용합니다.
    *   **기능**:
        *   Boolean 검색식 생성 및 API 호출.
        *   Vector DB를 활용한 의미 기반(Semantic) 검색 수행.
        *   검색 결과의 메타데이터(서지정보) 수집.

3.  **Relevance Evaluator (적합성 판단 모듈)**
    *   **역할**: 수집된 문헌이 타겟 발명의 신규성/진보성을 부정할 수 있는지 판단합니다.
    *   **기능**:
        *   **1차 필터링**: 제목/요약 기반의 경량화된 관련성 평가.
        *   **2차 정밀 평가(Deep Compare)**: 원문(Full-text)의 청구항/상세설명을 타겟 청구항과 1:1로 비교하여 매핑되는 문장을 식별.

4.  **Feedback Loop (자율 개선 모듈)**
    *   **역할**: 검색 결과가 불충분할 경우 전략을 수정합니다.
    *   **기능**:
        *   검색된 문헌이 타겟과 기술 분야가 다르거나 관련이 적을 경우, 쿼리(키워드/IPC)를 수정하여 재검색(Iterative Refinement)을 수행합니다.

### 3.2 워크플로 시나리오 (Workflow Scenario)
1.  **입력**: 에이전트에게 타겟 특허의 청구항 1항과 요약서가 입력됩니다.
2.  **전략 수립**: 에이전트는 청구항을 "A(구성) + B(기능)" 형태로 구조화하고, 핵심 키워드셋을 생성합니다.
3.  **탐색적 검색**: 1차적으로 광범위한 검색을 수행하여 후보군(Pool)을 확보합니다.
4.  **평가 및 선별**: 후보군 내에서 타겟 발명의 핵심 구성요소를 모두 포함하는(All-element rule) 문헌을 우선순위로 랭킹을 매깁니다.
5.  **최종 출력**: 심사관이 인용했을 법한 최상위 $K$개의 문헌 리스트와, 각 문헌이 선정된 이유(Reasoning)를 리포트로 생성합니다.

## 4. 결론
`/home/arkwith/Dev/paper_data/notebooks/`의 두 코드로 구축된 데이터셋은 **"심사관의 판단(GT)"**과 **"거절된 출원(Negative Sample)"**이라는 고품질의 레이블을 포함하고 있어, **자율형 선행기술 조사 에이전트의 성능을 정량적으로 검증하기에 최적화된 데이터셋**입니다. 제안된 실험 방안을 통해 단순 검색을 넘어선 '추론 기반 조사'의 가능성을 확인할 수 있을 것으로 기대됩니다.
