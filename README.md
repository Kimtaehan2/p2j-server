# p2j-server

**P2J** — P들을 위한 TODO List 공유 앱의 백엔드.

말로 아무렇게나 뱉은 목표를 AI 가 할 일로 쪼개 주고, 그룹에 선언한 뒤 인증샷으로 확인하는 서비스다.
모바일 앱은 별도 저장소 [`p2j-mobile`](https://github.com/Kimtaehan2/p2j-mobile) 에 있다.

| 담당 | 이름 |
| --- | --- |
| 백엔드 | 김태한 |
| DB · AI | 박영준 |
| 프론트엔드 | 김지호 (`p2j-mobile`) |

---

## 현재 상태

**기반 골격까지만 구현되어 있다.** 회원가입, 할 일, 목표, AI, 그룹 기능은 아직 없다.

동작하는 것:

- NestJS 앱 (PORT 8000, 전역 prefix `v1`)
- 환경변수 검증
- Prisma 연결 (PostgreSQL, driver adapter)
- Redis 연결
- `GET /v1/health` — PostgreSQL `SELECT 1` 과 Redis `PING` 을 **실제로** 확인
- 공통 응답 래퍼 `{ data }` / 공통 오류 필터 `{ error: { code, message, details } }`
- Swagger UI `/v1/docs`, OpenAPI JSON `/v1/docs-json`
- 04:00 KST 하루 경계 유틸과 단위 테스트

앞으로 만들 모듈 목록은 [`docs/architecture/module-map.md`](docs/architecture/module-map.md) 에 있다.

---

## 1. 사전 준비

### 1-1. Node.js 24

이 저장소는 **Node 24 LTS** 를 쓴다. `.nvmrc` 에 적혀 있다.

```bash
node -v
# v24.x.x 가 나와야 한다
```

없다면 [nodejs.org](https://nodejs.org/) 에서 24 LTS 를 받거나, 버전 관리자를 쓴다.

```bash
# nvm (macOS / Linux)
nvm install
nvm use

# fnm (Windows / macOS / Linux)
fnm use --install-if-missing
```

> Node 22 이하에서는 `prisma.config.ts` 가 쓰는 `process.loadEnvFile()` 이 없어서 실패한다.

### 1-2. Docker Desktop

PostgreSQL 과 Redis 를 컨테이너로 띄운다. 팀원 사이의 버전 차이를 없애기 위해서다.

- [Docker Desktop 다운로드](https://www.docker.com/products/docker-desktop/)
- 설치 후 **Docker Desktop 을 실행해 둔 상태**여야 한다. 아이콘이 초록색인지 확인한다.

```bash
docker --version
docker compose version
```

> Docker 없이도 서버는 뜨지만 `/v1/health` 가 503 을 돌려준다. 정상이다.
> DB 가 없다는 사실을 숨기지 않고 그대로 알려 주는 것이 이 엔드포인트의 목적이다.

### 1-3. Git

```bash
git --version
```

---

## 2. 설치부터 실행까지

### 2-1. 저장소 받기

```bash
git clone https://github.com/Kimtaehan2/p2j-server.git
cd p2j-server
```

### 2-2. 의존성 설치

```bash
npm ci
```

`npm install` 이 아니라 **`npm ci`** 를 쓴다. `package-lock.json` 에 적힌 버전 그대로 설치해서
팀원 사이에 버전이 갈리지 않게 한다.

설치 중 아래 경고가 뜨는데 **무시해도 된다.**

```
npm warn allow-scripts  3 packages have install scripts not yet covered by allowScripts
```

npm 11 이 의존성의 install 스크립트를 기본 차단하는 것이다.
Prisma 의 schema engine 은 패키지에 동봉되어 있어 스크립트 없이도 동작한다. 확인 방법:

```bash
npx prisma --version
# Schema Engine ... 줄이 보이면 정상
```

### 2-3. 환경변수 파일 만들기

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

기본값만으로 서버가 뜬다. **실제 API 키는 지금 넣지 않는다.**
JWT · Firebase · Clova · OpenAI 값은 해당 기능을 만들 때 채운다.

> `.env` 는 `.gitignore` 에 있다. **절대 커밋하지 않는다.**
> 실키는 팀 Notion 비공개 페이지나 Discord DM 으로 공유한다.

### 2-4. PostgreSQL · Redis 띄우기

```bash
docker compose up -d
```

확인:

```bash
docker compose ps
# postgres, redis 둘 다 (healthy) 여야 한다
```

- PostgreSQL 16 — `localhost:5432`, DB `p2j`, 계정 `postgres` / `devpass`
- Redis 7 — `localhost:6379`

### 2-5. Prisma Client 생성

```bash
npm run prisma:generate
```

`src/generated/prisma/` 에 클라이언트가 만들어진다. 이 폴더는 커밋하지 않는다.
`schema.prisma` 를 고칠 때마다 다시 실행한다.

> 아직 마이그레이션이 없다. DB 는 비어 있는 것이 정상이다.

### 2-6. 서버 실행

```bash
npm run start:dev
```

```
[Bootstrap] P2J 서버 시작 — http://localhost:8000/v1 (문서: /v1/docs)
```

### 2-7. 동작 확인

```bash
curl http://localhost:8000/v1/health
```

```json
{ "data": { "status": "ok", "postgres": "up", "redis": "up" } }
```

브라우저에서 열 것:

- API 문서 — <http://localhost:8000/v1/docs>
- OpenAPI JSON — <http://localhost:8000/v1/docs-json>

### 2-8. 정리

```bash
docker compose down
```

**`-v` 를 붙이지 않는다.** named volume 이 지워져 개발 데이터가 날아간다.

---

## 3. 모바일 앱과 연결하기

`p2j-mobile` 은 기본으로 `http://10.0.2.2:8000/v1` 을 본다.
`10.0.2.2` 는 Android 에뮬레이터에서 **호스트 PC 를 가리키는 주소**다.

```bash
# p2j-mobile 저장소에서
flutter run --dart-define=USE_MOCK=false
```

실기기에서 테스트하려면 PC 의 LAN IP 를 넣는다.

```bash
flutter run --dart-define=USE_MOCK=false --dart-define=API_BASE_URL=http://192.168.0.10:8000/v1
```

Flutter web(`flutter run -d chrome`)으로 볼 때는 CORS 가 필요하다.
개발 환경(`NODE_ENV != production`)에서는 이미 열려 있다.

---

## 4. 자주 쓰는 명령

| 명령 | 설명 |
| --- | --- |
| `npm run start:dev` | 개발 서버 (파일 변경 시 재시작) |
| `npm run build` | 빌드 (`dist/`) |
| `npm run start:prod` | 빌드 결과 실행 |
| `npm test` | 단위 테스트 (vitest) |
| `npm run test:e2e` | e2e 테스트 — **PostgreSQL·Redis 가 떠 있어야 한다** |
| `npm run lint` | 린트 (oxlint) |
| `npm run format` | 포맷 적용 (prettier) |
| `npm run format:check` | 포맷 검사 — CI 와 동일 |
| `npm run prisma:format` | `schema.prisma` 정렬 |
| `npm run prisma:validate` | 스키마 검증 |
| `npm run prisma:generate` | Prisma Client 생성 |

---

## 5. API 규약

### 성공

```json
{ "data": { } }
```

**204 No Content 는 감싸지 않는다.** 본문이 아예 없다.
모바일의 `uncomplete` 가 본문 없음을 전제로 요약을 다시 계산하기 때문이다.

### 실패

```json
{
  "error": {
    "code": "DECLARED_TODO_LOCKED",
    "message": "그룹에 선언한 할 일은 오늘 수정할 수 없습니다.",
    "details": { "todo_id": 42 }
  }
}
```

오류 코드 목록은 [`docs/specs/02-api-v1.md`](docs/specs/02-api-v1.md) 7절에 있다.
새 코드를 만들면 그 표에 추가하고 모바일 담당에게 알린다.

### 날짜

- 날짜는 `YYYY-MM-DD` 문자열, 시각은 `+09:00` 오프셋을 포함한 ISO 8601.
- **하루는 04:00 KST 에 바뀐다.** 새벽 3시에 끝낸 할 일은 "어제"의 성과다.
- 서버에서 오늘을 구할 때는 항상 `src/common/utils/service-day.ts` 를 쓴다.
  `new Date()` 로 오늘을 만들면 UTC 로 뜨는 Railway 컨테이너에서 날짜가 어긋난다.
- 클라이언트는 오늘 날짜를 직접 계산하지 않고 `GET /auth/me` 의 `today` 를 그대로 믿는다.

---

## 6. 폴더 구조

```
p2j-server/
├─ prisma/
│  └─ schema.prisma            datasource + generator (모델은 아직 없음)
├─ prisma.config.ts            Prisma 7 설정 원본
├─ src/
│  ├─ main.ts                  전역 설정 · Swagger · 부트스트랩
│  ├─ app.module.ts
│  ├─ config/env.validation.ts
│  ├─ common/
│  │  ├─ exceptions/           AppException
│  │  ├─ filters/              AllExceptionsFilter
│  │  ├─ interceptors/         ResponseInterceptor
│  │  └─ utils/                service-day
│  ├─ infra/
│  │  ├─ prisma/               PrismaService
│  │  └─ redis/                RedisService
│  ├─ modules/
│  │  └─ health/
│  └─ generated/               Prisma Client (커밋하지 않음)
├─ test/                       e2e
├─ docs/                       명세 원문 · 결정 기록 · 담당 영역
├─ experiments/ai/             AI 프롬프트 실험
└─ docker-compose.yml          PostgreSQL 16 + Redis 7
```

---

## 7. 문서

| 문서 | 내용 |
| --- | --- |
| [`docs/specs/`](docs/specs/) | 명세 원문 4건과 충돌 해결 규칙 |
| [`docs/architecture/module-map.md`](docs/architecture/module-map.md) | 지금 있는 모듈과 앞으로 만들 모듈 |
| [`docs/database/migration-policy.md`](docs/database/migration-policy.md) | 마이그레이션 규칙 (Prisma Migrate 만 사용) |
| [`docs/ai/README.md`](docs/ai/README.md) | AI 3단계 폴백과 운영 규칙 |
| [`docs/decisions/`](docs/decisions/) | 저장소 분리 · 런타임 버전 · **미결 사항** |
| [`docs/OWNERSHIP.md`](docs/OWNERSHIP.md) | 담당 영역과 공동 리뷰 대상 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 브랜치 · 커밋 · PR 규칙 |

**작업을 시작하기 전에 [`docs/decisions/pending-decisions.md`](docs/decisions/pending-decisions.md) 를 먼저 읽는다.**
아직 정하지 않은 항목을 임의로 구현하면 나중에 쌓인 데이터를 손봐야 한다.

---

## 8. 문제가 생기면

### `npm run start:dev` 가 환경변수 오류로 멈춘다

```
환경변수 검증에 실패했습니다. .env.example 을 참고해 값을 채우세요.
- DATABASE_URL: DATABASE_URL 이 비어 있습니다.
```

`.env` 파일이 없거나 키가 비어 있다. 2-3 단계를 다시 한다.

### `/v1/health` 가 503 을 준다

```json
{ "error": { "code": "HEALTH_CHECK_FAILED", "details": { "postgres": "down", "redis": "down" } } }
```

컨테이너가 떠 있지 않다.

```bash
docker compose ps
docker compose up -d
```

Docker Desktop 자체가 꺼져 있는 경우가 가장 많다.

### 포트 8000 또는 5432 가 이미 사용 중이다

```bash
# Windows
netstat -ano | findstr :8000

# macOS / Linux
lsof -i :8000
```

`.env` 의 `PORT` 를 바꾸거나 점유 중인 프로세스를 정리한다.
`PORT` 를 바꾸면 모바일의 `API_BASE_URL` 도 함께 바꿔야 한다.

### `PrismaClient` 를 찾을 수 없다고 나온다

```bash
npm run prisma:generate
```

`src/generated/` 는 커밋하지 않으므로, clone 직후에는 반드시 한 번 실행해야 한다.

### `prisma validate` 가 `P1012` 로 실패한다

Prisma 7 부터 `datasource` 블록에 `url` 을 쓸 수 없다.
접속 URL 은 `prisma.config.ts` 와 `PrismaService` 의 driver adapter 에서 지정한다.
자세한 내용은 [`docs/decisions/0002-runtime-versions.md`](docs/decisions/0002-runtime-versions.md).
