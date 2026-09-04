## 무엇을 바꿨나

<!-- 한두 문장. "왜"가 제목에서 안 보이면 여기에 적는다. -->

## 관련

- 이슈:
- 연결된 `p2j-mobile` PR: <!-- API 계약이 바뀌면 반드시 링크 -->

## 확인한 것

- [ ] `npm run format:check`
- [ ] `npm run lint`
- [ ] `npm test`
- [ ] `npm run build`
- [ ] 직접 실행해서 동작 확인 (엔드포인트 / 명령 적기)

## API 계약을 바꿨다면

- [ ] `docs/specs/02-api-v1.md` 를 갱신했다
- [ ] 요청·응답 예시를 PR 본문이나 문서에 남겼다
- [ ] 김지호(모바일) 리뷰를 요청했다
- [ ] 이전 계약을 아직 지우지 않았다 (모바일 전환 후에 지운다)

## DB 를 바꿨다면

- [ ] `migrate dev --create-only` 로 SQL 을 먼저 검토했다
- [ ] Prisma 가 표현하지 못하는 CHECK / partial index 를 `migration.sql` 에 넣었다
- [ ] 김태한 · 박영준 두 명의 리뷰를 요청했다

## 남은 일 / 알고 있는 문제

<!-- 없으면 "없음" -->
