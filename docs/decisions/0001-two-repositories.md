# 0001. 저장소를 둘로 나눈다

- 상태: 확정
- 결정일: 2026-09-04
- 관련: `docs/specs/01-development-plan.md` 2절

## 결정

P2J 는 모노레포를 쓰지 않는다. 저장소를 두 개로 나눈다.

| 저장소 | 내용 | 담당 |
| --- | --- | --- |
| `p2j-mobile` | Flutter 앱 | 김지호 |
| `p2j-server` | NestJS · Prisma · PostgreSQL · Redis · DB · AI | 김태한(서버) · 박영준(DB·AI) |

**DB 와 운영 AI 코드는 모두 `p2j-server` 안에 둔다.**
`p2j-db`, `p2j-ai` 같은 저장소를 따로 만들지 않는다.

## 이유

- **빌드·배포 파이프라인이 완전히 다르다.** Flutter 는 Gradle·APK, 서버는 Node·Docker·Railway 다.
  한 저장소에 두면 모바일 PR 마다 서버 CI 가 돌고 그 반대도 마찬가지다.
- **3인 팀에서 충돌 관리가 쉽다.** FE 와 BE 가 API 계약만 지키면 서로의 내부 구현을 볼 일이 없다.
- **AI 코드를 따로 떼면 배포 대상이 하나 더 늘어난다.** 학기 프로젝트에서 감당할 이유가 없다.
  AI 는 서버 안의 모듈(`src/modules/ai`, `src/integrations/`)로 둔다.

## API 계약의 원본

**`p2j-server` 가 관리한다.** `docs/specs/02-api-v1.md` 와 서버가 생성하는
OpenAPI 문서(`/v1/docs-json`)가 기준이다.

계약을 바꿀 때는 이 순서를 지킨다.

```
API 계약 변경 → 호환 가능한 서버 구현 → 연결된 p2j-mobile PR → 모바일 전환 → 필요하면 이전 계약 제거
```

**모바일 PR 과 서버 PR 은 서로 링크한다.** 어느 쪽이 먼저 머지되어도
상대 저장소에서 무엇을 해야 하는지 보이게 한다.

## 하지 않기로 한 것

- `p2j-mobile` 안에 `server`, `backend`, `apps/server` 를 만들지 않는다.
- `p2j-mobile` 을 `apps/mobile` 로 옮기지 않는다.
- GitHub Organization 을 새로 만들지 않는다.
