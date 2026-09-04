> 개척학기제 과제 · P들을 위한 TODO List 공유 어플
작성 기준일: 2026-09-02 / 확정 목표: 2주차(9/7~9/11) 3인 합의
> 

---

## 0. 공통 규약

### 0.1 기본 정보

| 항목 | 값 |
| --- | --- |
| Base URL | `https://api.p2j.dev/v1` (개발: `http://localhost:8000/v1`) |
| 프로토콜 | HTTPS, JSON only |
| 문자 인코딩 | UTF-8 |
| 시간대 | **모든 날짜·시각은 KST(UTC+9) 기준** |
| 날짜 형식 | `YYYY-MM-DD` (예: `2026-09-15`) |
| 시각 형식 | ISO 8601 (예: `2026-09-15T09:00:00+09:00`) |

> **하루의 경계**: 자정이 아니라 **04:00 KST**를 하루의 시작으로 본다. 새벽 1시에 앱을 켠 사용자에게 "오늘"은 어제 날짜여야 하기 때문이다. 서버가 `X-Client-Time` 헤더 또는 서버 시각을 기준으로 `today`를 계산해 내려주며, 클라이언트는 자체 계산하지 않는다.
> 

### 0.2 인증

```
Authorization: Bearer <access_token>
```

- Access Token: JWT, 유효기간 **1시간**
- Refresh Token: 유효기간 **30일**, 재발급 시 회전(rotation)
- 인증 실패 시 `401 UNAUTHORIZED` → 클라이언트는 `/auth/refresh` 1회 시도 후 실패하면 로그인 화면으로 이동

### 0.3 응답 형식

**성공**

```json
{
  "data": { }
}
```

**목록 (커서 페이지네이션)**

```json
{
  "data": [ ],
  "page": {
    "next_cursor": "eyJpZCI6MTIzfQ==",
    "has_next": true
  }
}
```

**실패**

```json
{
  "error": {
    "code": "GOAL_NOT_FOUND",
    "message": "해당 목표를 찾을 수 없습니다.",
    "details": { "goal_id": 42 }
  }
}
```

### 0.4 HTTP 상태 코드

| 코드 | 사용 상황 |
| --- | --- |
| 200 | 조회·수정 성공 |
| 201 | 생성 성공 |
| 204 | 삭제 성공 (본문 없음) |
| 400 | 요청 형식 오류 (`VALIDATION_ERROR`) |
| 401 | 토큰 없음·만료 |
| 403 | 권한 없음 (남의 그룹·남의 투두) |
| 404 | 리소스 없음 |
| 409 | 상태 충돌 (이미 선언함, 이미 가입함) |
| 422 | 비즈니스 규칙 위반 (선언 잠금 후 수정 시도) |
| 429 | AI 호출 한도 초과 |
| 500 | 서버 오류 |
| 503 | LLM 공급자 장애 (`AI_UNAVAILABLE`) |

---

## 1. Auth — 인증

### `POST /auth/signup`

```json
// Request
{
  "email": "a01057799406@gmail.com",
  "password": "********",
  "nickname": "태한"
}
// 201 Response
{
  "data": {
    "user_id": 1,
    "email": "a01057799406@gmail.com",
    "nickname": "태한",
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  }
}
```

오류: `409 EMAIL_ALREADY_EXISTS`, `400 WEAK_PASSWORD`

### `POST /auth/login`

```json
// Request
{ "email": "...", "password": "..." }
```

응답은 signup과 동일. 오류: `401 INVALID_CREDENTIALS`

### `POST /auth/refresh`

```json
// Request
{ "refresh_token": "eyJ..." }
// 200 Response
{ "data": { "access_token": "eyJ...", "refresh_token": "eyJ..." } }
```

### `POST /auth/logout`

`204` — 서버는 해당 refresh token을 폐기한다.

### `GET /auth/me`

```json
{
  "data": {
    "user_id": 1,
    "nickname": "태한",
    "profile_image_url": null,
    "created_at": "2026-09-01T10:00:00+09:00",
    "today": "2026-09-15"
  }
}
```

> `today`를 여기서 함께 내려주면 클라이언트가 앱 진입 시 한 번에 기준 날짜를 확보할 수 있다.
> 

---

## 2. Goal — 목표 (상위 개념)

Goal은 "일주일에 3회 운동, 4주간"처럼 **기간과 빈도를 가진 상위 목표**다.
TodoItem은 그 목표가 특정 날짜에 배치된 **개별 실행 단위**다. 이 분리가 반복 목표 처리의 핵심이다.

### Goal 객체

```json
{
  "goal_id": 12,
  "title": "운동하기",
  "type": "recurring",          // "single" | "recurring"
  "frequency": {                 // type=recurring 일 때만
    "times": 3,
    "per": "week"                // "week" | "month"
  },
  "duration_weeks": 4,
  "start_date": "2026-09-15",
  "end_date": "2026-10-12",
  "estimated_minutes": 60,
  "status": "active",            // "active" | "completed" | "abandoned"
  "progress": {
    "target_count": 12,
    "done_count": 5,
    "achievement_rate": 0.42,
    "current_week_done": 1,
    "current_week_target": 3
  },
  "created_at": "2026-09-15T08:12:00+09:00"
}
```

### `POST /goals`

AI 파싱 결과를 사용자가 확인한 뒤 확정 생성한다.

```json
// Request
{
  "title": "운동하기",
  "type": "recurring",
  "frequency": { "times": 3, "per": "week" },
  "duration_weeks": 4,
  "start_date": "2026-09-15",
  "estimated_minutes": 60,
  "parse_id": "prs_9f2a..."   // AI 파싱 거쳐 온 경우만. 수동 입력이면 null
}
```

> `parse_id`를 함께 저장해 두면 "AI 제안을 사용자가 그대로 수락했는지 / 수정했는지"를 나중에 집계할 수 있다. 최종보고서에 넣을 정확도 지표가 여기서 나온다.
> 

### `GET /goals`

Query: `status` (기본 `active`), `cursor`, `limit` (기본 20)

### `GET /goals/{goal_id}`

### `PATCH /goals/{goal_id}`

수정 가능: `title`, `frequency`, `duration_weeks`, `estimated_minutes`, `status`

> 이미 지난 날짜의 TodoItem은 재생성하지 않는다. 미래 항목만 재배치한다.
> 

### `DELETE /goals/{goal_id}`

`204` — soft delete. 과거 실행 기록은 통계를 위해 보존한다.

---

## 3. Todo — 일별 실행 항목

### TodoItem 객체

```json
{
  "todo_id": 301,
  "goal_id": 12,
  "goal_title": "운동하기",
  "title": "운동하기",
  "date": "2026-09-15",
  "status": "pending",           // "pending" | "done" | "deferred" | "skipped"
  "estimated_minutes": 60,
  "actual_minutes": null,
  "completed_at": null,
  "order": 2,
  "is_declared": false,          // 소셜 그룹에 선언되었는지
  "source": "ai_suggested"       // "ai_suggested" | "manual" | "auto_scheduled"
}
```

### `GET /todos`

Query: `date` (필수, `YYYY-MM-DD`)

```json
{
  "data": {
    "date": "2026-09-15",
    "items": [ /* TodoItem[] */ ],
    "summary": {
      "total": 4,
      "done": 1,
      "achievement_rate": 0.25,
      "total_estimated_minutes": 180
    }
  }
}
```

### `GET /todos/week`

홈 화면 상단의 **7일 캘린더**용. 날짜별 달성률만 가볍게 내려준다.
Query: `start_date` (기본: 오늘 기준 6일 전)

```json
{
  "data": [
    { "date": "2026-09-09", "total": 3, "done": 3, "achievement_rate": 1.0 },
    { "date": "2026-09-10", "total": 4, "done": 2, "achievement_rate": 0.5 }
  ]
}
```

### `POST /todos`

수동 생성 (AI를 거치지 않는 단발 항목).

```json
{ "title": "장보기", "date": "2026-09-15", "estimated_minutes": 30, "goal_id": null }
```

### `PATCH /todos/{todo_id}`

```json
{ "title": "...", "estimated_minutes": 45, "order": 1 }
```

오류: `422 DECLARED_TODO_LOCKED` — 그룹에 선언된 항목은 당일 수정 불가

### `POST /todos/{todo_id}/complete`

```json
// Request
{ "actual_minutes": 55 }
// 200 Response — 완료 시 갱신된 스트릭·목표 진행률을 함께 반환
{
  "data": {
    "todo": { /* TodoItem */ },
    "goal_progress": { "done_count": 6, "current_week_done": 2 },
    "personal_streak": 7
  }
}
```

### `POST /todos/{todo_id}/uncomplete`

완료 취소. `204`

### `POST /todos/{todo_id}/defer`

```json
{ "to_date": "2026-09-16" }
```

계획량 안내에서 "내일로 옮길까요?"를 사용자가 수락했을 때 호출한다.

### `DELETE /todos/{todo_id}`

### `GET /todos/suggestions`

> **핵심 기능**: 앱을 켤 때마다 호출. 진행 중인 반복 목표 중 페이스가 부족한 것을 오늘 할 일로 제안한다.
> 

Query: `date` (기본 오늘)

```json
{
  "data": [
    {
      "goal_id": 12,
      "title": "운동하기",
      "reason": "이번 주 3회 중 1회 완료. 남은 3일 동안 2회가 필요합니다.",
      "pace": { "week_done": 1, "week_target": 3, "days_left": 3 },
      "suggested_estimated_minutes": 60
    }
  ]
}
```

- 판정은 **규칙 기반**으로 처리한다(LLM 호출 없음). 남은 기간 대비 남은 횟수로 필요 페이스를 계산.
- 사용자가 수락하면 `POST /todos`로 `goal_id`를 지정해 생성한다.
- 거절 시 `POST /goals/{goal_id}/dismiss-suggestion` — 당일 재제안하지 않는다.

---

## 4. AI — 파싱 및 계획량 안내

### `POST /ai/parse`

> 비정형 음성·텍스트 입력 → 구조화된 Goal 초안. **저장하지 않고 초안만 반환**하며, 사용자 확인 후 `POST /goals`로 확정한다.
> 

```json
// Request
{
  "text": "일주일에 세 번 운동하고 한 달 정도 해볼래",
  "source": "stt",            // "stt" | "text"
  "stt_confidence": 0.87       // source=stt 일 때 클라이언트가 전달
}
```

```json
// 200 Response — 정상
{
  "data": {
    "parse_id": "prs_9f2a3b",
    "status": "ok",              // "ok" | "partial" | "fallback"
    "raw_text": "일주일에 세 번 운동하고 한 달 정도 해볼래",
    "drafts": [
      {
        "title": "운동하기",
        "type": "recurring",
        "frequency": { "times": 3, "per": "week" },
        "duration_weeks": 4,
        "estimated_minutes": 60,
        "confidence": 0.91,
        "uncertain_fields": []
      }
    ],
    "confirm_message": "일주일에 3회씩 4주간 운동하기로 등록할까요?"
  }
}
```

**3단계 대비책 (신청서 명시 사항)**

| 단계 | 처리 | 응답 |
| --- | --- | --- |
| 1 | JSON 스키마 강제 출력 (structured output) | `status: "ok"` |
| 2 | 스키마 위반 시 1회 재시도 → 실패하면 규칙 기반 파서 | `status: "partial"`, `uncertain_fields`에 미확정 필드 명시 |
| 3 | 규칙 파서도 실패 | `status: "fallback"`, `drafts`에 제목만 채운 항목 1개 + 사용자 직접 입력 유도 |

```json
// status: "partial" 예시 — 기간을 못 뽑은 경우
{
  "data": {
    "parse_id": "prs_7c1d",
    "status": "partial",
    "drafts": [{
      "title": "운동하기",
      "type": "recurring",
      "frequency": { "times": 3, "per": "week" },
      "duration_weeks": null,
      "confidence": 0.62,
      "uncertain_fields": ["duration_weeks"]
    }],
    "confirm_message": "얼마 동안 이어갈지 알려주세요."
  }
}
```

오류: `429 AI_RATE_LIMITED`, `503 AI_UNAVAILABLE` (→ 클라이언트는 수동 입력 화면으로 전환)

### `POST /ai/parse/{parse_id}/feedback`

```json
{ "accepted": true, "modified_fields": ["duration_weeks"] }
```

> 수락률·수정 필드 분포가 곧 AI 정확도 지표가 된다. 중간·최종보고서 근거 데이터.
> 

### `GET /ai/load-check`

> **계획량 안내 기능.** 오늘 계획이 평소 소화량을 넘는지 판정한다.
> 

Query: `date` (기본 오늘)

```json
{
  "data": {
    "check_id": "chk_4a8f",
    "level": "warning",          // "ok" | "warning"
    "message": "지난 2주간 한 시간 이상 걸리는 일을 두 개 넘게 끝낸 날은 이틀뿐이었습니다. 오늘 세 개는 부담일 수 있습니다.",
    "evidence": {
      "window_days": 14,
      "heavy_task_threshold_minutes": 60,
      "days_with_3plus_heavy": 2,
      "avg_completed_minutes_per_day": 95,
      "today_planned_minutes": 210
    },
    "suggestions": [
      { "todo_id": 305, "action": "defer", "to_date": "2026-09-16", "reason": "가장 늦게 추가된 항목" }
    ]
  }
}
```

- 판정은 **집계 쿼리 기반**. LLM은 안내 문구를 다듬는 용도로만 선택적으로 사용하고, 실패해도 템플릿 문구로 대체한다.
- 실행 기록이 7일 미만이면 `level: "ok"`, `message: null`로 반환한다(근거 부족).

### `POST /ai/load-check/{check_id}/response`

```json
{ "accepted": true, "applied_todo_ids": [305] }
```

> 신청서의 "사용자가 이를 받아들였는지 여부도 다시 기록으로 쌓여 다음 판단에 반영된다"에 해당한다.
> 

---

## 5. Stats — 통계

### `GET /stats/summary`

Query: `period` = `week` | `month` (기본 `week`)

```json
{
  "data": {
    "period": "week",
    "range": { "from": "2026-09-09", "to": "2026-09-15" },
    "achievement_rate": 0.68,
    "total_todos": 25,
    "completed_todos": 17,
    "total_actual_minutes": 640,
    "current_streak": 7,
    "longest_streak": 12,
    "by_day": [
      { "date": "2026-09-09", "achievement_rate": 1.0 }
    ],
    "by_hour": [
      { "hour": 9, "completed": 6 },
      { "hour": 22, "completed": 2 }
    ],
    "most_deferred": [
      { "goal_id": 15, "title": "논문 읽기", "defer_count": 5 }
    ]
  }
}
```

### `GET /stats/goals/{goal_id}`

개별 목표의 기간별 달성 추이.

---

## 6. Social — 그룹·선언·인증

### 6.1 그룹

#### `POST /groups`

```json
{ "name": "3학년 개발조", "max_members": 6 }
```

```json
// 201
{
  "data": {
    "group_id": 7,
    "name": "3학년 개발조",
    "owner_id": 1,
    "member_count": 1,
    "max_members": 6,
    "invite_code": "P2J-K3M9",
    "group_streak": 0,
    "created_at": "..."
  }
}
```

> 신청서 기준 그룹은 **3~6명**. `max_members` 기본값 6, 상한 6으로 서버에서 강제한다.
> 

#### `GET /groups`

내가 속한 그룹 목록. 카카오톡 방 목록 형태의 화면에 대응하며, 각 항목에 `unread_count`와 `last_activity_at`을 포함한다.

#### `GET /groups/{group_id}`

#### `POST /groups/{group_id}/invite`

새 초대 코드 발급. `{ "invite_code": "P2J-K3M9", "expires_at": "..." }` (유효기간 7일)

#### `POST /groups/join`

```json
{ "invite_code": "P2J-K3M9" }
```

오류: `409 ALREADY_MEMBER`, `422 GROUP_FULL`, `404 INVALID_INVITE_CODE`

#### `GET /groups/{group_id}/members`

```json
{
  "data": [
    {
      "user_id": 2,
      "nickname": "지호",
      "profile_image_url": null,
      "role": "member",
      "today_declared": true,
      "today_achievement_rate": 0.5,
      "streak": 4
    }
  ]
}
```

#### `DELETE /groups/{group_id}/members/me`

그룹 탈퇴. `204`

### 6.2 선언 (아침)

#### `POST /groups/{group_id}/declarations`

```json
// Request
{ "date": "2026-09-15", "todo_ids": [301, 302, 303] }
// 201 Response
{
  "data": {
    "declaration_id": 88,
    "date": "2026-09-15",
    "locked_at": "2026-09-15T08:30:00+09:00",
    "items": [
      { "declaration_item_id": 401, "todo_id": 301, "title": "운동하기", "status": "pending", "proof": null }
    ]
  }
}
```

- **선언 즉시 잠긴다.** 이후 해당 날짜의 선언은 수정·삭제 불가 → `422 DECLARATION_LOCKED`
- 하루 한 번만 가능 → `409 ALREADY_DECLARED`
- 선언에 포함된 TodoItem은 `is_declared: true`가 되며 제목·삭제가 잠긴다(완료 체크는 가능).

#### `GET /groups/{group_id}/declarations`

Query: `date`

```json
{
  "data": [
    {
      "user": { "user_id": 2, "nickname": "지호" },
      "declaration_id": 88,
      "items": [ /* ... */ ],
      "achievement_rate": 0.33
    }
  ]
}
```

> 미선언 멤버도 `declaration_id: null`로 함께 내려준다. "아직 선언 안 한 사람"이 보이는 것 자체가 압력 장치다.
> 

### 6.3 인증 (저녁)

#### `POST /uploads/presign`

```json
// Request
{ "content_type": "image/jpeg", "purpose": "proof" }
// 200 Response
{
  "data": {
    "upload_url": "https://storage.../presigned...",
    "file_key": "proofs/2026/09/15/uuid.jpg",
    "expires_at": "2026-09-15T20:10:00+09:00"
  }
}
```

> 이미지는 서버를 거치지 않고 클라이언트가 스토리지에 직접 업로드한 뒤, `file_key`만 API로 전달한다. 서버 트래픽과 메모리 부담을 줄이기 위함.
> 

#### `POST /groups/{group_id}/proofs`

```json
{ "declaration_item_id": 401, "file_key": "proofs/.../uuid.jpg", "caption": "헬스장 다녀옴" }
```

```json
// 201
{
  "data": {
    "post_id": 512,
    "declaration_item_id": 401,
    "image_url": "https://cdn.../uuid.jpg",
    "caption": "헬스장 다녀옴",
    "created_at": "...",
    "comment_count": 0,
    "reactions": {}
  }
}
```

오류: `403` (남의 선언), `422 PROOF_ALREADY_EXISTS`

#### `GET /groups/{group_id}/feed`

Query: `date` (선택), `cursor`, `limit` (기본 20)
스토리형 UI에 맞춰 **사용자별로 묶어서** 반환한다.

```json
{
  "data": [
    {
      "user": { "user_id": 2, "nickname": "지호" },
      "date": "2026-09-15",
      "declared_count": 3,
      "done_count": 2,
      "posts": [ /* proof 객체[] */ ],
      "missed_items": [ { "title": "논문 읽기", "status": "pending" } ]
    }
  ],
  "page": { "next_cursor": "...", "has_next": true }
}
```

> `missed_items`를 반드시 함께 내려준다. **미달성도 그대로 드러나는 것이 이 앱의 차별점**이므로 API에서부터 숨기지 않는다.
> 

### 6.4 댓글·리액션

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `POST` | `/posts/{post_id}/comments` | `{ "content": "고생했다" }` |
| `GET` | `/posts/{post_id}/comments` | 커서 페이지네이션 |
| `DELETE` | `/comments/{comment_id}` | 작성자 본인만 |
| `PUT` | `/posts/{post_id}/reactions` | `{ "type": "fire" }` — 사용자당 1개, 재호출 시 교체 |
| `DELETE` | `/posts/{post_id}/reactions` | 리액션 취소 |

리액션 타입: `fire`, `clap`, `heart`, `muscle` (서버 화이트리스트로 제한)

### 6.5 랭킹·스트릭

#### `GET /groups/{group_id}/ranking`

Query: `period` = `week` | `month` | `all`

```json
{
  "data": {
    "period": "week",
    "range": { "from": "2026-09-14", "to": "2026-09-20" },
    "rankings": [
      { "rank": 1, "user_id": 2, "nickname": "지호", "achievement_rate": 0.92, "declared_days": 6, "streak": 11 }
    ],
    "my_rank": 3
  }
}
```

#### `GET /groups/{group_id}/streak`

```json
{
  "data": {
    "group_streak": 5,
    "last_success_date": "2026-09-14",
    "today_status": "in_progress",   // "in_progress" | "success" | "broken"
    "members_completed_today": 4,
    "members_total": 6
  }
}
```

> 그룹 스트릭 규칙: **선언한 멤버 전원이 선언 항목을 100% 완료한 날**만 +1. 미선언 멤버는 계산에서 제외하되 `members_total`에는 포함해 화면에 표시한다.
> 

---

## 7. 오류 코드 표

| 코드 | HTTP | 설명 |
| --- | --- | --- |
| `VALIDATION_ERROR` | 400 | 필드 형식·필수값 오류 |
| `INVALID_CREDENTIALS` | 401 | 로그인 실패 |
| `TOKEN_EXPIRED` | 401 | Access token 만료 |
| `EMAIL_ALREADY_EXISTS` | 409 | 중복 가입 |
| `GOAL_NOT_FOUND` | 404 |  |
| `TODO_NOT_FOUND` | 404 |  |
| `DECLARED_TODO_LOCKED` | 422 | 선언된 투두 수정 시도 |
| `DECLARATION_LOCKED` | 422 | 선언 수정·삭제 시도 |
| `ALREADY_DECLARED` | 409 | 당일 중복 선언 |
| `PROOF_ALREADY_EXISTS` | 422 | 중복 인증 |
| `GROUP_FULL` | 422 | 정원 초과 |
| `ALREADY_MEMBER` | 409 |  |
| `INVALID_INVITE_CODE` | 404 | 없거나 만료된 코드 |
| `AI_RATE_LIMITED` | 429 | 일일 AI 호출 한도 초과 |
| `AI_UNAVAILABLE` | 503 | LLM 공급자 장애 |

---

## 8. 구현 순서 (추진일정 대응)

| 주차 | 담당 | 구현 대상 |
| --- | --- | --- |
| 4주 | 태한 | `/auth/*` 전체 |
| 5주 | 태한 | `/goals` CRUD, `/auth/me` |
| 6주 | 태한 | `/todos` CRUD, `/todos/week` |
| 6주 | 영준 | `/ai/parse` (스키마 강제 v1) |
| 7주 | 태한 | `/uploads/presign` |
| 7주 | 영준 | `/todos/suggestions` (반복목표 배치 규칙) |
| 8~9주 | 영준 | `/ai/parse` 재시도·폴백, `/ai/parse/{id}/feedback` |
| 10주 | 영준 | `/ai/load-check`, `/ai/load-check/{id}/response` |
| 11주 | 태한 | `/todos/{id}/complete`, `/defer`, `/stats/summary` |
| 12주 | 태한 | `/groups/*`, `/declarations`, `/proofs`, `/feed` |
| 13주 | 태한 | `/comments`, `/reactions`, `/ranking`, `/streak` |

---

## 9. 합의가 필요한 미결 사항

2주차 회의에서 아래 항목을 결정하고 이 문서를 v1.1로 갱신한다.

1. **소셜 갱신 방식** — 폴링(진입 시 + 당겨서 새로고침)으로 시작할지, 처음부터 WebSocket을 붙일지. 주 8시간 기준으로는 폴링 권장.
2. **하루 경계 04:00** — 규칙을 확정할지, 사용자 설정으로 뺄지.
3. **AI 호출 한도** — 사용자당 1일 몇 회로 제한할지. 
4. **선언 마감 시각** — 아침 선언에 마감 시각(예: 11시)을 둘지, 하루 중 아무 때나 허용할지.
5. **미선언 멤버의 랭킹 처리** — 0%로 집계할지, 제외할지.
6. **인증샷 보관 기간** — 스토리지 비용과 직결. 30일 후 자동 삭제 여부.