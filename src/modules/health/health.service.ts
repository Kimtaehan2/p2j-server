import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../infra/prisma/prisma.service.js';
import { RedisService } from '../../infra/redis/redis.service.js';

export type DependencyStatus = 'up' | 'down';

export interface HealthResult {
  status: 'ok' | 'degraded';
  postgres: DependencyStatus;
  redis: DependencyStatus;
}

/**
 * 실제 연결을 확인한다. 의존 서비스가 내려가 있으면 성공으로 가장하지 않는다.
 */
@Injectable()
export class HealthService {
  private readonly logger = new Logger(HealthService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly redis: RedisService,
  ) {}

  async check(): Promise<HealthResult> {
    const [postgres, redis] = await Promise.all([
      this.checkPostgres(),
      this.checkRedis(),
    ]);

    return {
      status: postgres === 'up' && redis === 'up' ? 'ok' : 'degraded',
      postgres,
      redis,
    };
  }

  private async checkPostgres(): Promise<DependencyStatus> {
    try {
      await this.prisma.ping();
      return 'up';
    } catch (error) {
      this.logger.warn(`PostgreSQL health check 실패 (${errorName(error)})`);
      return 'down';
    }
  }

  private async checkRedis(): Promise<DependencyStatus> {
    try {
      const pong = await this.redis.ping();
      return pong === 'PONG' ? 'up' : 'down';
    } catch (error) {
      this.logger.warn(`Redis health check 실패 (${errorName(error)})`);
      return 'down';
    }
  }
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : 'UnknownError';
}
