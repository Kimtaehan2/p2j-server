# 기여 방법

## 브랜치 전략 — GitHub Flow

3인 팀에 Git Flow 는 과하다. 규칙은 다섯 줄이면 끝난다.

- `main` 은 **항상 실행 가능한 상태**를 유지한다.
- `main` 에 직접 push 하지 않는다.
- 작업은 짧은 브랜치에서 한다. 하루이틀 안에 머지될 크기로 자른다.
- PR 은 **최소 1명 리뷰** 후 CI 가 통과하면 **squash merge** 한다.
- 머지한 브랜치는 지운다.

장기 `develop` 브랜치는 쓰지 않는다. 3인 팀에서는 통합이 늦어지기만 한다.
중간발표·최종발표 시점의 상태는 **Git tag** 로 남긴다.

### 브랜치 이름

```
feat/server-auth
feat/server-goals
feat/data-models
feat/ai-parse
fix/server-refresh-rotation
docs/api-v1
chore/ci
```

`<타입>/<영역>-<대상>` 형태다. 영역은 `server` / `data` / `ai` 중 하나를 쓰면
누가 리뷰해야 하는지 바로 보인다.

### 커밋 메시지

Conventional Commits 를 쓴다.

```
chore: bootstrap fastapi server
feat(auth): add refresh token rotation
feat(ai): add structured goal parser
chore(db): add goal constraints
fix(todos): keep complete allowed on declared todo
docs(api): update error code table
```

## PR 을 올리기 전에

```bash
uv run ruff format .
uv run ruff check .
uv run mypy app
uv run pytest
```

CI 에서 도는 것과 같다. 로컬에서 먼저 돌리면 리뷰가 빨라진다.

## API 계약을 바꿀 때

계약이 바뀌면 두 저장소가 함께 움직인다. 순서를 지킨다.

```
1. API 계약 변경          docs/specs/02-api-v1.md 갱신 + 김지호 리뷰
2. 호환 가능한 서버 구현   기존 계약을 깨지 않는 형태로 먼저 추가
3. 연결된 p2j-mobile PR    서로 링크한다
4. 모바일 전환
5. 필요하면 이전 계약 제거
```

**2번을 건너뛰고 바로 바꾸면 모바일이 그 순간 깨진다.**
서버가 먼저 배포되고 앱은 나중에 업데이트되기 때문이다.

## DB 를 바꿀 때

`docs/database/migration-policy.md` 를 따른다. 요약하면:

- `uv run alembic revision --autogenerate -m "..."` 로 파일을 만들고 **눈으로 검토**한다.
- autogenerate 가 놓치는 CHECK · partial index 는 마이그레이션 파일에 직접 넣는다.
- 이미 머지·적용된 마이그레이션은 고치지도 지우지도 않는다.
- `app/db/models/**`, `alembic/versions/**` 변경은 김태한 · 박영준 두 명의 리뷰를 받는다.

## 코드 규칙

- **주석과 사용자 노출 문구는 한국어**, 변수·함수·파일 이름은 영어.
  단, `alembic.ini` 는 OS 로캘로 읽히므로 **영어만** 쓴다 (한국어 Windows 에서 cp949 오류).
- **엔드포인트 파일에 로직을 쓰지 않는다.** 검증 → 서비스 호출 → `ok()` 래핑. 로직은 `app/services/`.
- 오류는 `AppError` 로만 던진다. 코드는 `ERROR_CATALOG` 에 먼저 등록한다. `fastapi.HTTPException` 을 쓰지 않는다.
- 오늘 날짜는 `app/core/time.py` 의 `service_today()` 로만 구한다. `datetime.now().date()` 로 "오늘"을 만들지 않는다.
- 시각 직렬화는 `to_kst_iso()`. 응답에 naive datetime 을 그대로 넣지 않는다.
- 비밀번호, 토큰, AI 입력 원문, 접속 URL 은 **로그에 남기지 않는다.**
- `.env` 를 커밋하지 않는다. 새 환경변수를 추가하면 `Settings` 와 `.env.example` 양쪽에 넣는다.
- 빈 모듈을 미리 만들지 않는다. 구현을 시작할 때 그 모듈을 만든다.
- 의존성을 추가하면 `uv.lock` 을 함께 커밋한다.

## 리뷰에서 볼 것

- 응답이 `{ data }` 형식인가. 204 를 감싸고 있지는 않은가.
- 오류가 `AppError` 로 나가는가. 코드가 `02-api-v1.md` §1.4 표와 `ERROR_CATALOG` 에 있는가. `message` 가 한국어인가.
- 새 엔드포인트에 `CurrentUser` 가 걸려 있는가 (인증 없는 경로는 4개뿐).
- 날짜 계산이 `service_today()` 를 쓰는가.
- 목록 조회에 N+1 이 없는가 (`selectinload` / join).
- 마이그레이션 파일을 사람이 읽었는가. 인덱스·CHECK 가 빠지지 않았는가.
