# plan-preflight

**한국어** | [English](README.en.md)

**구현 계획서를 위한 이륙 전 점검(preflight check).**

코드를 한 줄 쓰기 전에 계획 문서를 **PASS / FAIL 이진 판정**으로 닫아주는
[Claude Code](https://claude.com/claude-code) 스킬입니다. 두 AI 리뷰어가
계획서를 독립적으로 검토하고, 계약 수준 결함은 자동으로 수정되며, 게이트가
닫힐 때까지 재리뷰를 돕니다 — 보통 1~3라운드면 끝납니다.

```
/plan-preflight docs/payment-refund-plan.md
```

```
[PROGRESS] R1: accepted 2 (crit/high 1 · med 1) · rejected 3 · dup 0 · verdict continue
[PROGRESS] R2: accepted 0 · rejected 1 · dup 2 · verdict PASS

GATE PASS (2 rounds)
  fixed   : 환불 멱등성 계약 추가 · 롤백 단계 순서 확정
  rejected: impl-micro 3건 (재시도 간격, endpoint 경로, 에러 문구) · 정책 변경 제안 1건
  restore : docs/payment-refund-plan.md.pre-gate-20260803T101500Z
```

## 왜 만들었나

AI 덕분에 계획서 쓰는 일은 쉬워졌습니다. 하지만 계획서를 *신뢰하는* 비용은 그대로입니다.
몇 분 만에 계획을 뽑아놓고, 감으로 착수하거나 리뷰 스레드에서 반나절을 태웁니다.
plan-preflight는 계획서를 코드 다루듯 CI에 태웁니다. 결과는 통과 아니면 실패,
이진 판정이 나오는 게이트입니다.

믿을 만한 게이트를 만드는 건 보기보다 어렵습니다. "Claude야, 내 계획서 루프
돌려서 리뷰해줘" 식의 순진한 접근은 두 가지 함정에 반드시 빠지는데, plan-preflight는
그 둘을 중심으로 설계됐습니다 (둘 다 실전 운영에서 몸으로 배운 것들입니다):

**1. 평가 기준이 미끄러집니다.** 유능한 리뷰어에게 *계획서*를 리뷰시키면
3라운드쯤엔 poll 간격, HTTP 상태 코드, 정확한 endpoint 경로를 요구하기
시작합니다. 계획서는 그런 것들을 정당하게 미뤄두는 문서인데도요 — 그래서
PASS는 영원히 "빠진 디테일 하나" 앞에서 좌절됩니다. plan-preflight는 모든 프롬프트에
평가 고도를 못박아 둡니다. **판정 대상은 계약·결정·스키마의 완성도뿐이고,
구현 마이크로 디테일은 결함으로 치지 않습니다.**

**2. 리뷰어는 빈손 보고를 싫어합니다.** "결함을 찾아라"라는 지시를 받은 콜드
리뷰어는 아무것도 없다고 돌아오느니 medium급 발견을 만들어냅니다. 라운드가
불어나죠. plan-preflight는 리뷰어에게 **발견 0건이 정상적인 결과**임을 명시하고,
라운드 연장은 **critical/high 심각도에만** 걸며, 각 라운드의 처리 이력을
첨부해 이미 처리된 발견의 재보고를 차단합니다.

## 무엇을 하나

| 요소 | 동작 |
|---|---|
| 판정 대상 | "이 계획서로 구현에 들어가도 되는가" — 그 이상도 이하도 아님 |
| 이중 검증 | Claude + 2차 리뷰어: codex가 있으면 codex, 없으면 적대 프레이밍의 두 번째 Claude 서브에이전트 (단독 리뷰는 `--fallback none`일 때만) |
| 정책 불변 | 확정된 결정은 시작 시 수집되고 절대 수정되지 않음 — 변경 제안은 보고만 |
| 자동 수정 범위 | critical/high 계약 수준 결함만: 멱등성·롤백·상태전이 계약 누락, 문서 간 모순, 코드와 안 맞는 인용, 미표기 미해결 항목. medium은 편집하지 않고 노트로만 남김 |
| 종료 조건 | 한 라운드에 critical/high 0건이면 PASS (medium만 있으면 편집 없이 즉시 pass-with-notes) · 라운드 상한 초과 시 미해결 목록과 함께 FAIL. 게이트가 적용한 수정은 항상 다음 라운드가 재검토함 |

## 절대 하지 않는 것

- 확정된 결정 변경 — 리뷰어가 아무리 주장해도
- 계획서 이외 파일 수정
- 커밋, 푸시, 배포
- 복원점(`<file>.pre-gate-<timestamp>`) 없이 수정

## 설치

```bash
git clone https://github.com/jw1222/plan-preflight
cp -r plan-preflight/skills/plan-preflight ~/.claude/skills/
```

설치는 이게 전부입니다. 마크다운 파일 하나, 의존성 없음, 빌드 없음.

**2차 리뷰어:** codex 목소리는 다음 세 가지가 모두 충족될 때만 활성화됩니다:

1. **openai-codex Claude Code 플러그인** 설치 (`codex:codex-rescue` 에이전트 제공)
2. **OpenAI Codex CLI** 설치
3. **로그인** 상태 (`codex login` 또는 환경변수 `OPENAI_API_KEY`)

하나라도 빠지면 — "플러그인은 깔았는데 로그인 안 함" 포함 — 에이전트 호출이
실패하고, 2차 리뷰어 자리는 적대 프레이밍을 붙인 두 번째 Claude 서브에이전트가
대신 맡습니다 (`[dual-claude]`, 호출 도중 실패면 `[codex-degraded]`도 함께).
듀얼 보이스는 유지되고 아무것도 깨지지 않습니다. 단독 리뷰를 원하면
`--fallback none`을 붙이십시오 (`[primary-only]`).

## 사용법

```bash
# 기본 — 계획서 하나를 게이트에
/plan-preflight docs/checkout-refactor-plan.md

# 짝 문서 (문서 간 정합성도 함께 검사)
/plan-preflight plans/migration-v2.md,plans/migration-brief.md

# 고위험 계획: 적대적 2차 리뷰
/plan-preflight docs/billing-plan.md --codex-mode adversarial

# 불변 정책 파일 명시, 라운드 확장
/plan-preflight plan.md --invariants decisions.md --base 3 --max 5
```

| 옵션 | 기본값 | 의미 |
|---|---|---|
| `--invariants <file>` | 자동 수집 | 확정 정책의 출처 |
| `--codex on\|off\|auto` | `auto` | 2차 리뷰어 사용 여부 |
| `--codex-mode rescue\|adversarial` | `rescue` | codex 리뷰 강도 |
| `--fallback claude\|none` | `claude` | codex를 못 쓸 때의 2차 리뷰어: 적대 프레이밍 Claude 서브에이전트 / 단독 리뷰 |
| `--base N` / `--max M` | 3 / 5 | 기본 라운드 수 / 확장 상한 |
| `--log <file>` | `<plan>.review.md` | 라운드 이력 위치 |

`.md`, `.html`, `.txt` — 리뷰어가 읽을 수 있는 계획서라면 무엇이든 동작합니다.

**출력 언어:** 기본은 영어입니다. 보고서와 로그를 한글로(또는 다른 언어로)
받고 싶다면, 호출할 때 그렇게 요청하면 됩니다:

```
/plan-preflight docs/plan.md — 답변은 한글로 해줘
```

리뷰어에게 가는 것은 전부 영어로 고정돼 있습니다 — 첫 라운드 프롬프트뿐
아니라 2라운드 이후 디스패치, 이전 라운드 처분 블록, 재촉 메시지까지
포함합니다. 프롬프트가 영어로 조율됐고, 한글 프롬프트를 주면 CLI 기반
리뷰어(Codex)가 제3의 언어로 추론하는 현상이 관찰됐기 때문입니다. 사용자에게
보여주는 보고서와 `--log` 파일만 요청한 언어를 따릅니다.

## 동작 방식

```
Step 0  대상 확정 · 불변 정책 수집 · 코드 인용 추출
        · 계획서별 리뷰 포커스 도출 · 프롬프트 3종 조립 (1회)
Step 1  2차 리뷰어 확인 (codex 있으면 codex : 없으면 적대 Claude 서브에이전트)
Step 2  라운드 루프 (라운드는 순차, 라운드 안의 두 목소리는 병렬)
          두 리뷰어 발사 → 발견 분류
          → 정책/impl-micro 거부 → 계약 결함 자동 수정
          → severity gate: crit/high 없으면 PASS : 다음 라운드
Step 3  PASS/FAIL 보고 · 적용한 수정 · 거부 목록 · 복원점 안내
```

전체 메커니즘은 [`skills/plan-preflight/SKILL.md`](skills/plan-preflight/SKILL.md)에
있습니다 — 그 파일이 스킬이자 곧 문서입니다.

## 실제 실행 결과 보기 (토큰 소모 없음)

`examples/` 디렉터리에 실제 게이트 실행 한 세트가 통째로 들어 있어, 직접
돌려보지 않고도 읽을 수 있습니다:

| 파일 | 내용 |
|---|---|
| [`sample-plan.md`](examples/sample-plan.md) | 계약 결함을 일부러 심어둔 환불 기능 계획서 (하단에 채점표 주석) |
| [`sample-plan.gated.md`](examples/sample-plan.gated.md) | 실제 3라운드 듀얼 보이스 실행 **이후**의 같은 계획서 — 추가된 내용 전부가 자동 적용된 계약 수정 (medium 노트 규칙 이전 실행이라 medium 항목도 적용돼 있음) |
| [`sample-plan.review.md`](examples/sample-plan.review.md) | 라운드별 로그: 발견·심각도·오케스트레이터의 심각도 재판정·최종 `GATE PASS [pass-with-notes]` |

이 실행의 하이라이트: 심은 결함 3종을 1라운드에서 두 리뷰어 모두 검출했고,
채점표에 없던 진짜 결함도 4건 더 찾아냈습니다. 잠긴 정책은 하나도 건드리지
않았고 impl-micro도 전혀 건드리지 않았습니다. 그리고 3라운드에서는 매 라운드
새 결함을 파내려가던 리뷰어를 severity gate가 정확히 끊어냈습니다 — 바로 이
실패 모드 때문에 이 스킬을 만들었습니다.

## FAQ

**codex가 꼭 필요한가요?** 아니요. 없으면 적대 프레이밍을 붙인 두 번째
Claude 서브에이전트가 2차 리뷰어를 맡아 듀얼 보이스가 유지됩니다
(`[dual-claude]`). codex는 모델 계열이 달라 더 독립적인 두 번째 표본을 주는
선호 옵션일 뿐입니다. codex를 기대했는데 `[dual-claude]`나 `[codex-degraded]`가
찍혀 있다면 대개 Codex CLI 미로그인이 원인입니다 — `codex login` 후 다시
시도하세요.

**아키텍처를 "개선"해주나요?** 의도적으로 하지 않습니다. 확정한 결정은
설계상 범위 밖입니다. 게이트는 *당신의* 계획을 닫아주는 것이지, 자기 취향으로
바꿔치기하지 않습니다.

**왜 poll 간격이나 endpoint 경로는 검사를 거부하나요?** 그것까지 명시한
문서는 계획서가 아니라 구현 그 자체이기 때문입니다. 이 고도 규율 덕분에
PASS에 도달할 수 있습니다.

**코드나 PR도 리뷰할 수 있나요?** 아니요. 그런 요청이 오면 스스로 거절합니다.
구현 이전의 계획·설계 문서만 대상입니다. 구현 후에는 코드 리뷰 도구를 쓰세요.

**이름으로 호출해야 하나요, 자동 발동을 믿어도 되나요?** 명시 호출
(`/plan-preflight <파일>`)이 확실한 경로이고 권장 습관입니다. 모델의 자동 발동도
동작하지만 상황에 따라 편차가 있습니다.

## 라이선스

MIT — [LICENSE](LICENSE) 참고.
