import type { INestApplication } from '@nestjs/common';
import { Test, type TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { AppModule } from '../src/app.module.js';
import { configureApp } from '../src/main.js';

/**
 * PostgreSQL 과 Redis 가 실제로 떠 있어야 통과한다.
 *   docker compose up -d
 * 그 다음 npm run test:e2e
 */
describe('Health (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleRef: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleRef.createNestApplication();
    // configureApp 이 app.init() 까지 수행한다.
    await configureApp(app);
  });

  afterAll(async () => {
    await app.close();
  });

  it('GET /v1/health 는 { data } 로 감싼 정상 상태를 반환한다', async () => {
    const response = await request(app.getHttpServer()).get('/v1/health');

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      data: { status: 'ok', postgres: 'up', redis: 'up' },
    });
  });

  it('없는 경로는 { error } 형식으로 응답한다', async () => {
    const response = await request(app.getHttpServer()).get('/v1/no-such-path');

    expect(response.status).toBe(404);
    expect(response.body.error.code).toBe('NOT_FOUND');
    expect(response.body.data).toBeUndefined();
  });

  it('GET /v1/docs-json 은 OpenAPI 문서를 감싸지 않고 그대로 반환한다', async () => {
    const response = await request(app.getHttpServer()).get('/v1/docs-json');

    expect(response.status).toBe(200);
    expect(response.body.openapi).toBeDefined();
    expect(response.body.paths['/v1/health']).toBeDefined();
  });
});
