import {
  Injectable,
  Logger,
  type OnModuleDestroy,
  type OnModuleInit,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Redis } from 'ioredis';

/**
 * 프로젝트에서 사용하는 유일한 Redis 클라이언트다.
 * 다른 Redis 라이브러리를 함께 쓰지 않는다.
 *
 * 접속 URL 에는 비밀번호가 포함될 수 있으므로 로그에 남기지 않는다.
 */
@Injectable()
export class RedisService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  private readonly client: Redis;

  constructor(config: ConfigService) {
    this.client = new Redis(config.getOrThrow<string>('REDIS_URL'), {
      lazyConnect: true,
      maxRetriesPerRequest: 1,
      // 연결이 없을 때 명령을 쌓아 두지 않고 즉시 실패시킨다.
      // health check 가 "응답 없음"으로 매달리는 것을 막는다.
      enableOfflineQueue: false,
    });

    // 재연결 시도 중 오류가 unhandled 로 터지지 않도록 받아 둔다.
    this.client.on('error', (error: Error) => {
      this.logger.debug(`Redis 오류: ${error.name}`);
    });
  }

  async onModuleInit(): Promise<void> {
    try {
      await this.client.connect();
      this.logger.log('Redis 에 연결했습니다.');
    } catch (error) {
      this.logger.warn(
        `Redis 초기 연결에 실패했습니다. (${errorName(error)}) 이후 자동으로 재시도합니다.`,
      );
    }
  }

  async onModuleDestroy(): Promise<void> {
    try {
      await this.client.quit();
    } catch {
      this.client.disconnect();
    }
  }

  /** 연결 상태를 확인한다. 정상이면 'PONG'. */
  async ping(): Promise<string> {
    return this.client.ping();
  }
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : 'UnknownError';
}
