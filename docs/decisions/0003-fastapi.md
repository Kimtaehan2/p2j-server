# 0003. 백엔드를 FastAPI 로 전환한다

- 상태: 확정
- 결정일: 2026-09-05
- 대체: `0002-runtime-versions.md` (Node 24 · NestJS 12 · Prisma 7 — 더 이상 유효하지 않음)
- 관련: `docs/specs/02-api-v1.md` §14, `docs/specs/01-development-plan.md` v2

## 결정

`p2j-server` 는 **Python 3.12 + FastAPI** 로 만든다. 2026-09-04 에 만든 NestJS 스캐폴드는 제거했다
(커밋 `2c8014b` 에 남아 있다).

| 영역 | 기존 | 변경 |
| --- | --- | --- |
| 런타임 | Node 24 + NestJS 12 | **Python 3.12 + FastAPI** |
| ORM · 마이그레이션 | Prisma 7 | **SQLAlchemy 2.0 (async) + Alembic** |
| 검증 | class-validator DTO | **Pydantic v2** |
| 패키지 관리 | npm + package-lock | **uv + uv.lock** |
| 서버 실행 | `nest start` | **uvicorn** (Railway 도 uvicorn `--workers 2`) |
| 테스트 | vitest | **pytest + pytest-asyncio + httpx.ASGITransport** |
| 린트 · 포맷 | oxlint + prettier | **ruff** (둘 다) + mypy |
| API 문서 | `@nestjs/swagger` `/v1/docs` | FastAPI 자동 생성 `/v1/docs`, `/v1/openapi.json` |
| JWT | (미구현) | **PyJWT** — HS256, access 30분 |
| 비밀번호 | (미구현) | **bcrypt** 직접 사용, cost 12 |
| DB · Redis · Firebase · Railway | | **유지** |

## 이유

AI 파트(프롬프트, 규칙 파서, EXIF 제거)가 Python 에 몰려 있다. 박영준님이 Colab 에서 검증한 코드를
언어 변환 없이 `app/services/ai/` 로 옮길 수 있다. NestJS 의 강점인 프론트–백엔드 타입 공유는
클라이언트가 Dart 라서 이 프로젝트에서 무효다. 모바일 기본 주소 `10.0.2.2:8000` 이 uvicorn 기본 포트와 같다.

## 명세(§14)와 다르게 고른 것

명세 §14.3 은 `python-jose` 와 `passlib[bcrypt]` 를 적었다. 둘 다 쓰지 않는다.

- `python-jose` 는 2021년 이후 유지보수가 멈췄다. `PyJWT` 가 같은 일을 하고 활발하다.
- `passlib` 는 `bcrypt` 4.1 이상과 호환되지 않는다 (`__about__` 속성 제거로 경고·오류). `bcrypt` 를 직접 쓰면 코드가 다섯 줄이다.

refresh 토큰은 JWT 가 아니라 **무작위 불투명 문자열**이다. DB `refresh_tokens.token_hash` 에 SHA-256 만 저장한다(ERD §3.2).
rotation 과 재사용 감지가 DB 행으로 구현되므로 JWT 일 이유가 없다.

## 대가

- Alembic 은 Prisma Migrate 보다 손이 간다. `--autogenerate` 결과를 **사람이 반드시 읽고 고친다** (`docs/database/migration-policy.md`).
- FastAPI 에는 NestJS 같은 구조 강제가 없다. "엔드포인트에 로직 금지, 서비스 계층 분리"를 **팀 규칙**으로 지킨다 (README §5).
- async SQLAlchemy 2.0 의 세션·`selectinload`·N+1 은 처음 만나면 시간을 먹는다. 5주차 TODO CRUD 전에 "TODO 목록 + 목표 조인" 쿼리를 한 번 끝까지 짜 본다.

## 이 결정으로 고친 문서

- `README.md`, `CONTRIBUTING.md`, `.github/workflows/ci.yml`, `.github/PULL_REQUEST_TEMPLATE.md`
- `docs/database/migration-policy.md` (Prisma → Alembic)
- `docs/architecture/module-map.md`, `docs/OWNERSHIP.md`, `.github/CODEOWNERS.example` (경로)
- `docs/specs/README.md` 의 충돌 표 1·3·5번은 원문 보존 원칙상 그대로 두고, 이 문서를 우선한다.
