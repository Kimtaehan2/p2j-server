import { existsSync } from 'node:fs';
import path from 'node:path';
import { defineConfig, env } from 'prisma/config';

// Prisma 7 CLI 는 .env 를 자동으로 읽지 않는다.
// Node 24 내장 loadEnvFile 로 로컬 개발용 .env 만 읽는다. (.env 는 커밋 대상이 아니다)
if (existsSync('.env')) {
  process.loadEnvFile('.env');
}

export default defineConfig({
  schema: path.join('prisma', 'schema.prisma'),
  migrations: {
    path: path.join('prisma', 'migrations'),
  },
  datasource: {
    url: env('DATABASE_URL'),
  },
});
