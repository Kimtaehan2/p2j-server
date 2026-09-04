# DB 마이그레이션 정책

담당: 박영준(설계) · 김태한(운영). 스키마와 마이그레이션은 **두 사람이 함께 리뷰**한다.

## 도구

**Prisma Migrate 만 사용한다.**

`03-erd-v1.md` 7절은 Alembic(Python)을 권하지만, 이 저장소의 ORM 은 Prisma 다.
마이그레이션 도구를 두 개 쓰면 어느 쪽이 실제 스키마의 원본인지 알 수 없게 된다.
**Alembic 을 도입하지 않는다.**

## 현재 상태

이번 scaffold 에는 **모델도 마이그레이션도 없다.** datasource 와 Client 생성만 구성되어 있다.
`prisma/schema.prisma` 에 ERD v1 의 15개 테이블을 옮기는 작업이 다음 순서다.

## 로컬 작업 순서

```bash
docker compose up -d                       # PostgreSQL 16 + Redis 7
npx prisma migrate dev --create-only       # SQL 만 생성. 자동 적용하지 않는다
#   → prisma/migrations/<타임스탬프>_<이름>/migration.sql 을 눈으로 검토한다
#   → Prisma 가 표현하지 못하는 제약은 여기에 직접 추가한다
npx prisma migrate dev                     # 검토를 마친 뒤 적용
npm run prisma:generate
```

`--create-only` 없이 바로 적용하지 않는다. 의도하지 않은 컬럼 삭제를 눈으로 걸러야 한다.

## 직접 SQL 에 넣어야 하는 제약

Prisma 스키마로 표현할 수 없다. `migration.sql` 에 손으로 추가한다.

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
CREATE INDEX idx_todo_user_date_alive
  ON todo_items (user_id, date) WHERE deleted_at IS NULL;
CREATE INDEX idx_proofs_group_created_alive
  ON proofs (group_id, created_at DESC) WHERE deleted_at IS NULL;
```

## 금지 사항

- **병합·적용된 마이그레이션을 수정하거나 삭제하지 않는다.** 되돌려야 하면 새 마이그레이션을 추가한다.
- **공유 DB · 운영 DB 에서 `prisma db push` 를 쓰지 않는다.** 마이그레이션 이력이 남지 않는다.
- **`docker compose down -v` 를 쓰지 않는다.** named volume 이 지워져 팀 공용 개발 데이터가 날아간다.
- 운영 DB 에 로컬에서 직접 붙지 않는다.

## 운영 배포

Railway 배포 시 자동 실행한다.

```json
{
  "build": "prisma generate && nest build",
  "start:prod": "prisma migrate deploy && node dist/main.js"
}
```

`migrate deploy` 만 쓴다. `migrate dev` 는 로컬 전용이며 운영에서 실행하면 데이터가 날아갈 수 있다.

> 위 `build` / `start:prod` 는 Railway 배포 작업에서 반영한다.
> 이번 scaffold 의 `package.json` 은 마이그레이션이 아직 없으므로 `nest build` / `node dist/main.js` 만 실행한다.

## PK 타입

ERD 문서의 `bigserial` 대신 **Prisma `Int`(serial)** 를 쓴다.
Prisma 의 `BigInt` 는 JS `BigInt` 로 매핑되어 `JSON.stringify` 가 그대로 예외를 던진다.
학기 프로젝트 규모에서 21억 건을 넘길 일은 없다.

## 테이블·컬럼 이름

`@@map` / `@map` 으로 snake_case 를 유지해 `03-erd-v1.md` 와 1:1 로 대응시킨다.
Prisma 모델 필드는 camelCase, DB 는 snake_case 다.
