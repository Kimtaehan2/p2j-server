/**
 * 서비스 날짜(하루 경계) 계산.
 *
 * P2J 의 하루는 자정이 아니라 04:00 KST 에 바뀐다. 새벽 3시에 할 일을 끝내면
 * 그것은 "어제"의 성과다. 날짜를 다루는 모든 코드는 이 파일의 함수만 사용한다.
 *
 * 서버 로컬 timezone 에 의존하지 않는다. Railway 컨테이너는 UTC 로 뜨고
 * 개발자 PC 는 KST 라서, Date 의 로컬 getter 를 쓰면 두 환경의 결과가 갈린다.
 */

/** KST 는 UTC+09:00 고정이다. 한국은 서머타임을 쓰지 않는다. */
const KST_OFFSET_MINUTES = 9 * 60;

const MS_PER_MINUTE = 60_000;

/** 하루 경계 기본값. 환경변수 SERVICE_DAY_START_HOUR 로 덮어쓸 수 있다. */
export const DEFAULT_SERVICE_DAY_START_HOUR = 4;

function assertValidStartHour(dayStartHour: number): void {
  if (
    !Number.isInteger(dayStartHour) ||
    dayStartHour < 0 ||
    dayStartHour > 23
  ) {
    throw new RangeError(
      `dayStartHour 는 0 이상 23 이하의 정수여야 합니다. 받은 값: ${dayStartHour}`,
    );
  }
}

/** UTC getter 만 사용해 YYYY-MM-DD 로 만든다. */
function formatDate(date: Date): string {
  const year = String(date.getUTCFullYear()).padStart(4, '0');
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * 주어진 시각 기준으로 "서비스상 오늘" 날짜를 YYYY-MM-DD 로 반환한다.
 *
 * @param now 판정할 시각. 절대 시각(epoch)만 사용하므로 어떤 방식으로 만든
 *            Date 든 결과가 같다.
 * @param dayStartHour 하루가 시작되는 KST 기준 시각. 기본 4.
 */
export function getServiceDay(
  now: Date,
  dayStartHour: number = DEFAULT_SERVICE_DAY_START_HOUR,
): string {
  assertValidStartHour(dayStartHour);

  // epoch 를 KST 로 밀어 놓고, 이후에는 UTC getter 로만 읽는다.
  const kst = new Date(now.getTime() + KST_OFFSET_MINUTES * MS_PER_MINUTE);

  if (kst.getUTCHours() < dayStartHour) {
    kst.setUTCDate(kst.getUTCDate() - 1);
  }

  return formatDate(kst);
}

/**
 * 서비스 날짜가 시작되는 절대 시각을 반환한다.
 * 예) 2026-09-04, dayStartHour=4 이면 2026-09-03T19:00:00Z (= 09-04 04:00 KST).
 */
export function getServiceDayStart(
  serviceDay: string,
  dayStartHour: number = DEFAULT_SERVICE_DAY_START_HOUR,
): Date {
  assertValidStartHour(dayStartHour);

  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(serviceDay);
  if (match === null) {
    throw new RangeError(
      `serviceDay 는 YYYY-MM-DD 형식이어야 합니다. 받은 값: ${serviceDay}`,
    );
  }

  const [, year, month, day] = match;
  const kstMidnight = Date.UTC(Number(year), Number(month) - 1, Number(day));
  return new Date(
    kstMidnight + (dayStartHour * 60 - KST_OFFSET_MINUTES) * MS_PER_MINUTE,
  );
}
