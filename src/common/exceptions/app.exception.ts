import { HttpException, type HttpStatus } from '@nestjs/common';

/**
 * API 명세 v1 의 오류 코드 체계를 그대로 따르는 예외.
 *
 * 예)
 *   throw new AppException(
 *     'DECLARED_TODO_LOCKED',
 *     HttpStatus.UNPROCESSABLE_ENTITY,
 *     '그룹에 선언한 할 일은 오늘 수정할 수 없습니다.',
 *     { todo_id: todoId },
 *   );
 */
export class AppException extends HttpException {
  constructor(
    readonly code: string,
    status: HttpStatus,
    message: string,
    readonly details?: Record<string, unknown>,
  ) {
    super({ code, message, details }, status);
  }
}
