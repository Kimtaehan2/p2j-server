> `p2j-server` · NestJS + Prisma + PostgreSQL + Redis
담당: 김태한 (백엔드) / 박영준 (DB 설계 · AI 파이프라인)
기준 문서: API 명세 v1, ERD v1, `p2j-mobile` README (커밋 2건 기준)
> 

---

## 0. 선행 정리 — 자료 간 충돌 5건

착수 전에 아래를 확정해야 한다. 프론트엔드가 이미 명세 v1로 구현되어 있으므로, **충돌 시 명세 v1과 리포지토리 코드가 기준**이다.

| # | 충돌 | 결론 |
| --- | --- | --- |
| 1 | 스택 문서는 NestJS+Prisma, ERD 문서는 Alembic(Python) 권장 | **Prisma Migrate**를 쓴다. ERD 문서 7절의 Alembic 언급은 무효 |
| 2 | 셋업 문서 Day 0의 엔드포인트 예시(`/todos/from-voice`, `/verifications`) vs 명세 v1(`/ai/parse`, `/proofs`) | **명세 v1**. 프론트 Repository가 이미 v1 경로로 짜여 있다 |
| 3 | 프론트 기본 baseURL이 `http://10.0.2.2:8000/v1` — NestJS 기본 포트는 3000 | 서버가 **8000번**을 쓴다. `PORT=8000`, 전역 prefix `v1` |
| 4 | ERD 문서는 S3 presign, 스택 문서는 Firebase Storage | **Firebase Storage** + Admin SDK signed URL. 흐름은 presign과 동일 |
| 5 | ERD의 `bigserial` PK vs Prisma | **`Int`(serial)로 낮춘다.** Prisma에서 `BigInt`는 JS `BigInt`로 매핑되어 `JSON.stringify`가 그대로 죽는다. 학기 프로젝트 규모에서 21억 건을 넘길 일은 없다 |

---

## 1. 프로젝트 구조

```
p2j-server/
├── prisma/
│   ├── schema.prisma
│   ├── migrations/
│   └── seed.ts                    프론트 fixture와 동일한 시드
├── src/
│   ├── main.ts                    포트 8000, 전역 prefix 'v1'
│   ├── app.module.ts
│   ├── common/
│   │   ├── interceptors/
│   │   │   └── response.interceptor.ts     { data: ... } 래핑
│   │   ├── filters/
│   │   │   └── all-exceptions.filter.ts    { error: { code, message, details } }
│   │   ├── exceptions/
│   │   │   └── app.exception.ts            코드 기반 예외
│   │   ├── decorators/
│   │   │   ├── current-user.decorator.ts
│   │   │   └── public.decorator.ts
│   │   ├── guards/
│   │   │   └── jwt-auth.guard.ts           전역 적용, @Public()로 해제
│   │   ├── pipes/                          ValidationPipe 설정
│   │   └── utils/
│   │       ├── service-day.ts              04:00 KST 하루 경계 계산
│   │       └── cursor.ts                   커서 인코딩·디코딩
│   ├── infra/
│   │   ├── prisma/                         PrismaService
│   │   ├── redis/                          RedisService
│   │   └── storage/                        FirebaseStorageService
│   ├── modules/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── goals/
│   │   ├── todos/
│   │   ├── ai/                 parse, load-check
│   │   ├── stats/
│   │   ├── groups/             group, member, invite
│   │   ├── declarations/
│   │   ├── proofs/             proof, comment, reaction
│   │   ├── uploads/
│   │   └── batch/              스케줄 잡
│   └── integrations/
│       ├── clova/              STT
│       └── llm/                GPT-4o-mini
├── test/
├── .env.example
└── docker-compose.yml          postgres + redis
```

모듈은 **명세 v1의 섹션 구분을 그대로 따른다.** 프론트 feature 폴더(`auth`/`todo`/`goal`)와도 이름이 맞아 논의할 때 서로 헷갈리지 않는다.

---

## 2. 환경변수 (`.env.example`)

```bash
# 서버
NODE_ENV=development
PORT=8000

# DB
DATABASE_URL="postgresql://postgres:devpass@localhost:5432/p2j?schema=public"

# Redis
REDIS_URL="redis://localhost:6379"

# JWT
JWT_ACCESS_SECRET=change-me
JWT_ACCESS_TTL=3600            # 1시간 (초)
JWT_REFRESH_SECRET=change-me-too
JWT_REFRESH_TTL=2592000        # 30일

# 도메인 규칙
SERVICE_DAY_START_HOUR=4       # 하루 경계 04:00 KST
DECLARATION_CUTOFF_HOUR=       # 비우면 마감 없음 (2주차 결정 사항)

# Firebase
FIREBASE_PROJECT_ID=
FIREBASE_CLIENT_EMAIL=
FIREBASE_PRIVATE_KEY=          # 개행은 \n 이스케이프
FIREBASE_STORAGE_BUCKET=

# 외부 API
CLOVA_SPEECH_INVOKE_URL=
CLOVA_SPEECH_SECRET=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# 제한
AI_PARSE_DAILY_LIMIT=30
PROOF_IMAGE_MAX_BYTES=5242880  # 5MB
```

**실키는 절대 커밋하지 않는다.** `.env.example`만 올리고 실제 값은 Discord DM이나 Notion 비공개 페이지로 공유한다. Railway에는 대시보드 환경변수로 직접 넣는다.

---

## 3. Prisma 스키마

ERD v1을 Prisma로 옮긴 것이다. 테이블·컬럼명은 `@@map`/`@map`으로 snake_case를 유지해 ERD 문서와 1:1 대응시킨다.

```
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// ---------- ENUM ----------
enum GoalType      { single recurring }
enum FrequencyUnit { week month }
enum GoalStatus    { active completed abandoned }
enum TodoStatus    { pending done deferred skipped }
enum TodoSource    { ai_suggested manual auto_scheduled }
enum InputSource   { stt text }
enum ParseStatus   { ok partial fallback }
enum CheckLevel    { ok warning }
enum MemberRole    { owner member }
enum ReactionType  { fire clap heart muscle }

// ---------- 사용자 ----------
model User {
  id               Int       @id @default(autoincrement()) @map("user_id")
  email            String    @unique @db.VarChar(255)
  passwordHash     String    @map("password_hash") @db.VarChar(255)
  nickname         String    @db.VarChar(30)
  profileImageUrl  String?   @map("profile_image_url") @db.VarChar(500)
  dayStartHour     Int       @default(4) @map("day_start_hour") @db.SmallInt
  createdAt        DateTime  @default(now()) @map("created_at") @db.Timestamptz
  updatedAt        DateTime  @updatedAt @map("updated_at") @db.Timestamptz
  deletedAt        DateTime? @map("deleted_at") @db.Timestamptz

  refreshTokens    RefreshToken[]
  goals            Goal[]
  todoItems        TodoItem[]
  aiParses         AiParse[]
  loadChecks       LoadCheck[]
  dailyStats       UserDailyStat[]
  ownedGroups      Group[]         @relation("GroupOwner")
  memberships      GroupMember[]
  declarations     Declaration[]
  proofs           Proof[]
  comments         Comment[]
  reactions        Reaction[]
  invitesCreated   GroupInvite[]

  @@map("users")
}

model RefreshToken {
  id        Int       @id @default(autoincrement()) @map("token_id")
  userId    Int       @map("user_id")
  tokenHash String    @map("token_hash") @db.VarChar(255)
  expiresAt DateTime  @map("expires_at") @db.Timestamptz
  revokedAt DateTime? @map("revoked_at") @db.Timestamptz
  createdAt DateTime  @default(now()) @map("created_at") @db.Timestamptz

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([tokenHash])
  @@index([userId])
  @@map("refresh_tokens")
}

// ---------- 목표 · 투두 ----------
model Goal {
  id               Int           @id @default(autoincrement()) @map("goal_id")
  userId           Int           @map("user_id")
  title            String        @db.VarChar(100)
  type             GoalType
  frequencyTimes   Int?          @map("frequency_times") @db.SmallInt
  frequencyPer     FrequencyUnit? @map("frequency_per")
  durationWeeks    Int?          @map("duration_weeks") @db.SmallInt
  startDate        DateTime      @map("start_date") @db.Date
  endDate          DateTime?     @map("end_date") @db.Date
  estimatedMinutes Int?          @map("estimated_minutes") @db.SmallInt
  status           GoalStatus    @default(active)
  parseId          String?       @map("parse_id") @db.Uuid
  createdAt        DateTime      @default(now()) @map("created_at") @db.Timestamptz
  updatedAt        DateTime      @updatedAt @map("updated_at") @db.Timestamptz
  deletedAt        DateTime?     @map("deleted_at") @db.Timestamptz

  user      User       @relation(fields: [userId], references: [id])
  parse     AiParse?   @relation(fields: [parseId], references: [id])
  todoItems TodoItem[]

  @@index([userId, status])
  @@map("goals")
}

model TodoItem {
  id               Int        @id @default(autoincrement()) @map("todo_id")
  userId           Int        @map("user_id")
  goalId           Int?       @map("goal_id")
  title            String     @db.VarChar(100)
  date             DateTime   @db.Date
  status           TodoStatus @default(pending)
  estimatedMinutes Int?       @map("estimated_minutes") @db.SmallInt
  actualMinutes    Int?       @map("actual_minutes") @db.SmallInt
  completedAt      DateTime?  @map("completed_at") @db.Timestamptz
  declaredAt       DateTime?  @map("declared_at") @db.Timestamptz
  displayOrder     Int        @default(0) @map("display_order") @db.SmallInt
  source           TodoSource
  deferredFrom     DateTime?  @map("deferred_from") @db.Date
  createdAt        DateTime   @default(now()) @map("created_at") @db.Timestamptz
  updatedAt        DateTime   @updatedAt @map("updated_at") @db.Timestamptz
  deletedAt        DateTime?  @map("deleted_at") @db.Timestamptz

  user             User              @relation(fields: [userId], references: [id])
  goal             Goal?             @relation(fields: [goalId], references: [id])
  declarationItems DeclarationItem[]

  @@index([userId, date])
  @@index([goalId, status])
  @@index([userId, completedAt])
  @@map("todo_items")
}

// ---------- AI ----------
model AiParse {
  id             String       @id @default(uuid()) @map("parse_id") @db.Uuid
  userId         Int          @map("user_id")
  rawText        String       @map("raw_text")
  source         InputSource
  sttConfidence  Decimal?     @map("stt_confidence") @db.Decimal(3, 2)
  status         ParseStatus
  resultJson     Json         @map("result_json")
  model          String?      @db.VarChar(50)
  latencyMs      Int?         @map("latency_ms")
  inputTokens    Int?         @map("input_tokens")
  outputTokens   Int?         @map("output_tokens")
  accepted       Boolean?
  modifiedFields Json?        @map("modified_fields")
  createdAt      DateTime     @default(now()) @map("created_at") @db.Timestamptz

  user  User   @relation(fields: [userId], references: [id])
  goals Goal[]

  @@index([userId, createdAt])
  @@map("ai_parses")
}

model LoadCheck {
  id              String    @id @default(uuid()) @map("check_id") @db.Uuid
  userId          Int       @map("user_id")
  date            DateTime  @db.Date
  level           CheckLevel
  message         String?
  evidenceJson    Json      @map("evidence_json")
  suggestionsJson Json?     @map("suggestions_json")
  accepted        Boolean?
  appliedTodoIds  Int[]     @map("applied_todo_ids")
  respondedAt     DateTime? @map("responded_at") @db.Timestamptz
  createdAt       DateTime  @default(now()) @map("created_at") @db.Timestamptz

  user User @relation(fields: [userId], references: [id])

  @@unique([userId, date])
  @@map("load_checks")
}

model UserDailyStat {
  userId                Int      @map("user_id")
  date                  DateTime @db.Date
  totalCount            Int      @default(0) @map("total_count") @db.SmallInt
  doneCount             Int      @default(0) @map("done_count") @db.SmallInt
  achievementRate       Decimal  @default(0) @map("achievement_rate") @db.Decimal(4, 3)
  totalEstimatedMinutes Int      @default(0) @map("total_estimated_minutes")
  totalActualMinutes    Int      @default(0) @map("total_actual_minutes")
  heavyDoneCount        Int      @default(0) @map("heavy_done_count") @db.SmallInt
  streakCount           Int      @default(0) @map("streak_count") @db.SmallInt
  updatedAt             DateTime @updatedAt @map("updated_at") @db.Timestamptz

  user User @relation(fields: [userId], references: [id])

  @@id([userId, date])
  @@index([userId, date(sort: Desc)])
  @@map("user_daily_stats")
}

// ---------- 소셜 ----------
model Group {
  id              Int       @id @default(autoincrement()) @map("group_id")
  name            String    @db.VarChar(50)
  ownerId         Int       @map("owner_id")
  maxMembers      Int       @default(6) @map("max_members") @db.SmallInt
  groupStreak     Int       @default(0) @map("group_streak") @db.SmallInt
  lastStreakDate  DateTime? @map("last_streak_date") @db.Date
  createdAt       DateTime  @default(now()) @map("created_at") @db.Timestamptz
  deletedAt       DateTime? @map("deleted_at") @db.Timestamptz

  owner        User          @relation("GroupOwner", fields: [ownerId], references: [id])
  members      GroupMember[]
  invites      GroupInvite[]
  declarations Declaration[]
  proofs       Proof[]

  @@map("groups")
}

model GroupMember {
  id         Int        @id @default(autoincrement())
  groupId    Int        @map("group_id")
  userId     Int        @map("user_id")
  role       MemberRole @default(member)
  joinedAt   DateTime   @default(now()) @map("joined_at") @db.Timestamptz
  leftAt     DateTime?  @map("left_at") @db.Timestamptz
  lastReadAt DateTime?  @map("last_read_at") @db.Timestamptz

  group Group @relation(fields: [groupId], references: [id])
  user  User  @relation(fields: [userId], references: [id])

  @@index([userId])
  @@index([groupId])
  @@map("group_members")
}

model GroupInvite {
  id        Int       @id @default(autoincrement()) @map("invite_id")
  groupId   Int       @map("group_id")
  code      String    @unique @db.VarChar(12)
  createdBy Int       @map("created_by")
  expiresAt DateTime  @map("expires_at") @db.Timestamptz
  revokedAt DateTime? @map("revoked_at") @db.Timestamptz
  createdAt DateTime  @default(now()) @map("created_at") @db.Timestamptz

  group   Group @relation(fields: [groupId], references: [id])
  creator User  @relation(fields: [createdBy], references: [id])

  @@map("group_invites")
}

model Declaration {
  id        Int      @id @default(autoincrement()) @map("declaration_id")
  groupId   Int      @map("group_id")
  userId    Int      @map("user_id")
  date      DateTime @db.Date
  lockedAt  DateTime @map("locked_at") @db.Timestamptz
  createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz

  group Group             @relation(fields: [groupId], references: [id])
  user  User              @relation(fields: [userId], references: [id])
  items DeclarationItem[]

  @@unique([groupId, userId, date])
  @@index([groupId, date])
  @@map("declarations")
}

model DeclarationItem {
  id            Int    @id @default(autoincrement()) @map("declaration_item_id")
  declarationId Int    @map("declaration_id")
  todoId        Int?   @map("todo_id")
  titleSnapshot String @map("title_snapshot") @db.VarChar(100)

  declaration Declaration @relation(fields: [declarationId], references: [id], onDelete: Cascade)
  todo        TodoItem?   @relation(fields: [todoId], references: [id], onDelete: SetNull)
  proof       Proof?

  @@unique([declarationId, todoId])
  @@map("declaration_items")
}

model Proof {
  id                Int       @id @default(autoincrement()) @map("post_id")
  declarationItemId Int       @unique @map("declaration_item_id")
  groupId           Int       @map("group_id")
  userId            Int       @map("user_id")
  fileKey           String    @map("file_key") @db.VarChar(500)
  caption           String?   @db.VarChar(200)
  createdAt         DateTime  @default(now()) @map("created_at") @db.Timestamptz
  deletedAt         DateTime? @map("deleted_at") @db.Timestamptz

  declarationItem DeclarationItem @relation(fields: [declarationItemId], references: [id])
  group           Group           @relation(fields: [groupId], references: [id])
  user            User            @relation(fields: [userId], references: [id])
  comments        Comment[]
  reactions       Reaction[]

  @@index([groupId, createdAt(sort: Desc)])
  @@map("proofs")
}

model Comment {
  id        Int       @id @default(autoincrement()) @map("comment_id")
  postId    Int       @map("post_id")
  userId    Int       @map("user_id")
  content   String    @db.VarChar(500)
  createdAt DateTime  @default(now()) @map("created_at") @db.Timestamptz
  deletedAt DateTime? @map("deleted_at") @db.Timestamptz

  post Proof @relation(fields: [postId], references: [id], onDelete: Cascade)
  user User  @relation(fields: [userId], references: [id])

  @@index([postId, createdAt])
  @@map("comments")
}

model Reaction {
  id     Int          @id @default(autoincrement()) @map("reaction_id")
  postId Int          @map("post_id")
  userId Int          @map("user_id")
  type   ReactionType

  post Proof @relation(fields: [postId], references: [id], onDelete: Cascade)
  user User  @relation(fields: [userId], references: [id])

  @@unique([postId, userId])
  @@map("reactions")
}
```

### 3.1 Prisma가 표현하지 못하는 제약

아래는 마이그레이션 SQL을 직접 수정해서 넣는다. `prisma migrate dev --create-only`로 SQL을 만든 뒤 손으로 추가하고 적용한다.

```sql
-- 부분 유니크: 탈퇴 후 재가입 허용, 중복 가입 차단
CREATE UNIQUE INDEX uq_group_active_member
  ON group_members (group_id, user_id) WHERE left_at IS NULL;

-- 반복 목표는 빈도 필수
ALTER TABLE goals ADD CONSTRAINT chk_goal_frequency
  CHECK (type = 'single' OR (frequency_times IS NOT NULL AND frequency_per IS NOT NULL));

ALTER TABLE goals ADD CONSTRAINT chk_goal_date_order
  CHECK (end_date IS NULL OR end_date >= start_date);

-- 그룹 정원 3~6명
ALTER TABLE groups ADD CONSTRAINT chk_group_size
  CHECK (max_members BETWEEN 3 AND 6);

-- 부분 인덱스 (soft delete 제외)
CREATE INDEX idx_todo_user_date_alive ON todo_items (user_id, date) WHERE deleted_at IS NULL;
CREATE INDEX idx_proofs_group_created_alive ON proofs (group_id, created_at DESC) WHERE deleted_at IS NULL;
```

---

## 4. 공통 레이어

### 4.1 응답 래핑 (`ResponseInterceptor`)

컨트롤러는 순수 객체만 반환하고, 인터셉터가 `{ data: ... }`로 감싼다. 목록 응답은 서비스가 `{ items, nextCursor }`를 반환하면 인터셉터가 `{ data, page }` 형태로 변환한다.

**204 응답은 감싸지 않는다.** 프론트의 `uncomplete`가 바디 없음을 전제로 로컬에서 summary를 다시 계산하므로, 여기서 바디를 실어 보내면 계약이 깨진다.

### 4.2 예외 필터 (`AllExceptionsFilter`)

모든 예외를 명세 v1의 형식으로 변환한다.

```tsx
// common/exceptions/app.exception.ts
export class AppException extends HttpException {
  constructor(
    public readonly code: string,
    status: HttpStatus,
    message: string,
    public readonly details?: Record<string, unknown>,
  ) {
    super({ code, message, details }, status);
  }
}

// 사용 예
throw new AppException('DECLARED_TODO_LOCKED', HttpStatus.UNPROCESSABLE_ENTITY,
  '그룹에 선언한 할 일은 오늘 수정할 수 없습니다.', { todo_id: todoId });
```

필터가 처리해야 할 것:

- `AppException` → 그대로 매핑
- `ValidationPipe` 오류 → `400 VALIDATION_ERROR`, `details.fields`에 필드별 메시지
- Prisma `P2002`(유니크 위반) → 상황별 코드 매핑
- 그 외 → `500 INTERNAL_ERROR`, 스택은 로그에만 남기고 응답에 넣지 않음

### 4.3 직렬화 규칙

프론트가 snake_case 키를 기대한다(`achievement_rate`, `is_declared`, `estimated_minutes`). Prisma 모델은 camelCase이므로 **응답 DTO에서 명시적으로 변환**한다. 전역 자동 변환 인터셉터는 쓰지 않는다. `parse_id` 같은 값이 의도치 않게 바뀌면 추적이 어렵다.

날짜는 `YYYY-MM-DD` 문자열, 시각은 `+09:00` 오프셋 포함 ISO 8601로 직렬화한다.

### 4.4 인증 가드

`JwtAuthGuard`를 `APP_GUARD`로 전역 등록하고, `@Public()` 데코레이터가 붙은 라우트만 통과시킨다. Public은 `/auth/signup`, `/auth/login`, `/auth/refresh`, 헬스체크뿐이다.

기본이 "인증 필요"여야 한다. 반대로 하면 새 컨트롤러를 추가할 때 가드를 빠뜨려 인증 없이 열리는 사고가 난다.

### 4.5 하루 경계 계산 (`service-day.ts`)

```tsx
/** 04:00 KST를 기준으로 '서비스상 오늘' 날짜를 반환한다. */
export function getServiceDay(now: Date, dayStartHour = 4): string {
  const kst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  if (kst.getUTCHours() < dayStartHour) {
    kst.setUTCDate(kst.getUTCDate() - 1);
  }
  return kst.toISOString().slice(0, 10);
}
```

**날짜를 다루는 모든 곳에서 이 함수만 쓴다.** `new Date()`로 오늘을 구하는 코드가 하나라도 섞이면 새벽 시간대에 데이터가 어긋난다. Railway 컨테이너는 UTC로 뜨므로 서버 로컬 타임존에 의존하면 안 된다.

### 4.6 커서 페이지네이션

`{ "id": 123, "createdAt": "..." }`를 base64로 인코딩한다. 복호화 실패 시 `400 VALIDATION_ERROR`. offset 기반은 피드에서 새 글이 들어오면 항목이 중복·누락되므로 쓰지 않는다.

---

## 5. 모듈별 명세

### 5.1 `auth`

| 엔드포인트 | 메서드 | 인증 |
| --- | --- | --- |
| `/auth/signup` | POST | Public |
| `/auth/login` | POST | Public |
| `/auth/refresh` | POST | Public |
| `/auth/logout` | POST | 필요 |
| `/auth/me` | GET | 필요 |

**DTO 검증** (class-validator)

```tsx
export class SignupDto {
  @IsEmail() email: string;
  @MinLength(8, { context: { code: 'WEAK_PASSWORD' } }) password: string;
  @IsString() @Length(1, 30) nickname: string;
}
```

프론트 Mock이 8자 미만에서 `WEAK_PASSWORD`를 반환하도록 되어 있다. 서버도 동일하게 **8자 미만은 `400 WEAK_PASSWORD`**, 형식 오류는 `400 VALIDATION_ERROR`로 구분해야 프론트 에러 화면이 그대로 동작한다.

**비밀번호**: bcrypt, cost 10. 12는 Railway 무료 티어에서 로그인이 눈에 띄게 느려진다.

**Refresh 토큰 회전**

1. 전달받은 토큰을 해시해 `refresh_tokens`에서 조회
2. 없거나 `revoked_at`이 있거나 만료 → `401 TOKEN_EXPIRED`
3. 기존 행에 `revoked_at` 기록, 새 토큰 행 삽입, 새 access·refresh 반환
4. 1~3을 **하나의 트랜잭션**으로 묶는다

> 프론트 `AuthInterceptor`는 동시 401이 와도 재발급 Future를 하나만 유지한다. 서버가 회전을 쓰는 전제로 짜인 구조이므로, 회전을 빼면 프론트 로직이 헛돌게 된다.
> 

**`GET /auth/me`는 `today`를 반드시 포함한다.** 프론트가 오늘 날짜를 직접 계산하지 않고 이 값을 전역 상태(`serverTodayProvider`)로 쓴다. 이 필드가 빠지면 앱의 날짜 기준이 통째로 무너진다.

### 5.2 `goals`

| 엔드포인트 | 메서드 |
| --- | --- |
| `/goals` | GET, POST |
| `/goals/{id}` | GET, PATCH, DELETE |
| `/goals/{id}/dismiss-suggestion` | POST |

**생성 로직**

1. `type=recurring`이면 `frequency_times`, `frequency_per` 필수
2. `end_date = start_date + duration_weeks * 7 - 1`로 계산해 저장
3. `parse_id`가 있으면 소유자 일치 확인 후 연결
4. **미래 `todo_items`를 만들지 않는다.** 제안 수락 시점에만 생성

**진행률(`progress`) 계산**

```tsx
const targetCount = goal.type === 'recurring'
  ? goal.frequencyTimes * goal.durationWeeks
  : 1;
```

`done_count`, `current_week_done`은 `todo_items` 집계. 목록 조회에서 N+1이 나기 쉬우므로 `groupBy`로 한 번에 가져와 메모리에서 합친다.

**삭제**: soft delete. 연결된 미래 `todo_items`(오늘 이후, `pending`)도 함께 soft delete하되 과거 기록은 남긴다.

### 5.3 `todos`

| 엔드포인트 | 메서드 | 비고 |
| --- | --- | --- |
| `/todos?date=` | GET | `items` + `summary` |
| `/todos/week?start_date=` | GET | 홈 7일 캘린더 |
| `/todos` | POST |  |
| `/todos/{id}` | PATCH, DELETE | 선언 잠금 검사 |
| `/todos/{id}/complete` | POST |  |
| `/todos/{id}/uncomplete` | POST | **204, 바디 없음** |
| `/todos/{id}/defer` | POST |  |
| `/todos/suggestions` | GET | 규칙 기반 |

**선언 잠금 검사**

```tsx
if (todo.declaredAt !== null) {
  throw new AppException('DECLARED_TODO_LOCKED', 422, '...');
}
```

`PATCH`와 `DELETE`에만 적용한다. **`complete`/`uncomplete`는 잠금과 무관하게 허용**해야 한다. 선언한 일을 완료 체크하지 못하면 기능 자체가 성립하지 않는다.

**`/todos/week`는 `user_daily_stats`에서 읽는다.** 홈 화면 진입마다 호출되는데 `todo_items`를 7일치 집계하면 가장 먼저 느려지는 지점이 된다.

**`complete` 트랜잭션**

```
1. todo.status = done, completed_at = now, actual_minutes 기록
2. user_daily_stats upsert (total/done/achievement_rate/actual/heavy 갱신)
3. streak_count 재계산 (전일 행 참조)
4. 응답: { todo, goal_progress, personal_streak }
```

2·3번을 빠뜨리면 통계·랭킹·계획량 안내가 전부 어긋난다. 반드시 같은 트랜잭션 안에서 처리한다.

**`suggestions`는 LLM을 호출하지 않는다.** ERD 문서 6.1의 SQL을 `$queryRaw`로 쓰거나 Prisma로 옮긴다. 남은 기간 대비 남은 횟수 계산이라 규칙 기반이 정확하고 비용이 없다.

`dismiss-suggestion`은 Redis에 `dismiss:{userId}:{goalId}:{date}` 키를 TTL과 함께 저장하고, `suggestions` 조회 시 제외한다. DB 테이블을 늘릴 필요가 없다.

### 5.4 `ai`

| 엔드포인트 | 메서드 |
| --- | --- |
| `/ai/parse` | POST |
| `/ai/parse/{parse_id}/feedback` | POST |
| `/ai/load-check?date=` | GET |
| `/ai/load-check/{check_id}/response` | POST |

**3단계 폴백 (신청서 명시 사항)**

```
1단계  GPT-4o-mini + JSON Schema (strict) 호출
         성공 → status: "ok"
2단계  스키마 위반 또는 파싱 실패 → 1회 재시도
         실패 → 규칙 기반 파서 (정규식)
         부분 추출 성공 → status: "partial", uncertain_fields 명시
3단계  규칙 파서도 실패 → status: "fallback"
         제목만 채운 draft 1건 + 사용자 직접 입력 유도
```

규칙 파서가 잡아야 할 한국어 패턴:

- 빈도: `주 3회`, `일주일에 세 번`, `매일`, `주말마다`
- 기간: `한 달`, `4주`, `2주간`, `이번 학기`
- 소요: `한 시간`, `30분`, `1시간 반`

한글 수사(`세 번`, `한 달`)를 숫자로 바꾸는 매핑 테이블이 필요하다. LLM이 죽었을 때 이게 유일한 방어선이다.

**모든 호출을 `ai_parses`에 기록한다.** 실패한 호출도 남긴다. `status` 분포와 `accepted` 비율이 최종보고서의 정확도 근거이자, 신청서에 쓴 "한국어 목표 발화 표본으로 정확도를 확인"의 실제 데이터가 된다.

**타임아웃 8초, 실패 시 `503 AI_UNAVAILABLE`.** 프론트가 수동 입력 화면으로 전환한다. 무한정 기다리게 두면 앱이 멈춘 것처럼 보인다.

**레이트 리밋**: Redis `INCR ratelimit:ai:{userId}:{serviceDay}` + 하루 만료. 초과 시 `429 AI_RATE_LIMITED`. 기본 30회. 11월 토큰 예산 150,000원을 역산해 조정한다.

**`load-check`**

- `UNIQUE(user_id, date)`이므로 하루 첫 호출에만 계산하고 이후는 저장된 행을 반환
- 집계는 ERD 문서 6.2의 SQL. 14일 결과를 Redis에 캐시(TTL: 서비스일 종료까지)
- 실행 기록 7일 미만이면 `level: "ok"`, `message: null` — 근거가 없으면 경고하지 않는다
- LLM은 문구를 다듬는 용도로만 선택적 사용. 실패하면 템플릿 문구로 대체하고 요청 자체는 성공시킨다

### 5.5 `stats`

| 엔드포인트 | 메서드 |
| --- | --- |
| `/stats/summary?period=` | GET |
| `/stats/goals/{goal_id}` | GET |

`user_daily_stats`에서 읽는다. `by_hour`(시간대별 완료 분포)와 `most_deferred`만 `todo_items`를 직접 집계한다.

```sql
-- by_hour: KST 기준 시간대 추출
SELECT EXTRACT(HOUR FROM completed_at AT TIME ZONE 'Asia/Seoul') AS hour,
       COUNT(*) AS completed
FROM todo_items
WHERE user_id = $1 AND status = 'done' AND date BETWEEN $2 AND $3
GROUP BY 1 ORDER BY 1;
```

`AT TIME ZONE`을 빠뜨리면 UTC 기준으로 집계되어 9시간씩 밀린다.

### 5.6 `groups`

| 엔드포인트 | 메서드 |
| --- | --- |
| `/groups` | GET, POST |
| `/groups/{id}` | GET |
| `/groups/{id}/invite` | POST |
| `/groups/join` | POST |
| `/groups/{id}/members` | GET |
| `/groups/{id}/members/me` | DELETE |
- *`GroupMemberGuard`*를 만들어 `/groups/{id}/*` 전체에 적용한다. 각 서비스 메서드에서 개별 확인하면 반드시 한 군데를 빠뜨린다.

**초대 코드**: `P2J-` + 영숫자 6자(혼동되는 `0`/`O`/`1`/`I` 제외). 유효기간 7일. 재발급 시 기존 코드는 `revoked_at` 처리.

**가입**: 정원 확인 → 부분 유니크 인덱스 충돌 시 `409 ALREADY_MEMBER`. 동시 가입으로 정원이 초과되지 않도록 트랜잭션 내에서 `SELECT ... FOR UPDATE`로 그룹 행을 잠근다.

**탈퇴**: `left_at` 기록. 소유자가 탈퇴하면 가장 오래된 멤버에게 `owner` 승계, 마지막 1인이면 그룹 soft delete.

### 5.7 `declarations`

| 엔드포인트 | 메서드 |
| --- | --- |
| `/groups/{id}/declarations` | POST, GET |

**생성 트랜잭션**

```
1. todo_ids 소유권 확인 (전부 본인 것인지)
2. 날짜 일치 확인 (전부 해당 date인지)
3. declarations 삽입 (locked_at = now)
4. declaration_items 삽입 — title_snapshot에 제목 복사
5. 해당 todo_items의 declared_at = now
```

4·5번이 이 기능의 핵심이다. 스냅샷 없이 FK만 걸면 원본 투두를 지웠을 때 "어제 뭘 선언했는지"가 사라진다.

`UNIQUE(group_id, user_id, date)` 위반 → `409 ALREADY_DECLARED`.

**조회 시 미선언 멤버도 함께 반환한다.** `declaration_id: null`로 내려보낸다. 아직 선언하지 않은 사람이 목록에 보이는 것 자체가 이 앱의 압력 장치다.

### 5.8 `proofs` · `comments` · `reactions`

| 엔드포인트 | 메서드 |
| --- | --- |
| `/uploads/presign` | POST |
| `/groups/{id}/proofs` | POST |
| `/groups/{id}/feed` | GET |
| `/posts/{id}/comments` | POST, GET |
| `/comments/{id}` | DELETE |
| `/posts/{id}/reactions` | PUT, DELETE |

**Firebase Storage 업로드 흐름**

```tsx
const [url] = await bucket.file(fileKey).getSignedUrl({
  version: 'v4',
  action: 'write',
  expires: Date.now() + 10 * 60 * 1000,
  contentType: dto.contentType,
});
```

- `fileKey`: `proofs/{groupId}/{userId}/{uuid}.jpg` — 사용자 입력을 경로에 넣지 않는다
- 허용 타입: `image/jpeg`, `image/png`, `image/webp`만
- 클라이언트가 PUT으로 직접 업로드 후 `file_key`만 서버에 전달
- **서버는 파일이 실제로 올라갔는지 확인해야 한다.** `file.exists()`와 메타데이터 크기를 검사하고, 없거나 5MB 초과면 `422 INVALID_UPLOAD`

> Admin SDK는 Firebase Storage 보안 규칙을 우회한다. 권한 검사는 전적으로 서버 코드 책임이다.
> 

**피드 조회**는 명세대로 사용자별로 묶고 `missed_items`를 포함한다. 미달성을 숨기지 않는 것이 이 앱의 차별점이므로 API 레벨에서 강제한다.

**리액션**은 `PUT`으로 UPSERT. `UNIQUE(post_id, user_id)`가 있으므로 `upsert`가 곧 "1인 1리액션, 재호출 시 교체"가 된다.

### 5.9 `batch`

`@nestjs/schedule` 사용.

| 잡 | 시각(KST) | 내용 |
| --- | --- | --- |
| 그룹 스트릭 판정 | 매일 04:10 | 전일 대상. ERD 6.3 쿼리 |
| 만료 토큰 정리 | 매일 04:20 | `expires_at < now - 7d` 삭제 |
| 인증샷 정리 | 매일 04:30 | 보관기간 경과 시 스토리지 파일만 삭제 (미결) |

**Railway 인스턴스가 1개일 때만 안전하다.** 스케일 아웃하면 잡이 중복 실행된다. 이번 학기에는 단일 인스턴스로 고정한다.

크론 표현식에 타임존을 명시한다: `@Cron('10 4 * * *', { timeZone: 'Asia/Seoul' })`

---

## 6. 시드 데이터

`prisma/seed.ts`가 **프론트 Mock fixture와 같은 데이터**를 만들어야 한다. 실서버로 전환했을 때 화면이 동일하게 보여야 통합 시점의 문제를 빨리 찾을 수 있다.

- 계정: `test@p2j.dev` / `test1234`
- `taken@p2j.dev` — `EMAIL_ALREADY_EXISTS` 재현용
- 투두 4개, 목표 3개 (`normal` 시나리오와 동일)
- 지난 14일치 `todo_items` + `user_daily_stats` — 계획량 안내 테스트에 필요
- 날짜는 실행 시점 기준 상대값으로 생성. **하드코딩하면 다음 날 빈 화면이 된다** (프론트 fixture가 `{{TODAY}}` 플레이스홀더를 쓰는 것과 같은 이유)

---

## 7. 배포 · 운영

**Railway 구성**: 서버 서비스 + PostgreSQL 플러그인 + Redis 플러그인. `DATABASE_URL`과 `REDIS_URL`은 Railway가 자동 주입한다.

**빌드**

```json
{
  "build": "prisma generate && nest build",
  "start:prod": "prisma migrate deploy && node dist/main"
}
```

`migrate deploy`는 배포 시 자동 실행한다. `migrate dev`는 로컬 전용이며 운영에서 쓰면 데이터가 날아갈 수 있다.

**CORS**: Flutter web(`flutter run -d chrome`)으로 개발할 때 필요하다. 개발 환경에서만 `origin: true`, 운영은 차단.

**로깅**: 요청 ID, 사용자 ID, 소요 시간. 비밀번호·토큰·`raw_text`는 로그에 남기지 않는다.

**헬스체크**: `GET /v1/health` — DB·Redis 연결 확인. Railway가 이걸로 재시작을 판단한다.

---

## 8. 구현 순서

| 주차 | 대상 |
| --- | --- |
| 3주 | 스캐폴딩, Docker Compose, Prisma 초기화, 공통 레이어(필터·인터셉터·가드) |
| 4주 | `auth` 전체 + `/auth/me`의 `today` |
| 5주 | `goals` CRUD, `service-day` 유틸 확정 |
| 6주 | `todos` CRUD, `/todos/week`, 시드 데이터 |
| 7주 | `/uploads/presign`, `/todos/suggestions` |
| 8주 | Clova STT 연동, `/ai/parse` 1단계 |
| 9주 | `/ai/parse` 재시도·폴백, `feedback` |
| 10주 | `/ai/load-check`, `user_daily_stats` 갱신 로직, Redis 캐시 |
| 11주 | `complete`/`uncomplete`/`defer`, `/stats/*` |
| 12주 | `groups`, `declarations`, `proofs`, `feed` |
| 13주 | `comments`, `reactions`, `ranking`, `streak`, 배치 잡 |
| 14주 | 통합 테스트, 부하 점검, 에러 처리 보완 |
| 15주 | 최종 배포, API 문서 정리 |

**5주차 전에 `/auth/*`와 `/goals`가 떠야 한다.** 프론트가 이미 Mock으로 화면을 다 만들어 둔 상태라, 실서버 전환은 `--dart-define=USE_MOCK=false` 하나로 끝난다. 백엔드가 늦어지는 만큼 통합 검증 시점이 밀린다.

---

## 9. 미결 사항 (2주차 회의)

1. **`user_daily_stats` 갱신** — 완료 시점 즉시 반영을 기본으로 잡았다. 배치로 바꾸려면 통계 화면이 실시간이 아니게 된다는 점을 감수해야 한다.
2. **선언 마감 시각** — `DECLARATION_CUTOFF_HOUR`를 비워 두면 마감 없음. 11시로 정하면 "아침 선언"이라는 취지가 살지만 늦게 일어난 사람은 참여를 못 한다.
3. **미선언 멤버의 랭킹 처리** — 0%로 집계할지 제외할지. 0%로 하면 압력이 세지고, 제외하면 선언 자체를 안 하는 게 유리해진다. 후자는 기능을 무력화한다.
4. **인증샷 보관 기간** — Firebase Storage 무료 할당량(5GB)을 고려. 30일 후 파일만 삭제하고 `proofs` 행은 남기는 방식 권장.
5. **AI 일일 한도** — 기본 30회. 팀원 3명이 테스트하는 규모에서는 넉넉하지만, 시범 사용 기간에는 재산정이 필요하다.
6. **소셜 갱신 방식** — 폴링으로 시작. WebSocket은 13주차 이후 여유가 있을 때만.