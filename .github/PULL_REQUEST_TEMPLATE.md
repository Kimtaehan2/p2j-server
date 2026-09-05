## 무엇을 바꿨나

<!-- 한두 문장. "왜"가 제목에서 안 보이면 여기에 적는다. -->

## 관련

- 이슈:
- 연결된 `p2j-mobile` PR: <!-- API 계약이 바뀌면 반드시 링크 -->

## 확인한 것

- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy app`
- [ ] `uv run pytest`
- [ ] 직접 실행해서 동작 확인 (엔드포인트 / 명령 적기)

## API 계약을 바꿨다면

- [ ] `docs/specs/02-api-v1.md` 를 갱신했다
- [ ] 새 오류 코드를 `ERROR_CATALOG` 와 명세 §1.4 표에 넣었다
- [ ] 요청·응답 예시를 PR 본문이나 문서에 남겼다
- [ ] 김지호(모바일) 리뷰를 요청했다
- [ ] 이전 계약을 아직 지우지 않았다 (모바일 전환 후에 지운다)

## DB 를 바꿨다면

- [ ] `alembic revision --autogenerate` 결과를 **눈으로 읽고** 고쳤다
- [ ] autogenerate 가 놓치는 CHECK / partial index 를 마이그레이션에 직접 넣었다
- [ ] `alembic upgrade head` → `alembic check` 가 통과한다
- [ ] 김태한 · 박영준 두 명의 리뷰를 요청했다

## 남은 일 / 알고 있는 문제

<!-- 없으면 "없음" -->
