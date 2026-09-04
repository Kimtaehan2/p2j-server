import { afterAll, describe, expect, it } from 'vitest';
import {
  DEFAULT_SERVICE_DAY_START_HOUR,
  getServiceDay,
  getServiceDayStart,
} from './service-day.js';

/** KST 벽시계 시각을 절대 시각(Date)으로 만든다. 로컬 timezone 을 타지 않는다. */
function kst(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute = 0,
): Date {
  return new Date(Date.UTC(year, month - 1, day, hour - 9, minute));
}

describe('getServiceDay', () => {
  it('기본 하루 경계는 04:00 이다', () => {
    expect(DEFAULT_SERVICE_DAY_START_HOUR).toBe(4);
  });

  it('KST 03:59 는 전날로 계산한다', () => {
    expect(getServiceDay(kst(2026, 9, 4, 3, 59))).toBe('2026-09-03');
  });

  it('KST 04:00 은 당일로 계산한다', () => {
    expect(getServiceDay(kst(2026, 9, 4, 4, 0))).toBe('2026-09-04');
  });

  it('KST 00:00 은 전날로 계산한다', () => {
    expect(getServiceDay(kst(2026, 9, 4, 0, 0))).toBe('2026-09-03');
  });

  it('KST 23:59 는 당일로 계산한다', () => {
    expect(getServiceDay(kst(2026, 9, 4, 23, 59))).toBe('2026-09-04');
  });

  it('월말 경계를 넘긴다 (10-01 03:00 KST 는 9월 30일)', () => {
    expect(getServiceDay(kst(2026, 10, 1, 3, 0))).toBe('2026-09-30');
  });

  it('윤년 2월 경계를 넘긴다 (03-01 03:00 KST 는 2월 29일)', () => {
    expect(getServiceDay(kst(2028, 3, 1, 3, 0))).toBe('2028-02-29');
  });

  it('연말 경계를 넘긴다 (01-01 03:00 KST 는 전년 12월 31일)', () => {
    expect(getServiceDay(kst(2027, 1, 1, 3, 0))).toBe('2026-12-31');
  });

  it('연말 경계 직후는 당일이다 (01-01 04:00 KST)', () => {
    expect(getServiceDay(kst(2027, 1, 1, 4, 0))).toBe('2027-01-01');
  });

  it('dayStartHour 를 0 으로 주면 자정 경계로 동작한다', () => {
    expect(getServiceDay(kst(2026, 9, 4, 3, 59), 0)).toBe('2026-09-04');
  });

  it('dayStartHour 가 범위를 벗어나면 예외를 던진다', () => {
    expect(() => getServiceDay(new Date(0), 24)).toThrow(RangeError);
    expect(() => getServiceDay(new Date(0), -1)).toThrow(RangeError);
    expect(() => getServiceDay(new Date(0), 4.5)).toThrow(RangeError);
  });
});

describe('getServiceDay - 서버 timezone 비의존', () => {
  const originalTz = process.env.TZ;

  afterAll(() => {
    process.env.TZ = originalTz;
  });

  it('TZ 를 바꿔도 같은 절대 시각이면 같은 결과가 나온다', () => {
    const instant = kst(2026, 9, 4, 3, 59);
    const results = [
      'UTC',
      'Asia/Seoul',
      'America/New_York',
      'Pacific/Kiritimati',
    ].map((zone) => {
      process.env.TZ = zone;
      return getServiceDay(instant);
    });

    expect(new Set(results).size).toBe(1);
    expect(results[0]).toBe('2026-09-03');
  });

  it('같은 시각을 어떤 방식으로 만들어도 결과가 같다', () => {
    const fromEpoch = new Date(Date.UTC(2026, 8, 3, 18, 59));
    const fromIsoUtc = new Date('2026-09-03T18:59:00.000Z');
    const fromIsoKst = new Date('2026-09-04T03:59:00.000+09:00');

    expect(getServiceDay(fromEpoch)).toBe('2026-09-03');
    expect(getServiceDay(fromIsoUtc)).toBe('2026-09-03');
    expect(getServiceDay(fromIsoKst)).toBe('2026-09-03');
  });
});

describe('getServiceDayStart', () => {
  it('서비스 날짜의 시작 절대 시각을 반환한다', () => {
    expect(getServiceDayStart('2026-09-04').toISOString()).toBe(
      '2026-09-03T19:00:00.000Z',
    );
  });

  it('시작 시각은 그 날짜로 되돌아온다', () => {
    const start = getServiceDayStart('2026-09-04');
    expect(getServiceDay(start)).toBe('2026-09-04');
    expect(getServiceDay(new Date(start.getTime() - 1))).toBe('2026-09-03');
  });

  it('형식이 어긋나면 예외를 던진다', () => {
    expect(() => getServiceDayStart('2026-9-4')).toThrow(RangeError);
  });
});
