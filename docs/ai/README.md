# AI 파이프라인

담당: 박영준. 상세 사양은 `docs/specs/04-backend-v1.md` 5.4 절.

**이번 scaffold 에는 AI 코드가 없다.** 실제 연동은 8주차부터 시작한다.
여기에는 구현 전에 합의된 내용만 적어 둔다.

## 구성

| 역할 | 대상 |
| --- | --- |
| STT | 네이버 클로바 스피치 |
| 구조화 | GPT-4o-mini + JSON Schema (strict) |
| 저장 | `ai_parses` 테이블 (성공·실패 모두 기록) |

## 3단계 폴백

신청서에 명시한 사항이다. 반드시 이 순서를 지킨다.

```
1단계  GPT-4o-mini + JSON Schema(strict) 호출
         성공 → status: "ok"
2단계  스키마 위반 또는 파싱 실패 → 1회 재시도
         실패 → 규칙 기반 파서(정규식)
         부분 추출 성공 → status: "partial", uncertain_fields 명시
3단계  규칙 파서도 실패 → status: "fallback"
         제목만 채운 draft 1건 + 사용자 직접 입력 유도
```

규칙 파서가 잡아야 할 한국어 패턴:

- 빈도: `주 3회`, `일주일에 세 번`, `매일`, `주말마다`
- 기간: `한 달`, `4주`, `2주간`, `이번 학기`
- 소요: `한 시간`, `30분`, `1시간 반`

한글 수사(`세 번`, `한 달`)를 숫자로 바꾸는 매핑 테이블이 필요하다.
LLM 이 죽었을 때 이것이 유일한 방어선이다.

## 운영 규칙

- **타임아웃 8초**, 실패 시 `503 AI_UNAVAILABLE`. 모바일이 수동 입력 화면으로 전환한다.
- **레이트 리밋** — Redis `INCR ratelimit:ai:{userId}:{serviceDay}` + 하루 만료.
  초과 시 `429 AI_RATE_LIMITED`. 기본 30회(`AI_PARSE_DAILY_LIMIT`).
- **모든 호출을 `ai_parses` 에 기록한다.** 실패한 호출도 남긴다.
  `status` 분포와 `accepted` 비율이 최종보고서의 정확도 근거가 된다.
- **`raw_text` 는 로그에 남기지 않는다.** 사용자의 음성 발화 원문이다.

## 실험

프롬프트 실험과 정확도 비교는 `experiments/ai/` 에서 한다.
운영 코드로 들어갈 프롬프트는 `src/integrations/llm/` 로 옮긴 뒤 리뷰를 받는다.
