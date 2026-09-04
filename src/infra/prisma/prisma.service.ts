import {
  Injectable,
  Logger,
  type OnModuleDestroy,
  type OnModuleInit,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaPg } from '@prisma/adapter-pg';
import { PrismaClient } from '../../generated/prisma/client.js';

/**
 * Prisma 7 은 Rust query engine 대신 driver adapter 를 사용한다.
 * 접속 URL 은 schema.prisma 가 아니라 여기(런타임)와 prisma.config.ts(Migrate)에서 지정한다.
 */
@Injectable()
export class PrismaService
  extends PrismaClient
  implements OnModuleInit, OnModuleDestroy
{
  private readonly logger = new Logger(PrismaService.name);

  constructor(config: ConfigService) {
    super({
      adapter: new PrismaPg({
        connectionString: config.getOrThrow<string>('DATABASE_URL'),
      }),
    });
  }

  async onModuleInit(): Promise<void> {
    try {
      await this.$connect();
      // driver adapter 의 $connect 는 지연 연결이라 접속 성공을 보장하지 않는다.
      // 실제 도달 여부는 /v1/health 의 SELECT 1 이 판정한다.
      this.logger.log('PostgreSQL 클라이언트를 준비했습니다.');
    } catch (error) {
      // 여기서 죽이면 /v1/health 가 원인을 알려줄 기회조차 없어진다.
      // 접속 정보가 새지 않도록 오류 종류만 남긴다.
      this.logger.warn(
        `PostgreSQL 초기 연결에 실패했습니다. (${errorName(error)}) 요청 시 재시도합니다.`,
      );
    }
  }

  async onModuleDestroy(): Promise<void> {
    await this.$disconnect();
  }

  /** 실제로 질의가 가능한지 확인한다. */
  async ping(): Promise<void> {
    await this.$queryRaw`SELECT 1`;
  }
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : 'UnknownError';
}
