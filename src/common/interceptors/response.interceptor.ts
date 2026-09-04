import {
  type CallHandler,
  type ExecutionContext,
  HttpStatus,
  Injectable,
  type NestInterceptor,
} from '@nestjs/common';
import type { Response } from 'express';
import type { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

/** 성공 응답 공통 래퍼. */
export interface SuccessResponse<T> {
  data: T;
}

/**
 * 컨트롤러가 반환한 값을 API 명세 v1 의 `{ data: ... }` 형태로 감싼다.
 *
 * 204 No Content 는 감싸지 않는다. 모바일의 `uncomplete` 가 본문 없음을 전제로
 * summary 를 로컬에서 다시 계산하므로, 여기서 본문을 실어 보내면 계약이 깨진다.
 */
@Injectable()
export class ResponseInterceptor<T> implements NestInterceptor<
  T,
  SuccessResponse<T> | T
> {
  intercept(
    context: ExecutionContext,
    next: CallHandler<T>,
  ): Observable<SuccessResponse<T> | T> {
    const response = context.switchToHttp().getResponse<Response>();

    return next.handle().pipe(
      map((payload) => {
        if (response.statusCode === HttpStatus.NO_CONTENT) {
          return payload;
        }
        return { data: payload };
      }),
    );
  }
}
