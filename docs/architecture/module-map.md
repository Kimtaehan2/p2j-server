# 모듈 구성

## 현재 존재하는 것

```
app/
├─ main.py                     앱 팩토리, 예외 핸들러 4종, X-Request-Id 미들웨어, CORS, /v1 라우터
├─ core/
│  ├─ config.py                Settings (.env, 운영에서 JWT_SECRET 기본값 거부)
│  ├─ errors.py                AppError · ERROR_CATALOG(35종) · Pydantic 오류 → 한국어
│  ├─ response.py              ok() · paged() · no_content() · encode/decode_cursor()
│  ├─ security.py              bcrypt · access JWT(30분) · refresh 원문/해시 생성
│  ├─ deps.py                  get_db · get_current_user (CurrentUser)
│  └─ time.py                  service_today() 04:00 KST · to_kst_iso() · week_range()
├─ db/
│  ├─ base.py                  Base · naming_convention · BigIntPK · TimestampMixin
│  ├─ session.py               async engine · sessionmaker (테스트에서 교체 가능)
│  ├─ redis.py                 redis.asyncio 클라이언트
│  └─ models/                  User · RefreshToken
├─ schemas/
│  └─ user.py                  user_to_dict() · public_user_to_dict()
├─ api/v1/
│  ├─ router.py
│  └─ endpoints/
│     ├─ health.py             GET /health (probe 는 Depends 로 교체 가능)
│     └─ auth.py               GET /auth/me 만
└─ services/
   └─ auth.py                  issue_session · rotate_refresh_token · revoke_*
```

## 앞으로 만들 것

**빈 폴더를 미리 만들지 않는다.** 실제 구현을 시작하는 PR 에서 그 파일만 만든다.
지금 껍데기를 만들어 두면 "있는데 동작하지 않는" 상태가 길어지고, 모바일이 구현 여부를 착각한다.

```
app/api/v1/endpoints/          app/services/              app/db/models/
├─ auth.py  (+signup/login/     ├─ auth.py (+가입·로그인 규칙)
│            refresh/logout)
├─ users.py                    ├─ users.py
├─ goals.py                    ├─ goals.py                ├─ goal.py
├─ todos.py                    ├─ todos.py                ├─ todo.py
├─ ai.py                       ├─ ai/                     ├─ ai_parse.py
│                              │  ├─ llm.py
│                              │  ├─ rules.py
│                              │  └─ pipeline.py
├─ declarations.py             ├─ declarations.py         ├─ declaration.py (+items)
├─ groups.py                   ├─ groups.py               ├─ group.py (+members, invites)
│                              ├─ feed.py                 ├─ feed_item.py (+reactions)
│                              ├─ storage.py (Firebase)   ├─ proof.py
├─ stats.py                    ├─ stats.py                ├─ user_daily_stats.py
└─ devices.py (P1)                                        └─ device.py (P1)

app/workers/daily.py           04:00 KST 배치 (stats 확정 · streak · 증거 만료)
```

모듈 이름은 `02-api-v1.md` 의 섹션 구분을 그대로 따른다.
모바일의 feature 폴더(`auth` / `todo` / `goal`)와도 이름이 맞아, 회의할 때 서로 헷갈리지 않는다.

## 구현할 때 지켜야 할 것

- **엔드포인트 = 세 줄.** 요청 스키마 검증 → `services.*` 호출 → `ok()` / `paged()` / `no_content()`.
- **목록 응답** — 서비스가 `(items, next_cursor)` 를 돌려주면 `paged(items, next_cursor)`.
  커서는 `encode_cursor({"id": ..., "at": ...})`. 클라이언트는 해석하지 않는다.
- **인증** — 새 엔드포인트는 `user: CurrentUser` 인자를 받는 것이 기본이다. 인증 없는 경로는
  `/auth/signup`, `/auth/login`, `/auth/refresh`, `/health` 네 개뿐.
- **직렬화** — 응답 dict 를 만드는 함수를 `app/schemas/<도메인>.py` 에 둔다 (`user_to_dict` 처럼).
  ORM 객체를 그대로 반환하지 않는다. `response_model` 을 쓰지 않는다.
- **날짜** — `YYYY-MM-DD`, 시각은 `to_kst_iso()`. 오늘은 `service_today()`.
- **204** — `no_content()`. 감싸지 않는다. 모바일 `uncomplete` 가 본문 없음을 전제한다.
- **오류** — `AppError(code)` 또는 `errors.py` 의 이름 있는 클래스. 소유권 위반은 404 (존재를 숨김), 그룹 권한은 403.
- **N+1** — 목록 + 조인은 `selectinload` 또는 명시적 join. 5주차 전에 "TODO 목록 + 목표 제목" 쿼리를 한 번 끝까지 짜 본다.
