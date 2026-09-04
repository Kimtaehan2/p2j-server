# 명세 원문 보관

원본을 그대로 복사해 둔 것이다. **이 폴더의 파일은 고치지 않는다.**
내용을 바꿔야 하면 원본 문서를 갱신하고 다시 복사한 뒤, 무엇이 바뀌었는지 PR 설명에 적는다.

| 파일 | 문서 | 줄 수 |
| --- | --- | --- |
| `01-development-plan.md` | 개발 착수 문서 | 160 |
| `02-api-v1.md` | API 명세 v1 | 782 |
| `03-erd-v1.md` | ERD · DB 스키마 설계서 v1 | 546 |
| `04-backend-v1.md` | 백엔드 명세서 v1 | 856 |

## 충돌 시 우선순위

문서끼리 어긋나면 위에 있는 쪽을 따른다.

1. **외부 API 경로 · 요청 · 응답 · 오류** → `02-api-v1.md`
2. **서버 구현 · 기술 선택** → `04-backend-v1.md`
3. **데이터 의미 · 관계** → `03-erd-v1.md`
4. **역할 · 저장소 · 일정** → `01-development-plan.md`
5. **모바일의 실제 동작** → `p2j-mobile` 저장소 코드

## 이미 해결된 충돌

착수 전에 확정한 사항이다. 문서에 반대로 적혀 있어도 아래를 따른다.

| # | 충돌 | 결론 |
| --- | --- | --- |
| 1 | `03-erd-v1.md` 7절이 Alembic(Python)을 권한다 | **Prisma Migrate** 를 쓴다. Alembic 언급은 무효 |
| 2 | `01-development-plan.md` 의 옛 엔드포인트 예시 (`/todos/from-voice`, `/verifications`) | **`02-api-v1.md`** 를 따른다 (`/ai/parse`, `/proofs`). 모바일 Repository 가 이미 v1 경로로 짜여 있다 |
| 3 | NestJS 기본 포트는 3000, 모바일 baseURL 은 `http://10.0.2.2:8000/v1` | 서버는 **8000** 번을 쓰고 전역 prefix 는 **`v1`** |
| 4 | ERD 는 S3 presign, 착수 문서는 Firebase Storage | **Firebase Storage** + Admin SDK signed URL. 흐름은 presign 과 동일 |
| 5 | ERD 의 `bigserial` PK | **Prisma `Int`(serial)** 로 낮춘다. `BigInt` 는 JS `BigInt` 로 매핑되어 `JSON.stringify` 가 그대로 죽는다 |
| 6 | DB 버전 | **PostgreSQL 16**, **Redis 7** |
