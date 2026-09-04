> 목적: 신청서 문구 수정이 아니라, **실제 개발 착수를 위한 구조화·스케줄링·셋업 순서**를 정리한 문서.
팀: 김지호(프론트엔드) · 김태한(백엔드) · 박영준(DB & AI)
> 

---

## 1. 확정 기술 스택 (더 이상 후보 아님 — 이걸로 간다)

| 영역 | 확정 | 담당 |
| --- | --- | --- |
| 프론트엔드 | Flutter (Android 우선, iOS는 추후) | 김지호 |
| 상태관리 | Riverpod | 김지호 |
| 백엔드 | Node.js + NestJS | 김태한 |
| ORM | Prisma | 김태한 |
| DB | PostgreSQL | 박영준 (설계) / 김태한 (운영) |
| 캐시 | Redis (계획량 안내용 14일 집계 캐시) | 김태한 |
| STT | 네이버 클로바 스피치 API | 박영준 |
| LLM | GPT-4o-mini API | 박영준 |
| 이미지 저장 | Firebase Storage | 김태한 |
| 배포(학기 중) | Railway(백엔드) + Firebase(스토리지) | 김태한 |
| API 문서 | Postman Collection (+ Swagger 자동생성) | 김태한 |
| 디자인 | Figma | 김지호 |
| 협업 | GitHub + Discord/Notion | 전원 |

Prisma를 선택한 이유: TypeORM보다 스키마 정의·마이그레이션이 직관적이라 3인 학생팀에서 학습 비용이 낮음. Riverpod은 Provider보다 최신이고 테스트가 쉬워 추천.

---

## 2. 저장소 구조

**2개 레포로 분리**를 추천합니다 (모노레포 대신):

- `p2j-mobile` (Flutter)
- `p2j-server` (NestJS)

이유: 빌드/배포 파이프라인이 완전히 다르고, FE/BE가 API 계약만 지키면 서로의 내부 구현에 신경 쓸 필요가 없어 3인 팀에서 충돌 관리가 더 쉬움.

**브랜치 전략** (간단한 GitHub Flow — 3인 팀엔 Git Flow는 과함):

```
main       → 항상 배포 가능한 상태
develop    → 통합 브랜치
feature/*  → 기능별 (예: feature/stt-input, feature/todo-list)
```

PR은 최소 1인 리뷰 후 develop에 머지. main은 학기 말/중간보고서 시점에만 머지.

---

## 3. Day 0 — 개발 착수 전 공통 준비 (전원, 코드 짜기 전에 먼저)

순서가 중요합니다. 아래 순서를 지키지 않으면 나중에 API 형식이 안 맞아 다시 작업하는 일이 생깁니다.

1. **GitHub Organization 생성** → `p2j-mobile`, `p2j-server` 레포 생성, README·`.gitignore` 세팅
2. **API 계약 먼저 합의** (코드보다 먼저!) — Postman에 엔드포인트 목록만 먼저 정의
    - 예: `POST /todos/from-voice`, `GET /todos/today`, `POST /declarations`, `POST /verifications`
    - FE는 이 계약을 보고 Mock 데이터로 화면 개발 시작 가능 → BE 완성을 기다리지 않아도 됨
3. **ERD 초안 작성** (dbdiagram.io 추천 — 무료, 링크 공유만으로 팀 전체 열람 가능)
    - 최소 테이블: `User`, `Todo`, `ExecutionLog`, `Group`, `GroupMember`, `Declaration`, `Verification`, `Comment`
4. **환경변수 관리 규칙 합의**: `.env.example`만 커밋, 실제 키(클로바/OpenAI)는 Notion 비공개 페이지나 팀 Discord DM으로 공유. 절대 레포에 실키 커밋 금지
5. **API 키 미리 발급** (8~9주차에 필요하지만 지금 받아두면 초반에 테스트 가능):
    - NAVER Cloud Platform 가입 → Clova Speech 서비스 신청 (승인에 시간 걸릴 수 있어 최우선)
    - OpenAI API 키 발급 (또는 Anthropic API 키)

---

## 4. 역할별 로컬 환경 셋업 (설치 순서)

### 김지호 — 프론트엔드

```bash
# 1. Flutter SDK 설치 후 환경 점검
flutter doctor
# 2. Android Studio 설치 (에뮬레이터 포함) — 이번 학기는 Android 우선
# 3. VS Code + Flutter/Dart 확장 설치
# 4. 프로젝트 생성
flutter create p2j_mobile
cd p2j_mobile
flutter pub add riverpod flutter_riverpod dio
```

- `dio`는 HTTP 클라이언트(백엔드 API 호출용)
- Figma 계정 생성 후 팀 프로젝트 파일 하나로 공유

### 김태한 — 백엔드

```bash
# 1. Node.js LTS 설치 (v20.x)
node -v
# 2. NestJS CLI 설치
npm i -g @nestjs/cli
nest new p2j-server
# 3. Prisma 설치 및 초기화
cd p2j-server
npm i prisma @prisma/client
npx prisma init
# 4. PostgreSQL — Docker로 로컬 실행 (개별 설치보다 팀원 간 버전 통일이 쉬움)
docker run --name p2j-db -e POSTGRES_PASSWORD=devpass -p 5432:5432 -d postgres:16
# 5. Redis도 동일하게 Docker로
docker run --name p2j-redis -p 6379:6379 -d redis:7
```

- Postman 설치 후 팀 공유 워크스페이스 생성 (API 계약 문서 여기서 관리)
- Docker Desktop이 없다면 이게 최우선 설치 항목 — DB/Redis를 팀원 전체가 동일 버전으로 맞추는 게 목적

### 박영준 — DB & AI

- ERD 설계 주도 (dbdiagram.io) → 김태한과 함께 Prisma 스키마로 변환
- 클로바 스피치 API 테스트: 발급받은 키로 Postman에서 샘플 요청 먼저 성공시키기
- GPT-4o-mini API로 JSON 구조화 프롬프트 프로토타입 — Python이 익숙하면 별도 Jupyter/Colab 노트북에서 프롬프트만 먼저 검증한 뒤 BE에 전달해도 되고, 바로 NestJS 안에서 실험해도 무방

---

## 5. 15주 스케줄 — 역할별 세분화

기존 신청서의 15주 일정(날짜·예산)은 그대로 두고, **주차별로 3명이 각자 뭘 하는지만 명확히** 나눴습니다. 병렬 작업이 가능하도록 배치한 게 핵심입니다.

| 주차 | 기간 | 김지호(FE) | 김태한(BE) | 박영준(DB&AI) |
| --- | --- | --- | --- | --- |
| 1 | 9.1~9.4 | 경쟁 서비스 UX 조사 | API 엔드포인트 목록 초안 | ERD 초안 |
| 2 | 9.7~9.11 | 화면 목록·플로우 정리 | 기술명세표 작성 | ERD 확정, Prisma 스키마 변환 |
| 3 | 9.14~9.18 | 와이어프레임(Figma) | 프로젝트 스캐폴딩 | 클로바 스피치 API 키 테스트 |
| 4 | 9.21~9.23 | UI 디자인 확정 | 인증(로그인) API 구현 | GPT-4o-mini 프롬프트 프로토타입 |
| 5 | 9.28~10.2 | 로그인·홈 화면 구현 (Mock API) | DB 마이그레이션, 기본 CRUD API | STT 결과 → JSON 변환 실험 |
| 6 | 10.6~10.8 | 목표 입력 화면 (Mock) | 목표 입력 API 스캐폴딩 | STT 정확도 비교(클로바 vs Google) |
| 7 | 10.12~10.16 | Todo 화면 UI | DB/API 구조 완성 | ExecutionLog 스키마 확정 |
| 8 | 10.19~10.23 | STT 버튼 실제 연동 | STT API 통합 | 클로바 연동 마무리, 중간보고서 |
| 9 | 10.26~10.30 | Todo 표시/수정 UI | LLM 구조화 API | 3단계 폴백 로직 구현 |
| 10 | 11.2~11.6 | 계획량 안내 UI(배너 등) | 계획량 안내 API | 14일 집계 알고리즘 구현 |
| 11 | 11.9~11.13 | Todo 관리(완료체크) UI | Todo 상태 API | 알고리즘 튜닝 |
| 12 | 11.16~11.20 | 그룹 선언 화면 | 그룹/선언 API | 인증샷 저장 로직 |
| 13 | 11.23~11.27 | 댓글·랭킹 UI | 랭킹/스트릭 API | 데이터 검증 |
| 14 | 11.30~12.4 | 통합 테스트 (전원) | 통합 테스트 (전원) | 통합 테스트 (전원) |
| 15 | 12.7~12.18 | 개선 반영 | 개선 반영 | 최종보고서 자료 정리 |

**병렬 개발 원칙**: FE는 5주차부터 BE 완성을 기다리지 않고 Mock API로 화면을 먼저 만듭니다. 2주차에 API 계약(엔드포인트·응답 형식)만 확정되면 가능합니다. 이게 안 되면 FE가 8~9주차까지 할 일이 없어지는 병목이 생깁니다.

---

## 6. 지금 당장 할 일 (우선순위 순)

1. GitHub 레포 2개 생성 + 브랜치 전략 세팅
2. Postman에 API 엔드포인트 목록만 먼저 작성 (코드 없이 목록만)
3. dbdiagram.io로 ERD 초안
4. NAVER Cloud Platform 가입 + Clova Speech 서비스 신청 (승인 대기시간 있을 수 있어 최우선)
5. 각자 로컬 환경 셋업 (위 4번 섹션 명령어대로)
6. Docker Desktop 설치 (BE 담당이지만 DB 버전 통일을 위해 팀 전체 설치 권장)

이 순서대로 하면 1주차가 끝나기 전에 세 사람이 각자 독립적으로 개발을 시작할 수 있는 상태가 됩니다.

P2J API 명세서 v1 (초안)

**P2J ERD · DB 스키마 설계서 v1**

P2J 백엔드 명세서 v1

생각한 부분.

무조건 아이콘들이 있어야 함. UI를 보기 좋게 만드려면 아이콘들을 디자인해야 함.

프롬프트 엔지니어링을 조금 배워야 겠음