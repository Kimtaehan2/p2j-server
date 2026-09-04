import {
  type ArgumentsHost,
  Catch,
  type ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { AppException } from '../exceptions/app.exception.js';

/** API 명세 v1 의 오류 응답 형태. */
export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

/** 도메인 코드가 없는 HTTP 오류에 사용할 기본 코드. */
const DEFAULT_CODE_BY_STATUS: Record<number, string> = {
  [HttpStatus.BAD_REQUEST]: 'VALIDATION_ERROR',
  [HttpStatus.UNAUTHORIZED]: 'UNAUTHORIZED',
  [HttpStatus.FORBIDDEN]: 'FORBIDDEN',
  [HttpStatus.NOT_FOUND]: 'NOT_FOUND',
  [HttpStatus.CONFLICT]: 'CONFLICT',
  [HttpStatus.UNPROCESSABLE_ENTITY]: 'UNPROCESSABLE_ENTITY',
  [HttpStatus.TOO_MANY_REQUESTS]: 'TOO_MANY_REQUESTS',
  [HttpStatus.SERVICE_UNAVAILABLE]: 'SERVICE_UNAVAILABLE',
};

const INTERNAL_ERROR_MESSAGE = '서버 오류가 발생했습니다.';

/**
 * 모든 예외를 단일 형식으로 변환한다.
 *
 * 예상하지 못한 오류의 stack, 환경변수, DB URL, 토큰은 클라이언트 응답에 넣지 않는다.
 * 원인 추적에 필요한 내용은 서버 로그에만 남긴다.
 */
@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const http = host.switchToHttp();
    const response = http.getResponse<Response>();

    const { status, body } = this.toErrorResponse(exception);

    if (status >= HttpStatus.INTERNAL_SERVER_ERROR) {
      this.logger.error(
        `처리되지 않은 오류 (${body.error.code})`,
        exception instanceof Error ? exception.stack : undefined,
      );
    }

    response.status(status).json(body);
  }

  private toErrorResponse(exception: unknown): {
    status: number;
    body: ErrorResponse;
  } {
    if (exception instanceof AppException) {
      return {
        status: exception.getStatus(),
        body: {
          error: {
            code: exception.code,
            message: exception.message,
            details: exception.details,
          },
        },
      };
    }

    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      const payload = exception.getResponse();
      const message =
        typeof payload === 'string'
          ? payload
          : this.pickMessage(payload, exception.message);

      return {
        status,
        body: {
          error: {
            code: DEFAULT_CODE_BY_STATUS[status] ?? 'INTERNAL_ERROR',
            message,
          },
        },
      };
    }

    return {
      status: HttpStatus.INTERNAL_SERVER_ERROR,
      body: {
        error: { code: 'INTERNAL_ERROR', message: INTERNAL_ERROR_MESSAGE },
      },
    };
  }

  private pickMessage(payload: unknown, fallback: string): string {
    if (payload !== null && typeof payload === 'object') {
      const message = (payload as { message?: unknown }).message;
      if (typeof message === 'string') {
        return message;
      }
      if (Array.isArray(message) && typeof message[0] === 'string') {
        return message[0];
      }
    }
    return fallback;
  }
}

/**
 * Nest 라우터에 매칭되지 않은 경로.
 *
 * Express 기본 404 는 HTML 을 돌려주는데, 모바일 Dio 는 모든 실패를
 * { error: { code, ... } } 로 파싱한다. 형식을 맞춰 준다.
 * 라우트가 모두 등록된 뒤에 붙여야 하므로 app.init() 이후에 등록한다.
 */
export function notFoundHandler(request: Request, response: Response): void {
  const body: ErrorResponse = {
    error: {
      code: 'NOT_FOUND',
      message: '요청한 경로를 찾을 수 없습니다.',
      details: { method: request.method, path: request.originalUrl },
    },
  };

  response.status(HttpStatus.NOT_FOUND).json(body);
}
