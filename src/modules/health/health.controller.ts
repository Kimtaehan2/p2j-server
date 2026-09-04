import { Controller, Get, HttpStatus } from '@nestjs/common';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { AppException } from '../../common/exceptions/app.exception.js';
import { HealthService, type HealthResult } from './health.service.js';

@ApiTags('health')
@Controller('health')
export class HealthController {
  constructor(private readonly health: HealthService) {}

  @Get()
  @ApiOperation({
    summary: '서버·PostgreSQL·Redis 연결 상태 확인',
    description:
      'Railway 가 재시작 판단에 사용한다. 의존 서비스가 하나라도 내려가 있으면 503 을 반환한다.',
  })
  @ApiResponse({
    status: HttpStatus.OK,
    description: '모든 의존 서비스 정상',
    schema: {
      example: {
        data: { status: 'ok', postgres: 'up', redis: 'up' },
      },
    },
  })
  @ApiResponse({
    status: HttpStatus.SERVICE_UNAVAILABLE,
    description: '의존 서비스 연결 실패',
    schema: {
      example: {
        error: {
          code: 'HEALTH_CHECK_FAILED',
          message: '일부 의존 서비스에 연결할 수 없습니다.',
          details: { postgres: 'up', redis: 'down' },
        },
      },
    },
  })
  async check(): Promise<HealthResult> {
    const result = await this.health.check();

    if (result.status !== 'ok') {
      throw new AppException(
        'HEALTH_CHECK_FAILED',
        HttpStatus.SERVICE_UNAVAILABLE,
        '일부 의존 서비스에 연결할 수 없습니다.',
        { postgres: result.postgres, redis: result.redis },
      );
    }

    return result;
  }
}
