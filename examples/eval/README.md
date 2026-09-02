# 평가 세트 (회귀 검사)

스킬의 동작은 모델 버전에 따라 미끄러집니다. 이 디렉터리는 결함을 일부러 심은
계획서 6종과 기대 결과를 두고, 모델이나 스킬 본문이 바뀔 때마다 게이트가 여전히
같은 판정을 내리는지 확인하기 위한 것입니다.

## 구성

```
examples/eval/
├── run.py            준비(prepare) · 판정(check) · 목록(list)
├── cases/<case>/     게이트가 보는 것 전부 — 계획서, 동반 문서, 인용된 코드
├── keys/<case>.json  정답 키 — 실행 디렉터리에 복사되지 않으므로 리뷰어가 볼 수 없음
└── .runs/            실행 디렉터리 (git 제외)
```

기존 예시(`examples/sample-plan.md`)는 계획서 하단에 채점표가 달려 있어 리뷰어에게
답이 노출됩니다. 이 세트는 키를 분리해 그 문제를 피합니다.

## 실행 방법

```bash
# 1. 실행 디렉터리 준비 (케이스를 고르지 않으면 전부)
python3 examples/eval/run.py prepare
python3 examples/eval/run.py prepare 02-contract-gaps 04-medium-only

# 2. 출력된 호출 문구를 Claude Code에서 그대로 실행
/plan-preflight examples/eval/.runs/<stamp>/02-contract-gaps/plan.md --codex off

# 3. 판정
python3 examples/eval/run.py check examples/eval/.runs/<stamp>
```

`prepare`는 케이스 파일을 새 실행 디렉터리로 복사하고 파일별 해시를 남깁니다.
`check`는 그 해시와 게이트가 남긴 `*.review.md` 로그, 수정된 계획서를 키와
대조합니다. 하나라도 실패하면 종료 코드가 1입니다.

## 케이스

| 케이스 | 검사하는 것 | 기대 |
|---|---|---|
| `01-clean-pass` | 고도 유지(Trap 1)와 빈손 보고(Trap 2). impl-micro를 명시적으로 미룬 완결된 계획서 | PASS · 1라운드 · 편집 없음 |
| `02-contract-gaps` | 실제 critical/high 계약 결함 4건(멱등성 부재, 미정의 상태, enum 누락, 미표기 모순)의 검출과 수렴 | PASS · 3라운드 이내 · 4건 모두 로그에 등장 · 편집 있음 · Decisions 절 불변 |
| `03-locked-policy` | 확정 정책 보존. 재론을 유도하는 결정(소프트 삭제 없음, 즉시 삭제 없음)과 실제 결함 2건(취소 전이 누락, 확정 결정과 모순) | PASS · 3라운드 이내 · `## Decisions (locked)` 절 바이트 동일 · 2건 검출 |
| `04-medium-only` | medium 노트 규칙과 심각도 보정. 계약 수준은 완결, 흠은 medium뿐 | PASS · 1라운드 · 편집 없음 (`[pass-with-notes]`든 발견 0건이든 모두 정답) |
| `05-code-citation` | 코드 인용 검증. 반올림 방식과 상한값 두 곳이 코드와 다르고, 한 곳은 맞음 | PASS · 3라운드 이내 · 2건 검출 · 계획서는 코드 쪽으로 수정 · 코드 파일 불변 |
| `06-companion-contradiction` | 동반 문서 일관성과 수정 방향. `brief.md`(확정)와 `plan.md`가 두 곳에서 모순 | PASS · 3라운드 이내 · 2건 검출 · `brief.md` 불변 |

각 키 파일의 `seeded_defects`에 심어 둔 결함의 설명이 있습니다.

## 판정 항목

| 항목 | 방법 |
|---|---|
| verdict | 로그의 마지막 `GATE PASS` / `GATE FAIL` |
| rounds | 로그의 `## R<n>` 제목(없으면 `[PROGRESS] R<n>`)의 최댓값 ≤ `max_rounds` |
| plan unchanged / edited | 준비 시점 해시와 비교 |
| unchanged files | 동반 문서와 코드 파일의 해시 비교 |
| unchanged sections | 지정한 제목의 절 본문을 원본과 문자열 비교 |
| must_catch | 결함마다 키워드 후보 중 하나 이상이 로그에 등장 |
| required_tags | 지정한 태그가 로그에 등장 |

`info` 줄에는 로그에서 찾은 태그와 복원 지점 개수를 함께 보여 줍니다.

## 주의

- 리뷰는 비결정적입니다. 판단은 한 번의 실패가 아니라 세 번 반복해서 같은
  케이스가 두 번 이상 실패할 때 내리십시오.
- `--codex off`가 기본 권장입니다. codex 목소리가 없으면 적대 프레이밍 Claude
  서브에이전트가 2차 리뷰어를 맡으므로 듀얼 보이스는 유지되고, 비용과 외부
  의존이 줄어듭니다. codex까지 검사하려면 같은 실행 디렉터리를 다시 준비해
  옵션 없이 돌리십시오.
- 실행 디렉터리는 매번 새로 만드십시오. 게이트가 계획서를 제자리에서 수정하고
  복원 지점을 남기기 때문에, 같은 디렉터리를 두 번 쓰면 판정이 오염됩니다.
- 로그 위치를 `--log`로 바꾸면 판정기가 찾지 못합니다. 기본 위치를 쓰십시오.

## 케이스 추가

1. `cases/<id>/`에 게이트가 볼 파일만 넣습니다. 계획서 안에 답을 적지 않습니다.
2. `keys/<id>.json`에 `plan`, `companions`, `seeded_defects`, `expect`를 적습니다.
   `must_catch`의 키워드는 리뷰어가 어떤 말로 지적하든 하나는 걸리도록 여러
   표현을 넣되, 다른 문맥에서도 흔히 나오는 짧은 단어는 피합니다.
3. `python3 examples/eval/run.py list`로 키가 읽히는지 확인합니다.
