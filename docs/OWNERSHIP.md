# 담당 영역과 협업 규칙

## 담당

### 김지호 — 프론트엔드

- `p2j-mobile` 저장소 전체
- 모바일 DTO 와 Mock 데이터
- API 계약 변경 검토 (서버가 계약을 바꾸면 반드시 리뷰에 참여)

### 김태한 — 백엔드

- NestJS 공통 구조 (필터 · 인터셉터 · 가드 · 파이프)
- 일반 API (`auth`, `goals`, `todos`, `stats`, `groups`, `declarations`, `proofs`)
- Redis, Firebase Storage, Railway 배포
- DB 운영과 마이그레이션 적용

### 박영준 — DB & AI

- ERD 와 Prisma 모델 설계
- AI `parse`, `load-check`, 3단계 폴백
- 클로바 STT · LLM 연동
- 집계 쿼리와 데이터 검증

## 공동 리뷰가 필요한 경로

아래는 **혼자 머지하지 않는다.** 두 담당자의 승인을 받는다.

| 경로 | 리뷰어 |
| --- | --- |
| `prisma/schema.prisma` | 김태한 + 박영준 |
| `prisma/migrations/**` | 김태한 + 박영준 |
| `prisma/seed.ts` | 김태한 + 박영준 |
| `src/modules/ai/**` | 김태한 + 박영준 |
| `src/integrations/**` | 김태한 + 박영준 |
| API 요청·응답 형식 변경 | 김태한 + 김지호 |
| 서버 seed 와 모바일 Mock 의 일치 | 김태한 + 김지호 |

**이유**: 스키마와 마이그레이션은 되돌리기 어렵다. API 형식은 두 저장소가 동시에 깨진다.
`seed.ts` 는 모바일 Mock fixture 와 같은 데이터를 만들어야 실서버 전환 시 화면이 그대로 보인다.

## CODEOWNERS

실제 GitHub ID 를 아직 모르므로 활성 `CODEOWNERS` 를 만들지 않았다.
`.github/CODEOWNERS.example` 에 placeholder 가 있다.

세 사람의 GitHub ID 를 확인하면 placeholder 를 바꿔 `.github/CODEOWNERS` 로 옮긴다.
잘못된 ID 가 들어간 CODEOWNERS 는 리뷰어 자동 지정을 조용히 실패시킨다.

## 저장소가 걸쳐 있을 때

계약이 바뀌면 두 저장소가 함께 움직인다.

```
API 계약 변경 → 호환 가능한 서버 구현 → 연결된 p2j-mobile PR → 모바일 전환 → 필요하면 이전 계약 제거
```

**모바일 PR 과 서버 PR 은 서로 링크한다.** PR 본문에 상대 저장소 PR 주소를 적는다.
