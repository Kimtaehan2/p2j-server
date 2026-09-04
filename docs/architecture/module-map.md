# 모듈 구성

## 현재 존재하는 것

```
src/
├─ main.ts                     PORT 8000, prefix v1, 전역 파이프·인터셉터·필터, Swagger
├─ app.module.ts
├─ config/
│  └─ env.validation.ts        기반 실행에 필요한 환경변수만 검증
├─ common/
│  ├─ exceptions/app.exception.ts        코드 기반 예외
│  ├─ filters/all-exceptions.filter.ts   { error: { code, message, details } }
│  ├─ interceptors/response.interceptor.ts  { data: ... }
│  └─ utils/service-day.ts     04:00 KST 하루 경계
├─ infra/
│  ├─ prisma/                  PrismaService (driver adapter)
│  └─ redis/                   RedisService (ioredis 단일 클라이언트)
└─ modules/
   └─ health/                  GET /v1/health
```

## 앞으로 만들 것

**빈 폴더를 미리 만들지 않는다.** 실제 구현을 시작하는 PR 에서 그 모듈만 만든다.
지금 껍데기를 만들어 두면 "있는데 동작하지 않는" 상태가 길어지고, 모바일이 구현 여부를 착각한다.

```
src/modules/
├─ auth            signup, login, refresh(회전), logout, me
├─ users
├─ goals
├─ todos
├─ ai              parse, load-check
├─ stats
├─ groups          group, member, invite
├─ declarations
├─ proofs          proof, comment, reaction
├─ uploads         Firebase signed URL
└─ batch           스케줄 잡 (@nestjs/schedule)

src/integrations/
├─ clova           STT
└─ llm             GPT-4o-mini

src/infra/
└─ storage         FirebaseStorageService
```

모듈 이름은 `02-api-v1.md` 의 섹션 구분을 그대로 따른다.
모바일의 feature 폴더(`auth` / `todo` / `goal`)와도 이름이 맞아, 회의할 때 서로 헷갈리지 않는다.

## 구현할 때 지켜야 할 것

아래는 이번 scaffold 범위 밖이지만, 해당 기능을 만들 때 반드시 반영한다.

- **목록 응답** — 서비스가 `{ items, nextCursor }` 를 반환하면
  `{ data: [...], page: { next_cursor, has_next } }` 형태로 내려간다.
  커서 인코딩 유틸(`common/utils/cursor.ts`)과 함께 `ResponseInterceptor` 를 확장한다.
  지금은 목록 엔드포인트가 없어 `{ data }` 래핑만 구현되어 있다.
- **인증** — `JwtAuthGuard` 를 `APP_GUARD` 로 전역 등록하고 `@Public()` 이 붙은 라우트만 통과시킨다.
  기본이 "인증 필요"여야 한다. 반대로 하면 새 컨트롤러에서 가드를 빠뜨려 인증 없이 열린다.
  Public 은 `/auth/signup`, `/auth/login`, `/auth/refresh`, `/health` 뿐이다.
- **직렬화** — 모바일은 snake_case 키를 기대한다(`achievement_rate`, `is_declared`).
  Prisma 모델은 camelCase 이므로 **응답 DTO 에서 명시적으로 변환**한다.
  전역 자동 변환 인터셉터는 쓰지 않는다. `parse_id` 같은 값이 의도치 않게 바뀌면 추적이 어렵다.
- **날짜** — `YYYY-MM-DD` 문자열, 시각은 `+09:00` 오프셋을 포함한 ISO 8601.
  오늘 날짜는 항상 `common/utils/service-day.ts` 로 구한다. `new Date()` 로 오늘을 만들지 않는다.
- **204** — `ResponseInterceptor` 는 204 를 감싸지 않는다.
  모바일 `uncomplete` 가 본문 없음을 전제로 summary 를 다시 계산한다.
