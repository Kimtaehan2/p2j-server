# 0002. 런타임과 패키지 버전

- 상태: **폐기** — `0003-fastapi.md` (2026-09-05) 로 대체. Node·NestJS·Prisma 는 더 이상 쓰지 않는다. 기록용으로 남긴다.
- 결정일: 2026-09-04

## 선택한 버전

| 대상 | 버전 | 비고 |
| --- | --- | --- |
| Node.js | 24.18.0 (24 LTS) | `.nvmrc` = `24`, `package.json` engines = `>=24 <25` |
| 패키지 매니저 | npm 11.16.0 | `package-lock.json` 커밋 |
| NestJS | 12.0.1 | Node 24 호환 안정 버전 |
| TypeScript | 6.0.3 | NestJS 12 템플릿 기본값 |
| Prisma ORM | **7.10.0** | `prisma`, `@prisma/client`, `@prisma/adapter-pg` 모두 동일 버전으로 **고정** |
| PostgreSQL | 16 (`postgres:16-alpine`) | Docker Compose |
| Redis | 7 (`redis:7-alpine`) | Docker Compose |
| Redis 클라이언트 | ioredis 6.0.0 | **하나만 쓴다.** 다른 Redis 라이브러리를 섞지 않는다 |
| 테스트 | vitest 4 | NestJS 12 기본값 (Jest 아님) |
| 린터 | oxlint 1 | NestJS 12 기본값 (ESLint 아님) |

## Prisma 를 7 에 고정한 이유

작업 시점의 `prisma@latest` 는 **`8.0.0-rc.12`** 였다. RC 를 학기 프로젝트의 기반으로 깔 수 없다.
`^` 나 `latest` 를 쓰면 다른 팀원이 `npm install` 하는 순간 8 로 올라간다.
그래서 세 패키지를 **범위 없이 정확한 버전으로** 적었다.

```json
"@prisma/adapter-pg": "7.10.0",
"@prisma/client": "7.10.0",
"prisma": "7.10.0"
```

`prisma` 와 `@prisma/client` 의 버전이 다르면 생성된 클라이언트와 런타임이 어긋난다.
올릴 때는 **셋을 같이** 올리고 `npm run prisma:generate` 를 다시 돌린다.

CLI 가 `prisma@latest` 로 업그레이드하라고 안내하지만 **따르지 않는다.**
8 로 올리는 것은 별도 결정 문서를 쓴 뒤에 한다.

## Prisma 7 에서 달라진 점

이 세 가지 때문에 6 이하의 예제를 그대로 쓰면 동작하지 않는다.

1. **`datasource` 블록에 `url` 을 쓸 수 없다.**
   접속 URL 은 `prisma.config.ts`(Migrate 용)와 `PrismaClient` 의 driver adapter(런타임 용)에서 지정한다.
   schema 에 `url = env("DATABASE_URL")` 을 남기면 `P1012` 로 검증이 실패한다.

2. **Rust query engine 대신 driver adapter 를 쓴다.**
   `@prisma/adapter-pg` + `pg` 조합이며 `new PrismaClient({ adapter })` 로 넘긴다.
   `prisma --version` 이 `Query Compiler: enabled` 로 나오는 것이 정상이다.

3. **`prisma.config.ts` 가 설정 원본이다.**
   Prisma 7 CLI 는 `.env` 를 자동으로 읽지 않는다.
   `prisma.config.ts` 에서 Node 24 내장 `process.loadEnvFile()` 로 직접 읽는다.

## 생성 코드 위치

```
generator client {
  provider = "prisma-client"
  output   = "../src/generated/prisma"
}
```

- Prisma 7 의 `prisma-client` generator 는 `output` 이 **필수**다.
- 생성 결과는 **TypeScript ESM** 이라 `src` 안에 두어야 `nest build` 가 함께 컴파일한다.
- `src/generated` 는 `.gitignore`, `.prettierignore`, `oxlint.json` 의 제외 목록에 넣었다.
  커밋하지 않고 `npm run prisma:generate` 로 재생성한다.
- **생성된 코드는 손으로 고치지 않는다.**

## ESM

NestJS 12 템플릿이 기본으로 ESM 이다 (`"type": "module"`, `module: nodenext`).
따라서 별도의 ESM 전환 작업이 없었고, Prisma 7 의 ESM 클라이언트와도 그대로 맞는다.

상대 경로 import 에는 **`.js` 확장자를 붙인다** (`./app.module.js`).
TypeScript 파일을 가리키더라도 `nodenext` 규칙상 컴파일 결과 기준으로 적어야 한다.

## 템플릿 선택

공식 `create-prisma --template nest` 를 검토했지만 쓰지 않았다.
`--help` 에 **Prisma 버전을 지정하는 옵션이 없어** 7 고정을 보장할 수 없고,
기본값이 `latest`(= 8 RC)로 잡힌다.

대신 `@nestjs/cli` 로 표준 NestJS 프로젝트를 만들고 Prisma 7 을 직접 설치했다.

```bash
npx @nestjs/cli@latest new p2j-server --package-manager npm --skip-git --skip-install --strict
```

## npm install 스크립트 경고

npm 11 은 의존성의 install 스크립트를 기본 차단한다.

```
npm warn allow-scripts  prisma@7.10.0 (preinstall), @prisma/engines@7.10.0 (postinstall), @scarf/scarf@1.4.0 (postinstall)
```

**허용하지 않아도 된다.** 확인 결과 schema engine 바이너리는 패키지에 동봉되어 있고
`prisma validate` / `generate` 가 정상 동작한다. `@scarf/scarf` 는 사용 통계 수집이라 막는 편이 낫다.
