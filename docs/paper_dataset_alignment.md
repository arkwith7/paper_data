# 논문 정합성 메모 (심사관 인용 문헌 기반)

이 문서는 “논문에서 의도한 실험 설정”을 현재 레포의 산출물/파이프라인과 1:1로 대응시키고, 논문과 비교 가능한 결과를 얻기 위해 **무엇이 위험(정합성 리스크)** 인지와 **실험 전에 어떤 변경이 필요한지(구체 작업)** 를 정리합니다.

현재 레포의 핵심 아티팩트는 다음과 같습니다.

- 데이터셋(JSONL): `data/processed/kipris_semiconductor_ai_dataset.jsonl`
- 빌더 노트북: `notebooks/02_kipris_dataset_builder.ipynb`
- 원문 수집(Fulltext) 노트북: `notebooks/03_kipris_fulltext_collector.ipynb`

## 1) 논문이 “측정하려는 것” (운영 관점 정의)

논문의 실험 설정을 운영(implementation) 관점에서 풀어쓰면 다음과 같습니다.

- **시스템 입력(Query):** “발명의 공개(invention disclosure)”를 근사하는 텍스트. 논문은 보통 *제목 + 초록 + 청구항 1(Claim 1)* 조합을 제안합니다.
- **정답 집합(Ground truth):** *심사관 인용 문헌(examiner-cited documents, ‘심사관 인용’)* 을 타겟 특허별 relevant set으로 간주합니다.
- **과제(Task):** 코퍼스에서 심사관 인용 문헌을 RAG/에이전트 반복(Iteration)으로 검색/회수합니다.
- **평가지표(Metrics):** Recall@K / Precision@K / MRR / Miss Rate (타겟별, 필요 시 iteration별).

따라서 논문과 정합성을 맞추려면 아래 2가지가 반드시 성립해야 합니다.

1) Ground truth는 **심사관 인용만(examiner-only)** 이어야 하고, 출원인/자기 인용(applicant/self-citation)이 섞이면 안 됩니다.
2) Query 입력은 **청구항 1(Claim 1)** 을 포함해야 합니다. 포함이 어렵다면, 대체 근사(예: 제목+초록) 사용을 “편차(deviation)”로 명시하고 결과를 분리 보고해야 합니다.

## 2) 현재 레포가 이미 잘 맞는 부분

- `kipris_semiconductor_ai_dataset.jsonl`에 **타겟 → 인용 문헌 매핑** 이 존재합니다.
- 원문 수집 파이프라인이 이미 **검색 코퍼스 구축** 형태로 동작합니다.
  - KIPRIS Plus PDF → 텍스트 추출 (`getPubFullTextInfoSearch` → PDF 다운로드 → 추출)
  - 비-KR 선행문헌은 Google Patents HTML을 보조 소스로 사용
- NPL이 `prior_art_npl_values`로 **분리** 되어 있어, “특허만” 대상으로 실험할 때 조용히 섞여 들어가 결과를 오염시키는 위험이 낮습니다.

즉, 벡터 스토어 구축 및 Top-K 검색 실험을 시작하기 위한 기반은 이미 갖춰져 있습니다.

## 3) 논문 대비 갭/리스크

### A. 현재 Ground truth가 “심사관 인용만”이 아닐 가능성

JSONL의 `meta.search_policy`를 보면 현재 데이터는 **experiment** 모드로 빌드된 것으로 보입니다.
`02_kipris_dataset_builder.ipynb`에서 `get_prior_art(..., policy="paper")`는 `examinerQuotationFlag == 'Y'`로 필터링하지만, `policy="experiment"`는 더 넓은 집합을 허용합니다.

**왜 중요한가:** 심사관 인용만을 대상으로 평가해야 논문이 말하는 “examiner-cited prior art retrieval”에 해당합니다. 인용이 혼합되면 (재현이 아니라) 다른 과제를 푸는 것이 됩니다.

**권장:** 타겟별로 ground truth를 2종으로 명시적으로 저장하세요.

- `ground_truth_examiner_prior_arts`
- `ground_truth_all_prior_arts`

그러면 (a) 논문 정합 실험과 (b) 확장 실험을 라벨링해서 병렬로 운영할 수 있습니다.

### B. 데이터 스키마에 Claim 1이 없음

현재 `target_patent`에는 제목/초록 등은 있으나 **청구항 1 필드가 없습니다**.

**왜 중요한가:** Query를 제목+초록만으로 구성하면 논문이 제시한 입력 프록시와 달라져 결과 비교 가능성이 떨어집니다.

**권장 옵션(하나를 선택하고 문서화):**

1) **권장(Preferred):** KIPRIS PDF 전문에서 Claim 1을 추출하여, 데이터셋 빌드 단계 또는 후처리 단계에 `target_patent.claim_1`(또는 유사 필드)을 추가합니다.
2) **대안(Fallback):** Claim 추출 품질이 불안정하다면, 명시적으로 대체 프록시(예: 제목+초록)를 정의하고, Claim 1 포함/미포함을 ablation으로 분리해 보고합니다.

### C. 타겟 선정 기준(기간/등록특허)이 논문과 다를 수 있음

논문 예시는 보통 최근(예: 2023–2024) KR **등록** 특허를 샘플링합니다.
현재 데이터셋은 주제 기반 필터(“semiconductor_ai”)로 보이며, 등록특허-only 또는 특정 기간으로 강제되지 않았을 수 있습니다.

**왜 중요한가:** 기간/상태에 따라 인용 관행과 문서 가용성이 달라지고, 이는 검색 난이도와 성능 수치에 직접 영향을 줍니다.

**권장:** 빌더 단계에서 타겟 필터를 명시적으로 잠그세요.

- KR only (논문이 KR 중심이면)
- registered-only (논문 설정이 등록특허라면)
- 고정 기간(예: 2023-01-01 ~ 2024-12-31)

### D. 코퍼스 완전성/언어 왜곡(소스 편차)

- Google Patents HTML은 섹션 누락(청구항/명세서 누락 등)이 생기거나, 언어 라우트에 따라 내용이 달라질 수 있습니다.
- 비-KR 문서는 Google Patents에서 번역/정규화 방식이 문서별로 달라질 수 있습니다.

**왜 중요한가:** 문서 소스가 일관되지 않으면, 모델 성능이 아니라 “텍스트 품질 차이”가 결과를 좌우할 수 있습니다.

**권장:**

- 가능하면 PDF 소스를 우선하세요(KR은 KIPRIS; JP/CN/WO/EP/US는 가용한 대체 소스가 있으면 활용).
- 문서별 provenance를 기록하세요(`source="kipris_pdf" | "google_patents_html"`). 필요하면 provenance가 균일한 서브셋에서 별도 평가를 수행합니다.

### E. NPL 처리가 논문 정합 과제에서 정의되지 않음

현재는 NPL 전문 수집을 건너뜁니다.

**왜 중요한가:** 심사관 인용에 NPL이 포함된다면, NPL을 코퍼스/GT에서 제외하는 순간 ground truth 정의가 바뀝니다.

**권장(둘 중 하나 선택):**

- 논문 정합 실험을 *특허 선행문헌만* 으로 제한하고, NPL 제외 비율(심사관 인용 중 NPL 비중)을 함께 보고하거나
- NPL 수집 경로(DOI/Crossref/PDF 등)를 추가해, NPL도 코퍼스의 일부로 포함합니다.

### F. 평가 프로토콜에서 반드시 고정해야 하는 디테일

RAG 평가에서 자주 발생하는 실패 포인트는 다음과 같습니다.

- **Self-match leakage:** 타겟 특허 자체가 검색 결과 후보에 들어가지 않도록 제외해야 합니다.
- **중복 처리(Deduping):** 동일 문서가 kind code/표기 차이로 여러 개로 나타나면 하나의 canonical key로 정규화해야 합니다.
- **패밀리 처리(Family conflation):** 인용이 패밀리 멤버를 가리킬 때 hit로 인정할지 기준을 정해야 합니다.

**권장:** canonical doc-id 정규화를 구현하고, 아래 3곳에서 동일하게 사용하세요.

- ground truth 키
- 코퍼스 문서 id
- 검색 결과(리트리버 출력) id

## 4) 논문 정합 상태로 만들기 위한 “다음 변경 사항”

1) **심사관-only ground truth로 데이터셋 재빌드**
   - `02_kipris_dataset_builder.ipynb`에서 prior-art policy를 심사관-only 모드로 설정합니다(노트북에 이미 관련 로직이 존재).
   - 확장 실험도 유지하려면 examiner-only와 all-citations를 둘 다 저장합니다.

2) **`target_patent`에 Claim 1 추가**
   - KR 타겟은 KIPRIS PDF에서 Claim 1을 추출하거나, Claim 1 미포함을 ablation으로 명시합니다.

3) **타겟 선정 기준 고정**
   - 빌더에서 국가/등록 상태/기간 필터를 명시적으로 추가합니다.
   - 재현성을 위해 이 기준을 `meta` 필드에 기록합니다.

4) **실험 친화 메타데이터 추가**
   - 타겟별: `query_text`(실제로 사용한 문자열), `ground_truth_type`(examiner/all), 각종 count.
   - 문서별: `source`, `language`, `collection_timestamp`.

5) **수집 텍스트 품질 게이트**
   - 아래 조건을 플래그 처리(필요 시 재수집):
     - 텍스트가 비정상적으로 짧음
     - claims/description 섹션 누락
     - 깨짐(mojibake)/인코딩 아티팩트

## 5) (어쩔 수 없이) 편차가 생길 때의 서술 방식

논문 설정을 100% 맞추기 어렵더라도, 편차를 명확히 선언하면 연구 보고가 깔끔해집니다. 예:

- “심사관 인용 중 특허 문헌만을 대상으로 평가하며, NPL 인용은 제외했다.”
- “Claim 1 추출 품질 이슈로 Query는 제목+초록만 사용했고, 이를 ablation으로 분리 보고했다.”
- “해외 선행문헌 전문은 Google Patents HTML에서 수집했으며, provenance와 실패율을 함께 보고했다.”

핵심은 **ground truth 정의** 와 **query 입력 정의** 를 일관되고 감사 가능(auditable)하게 유지하는 것입니다.
