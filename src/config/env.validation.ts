import { Type, plainToInstance } from 'class-transformer';
import {
  IsEnum,
  IsInt,
  IsNotEmpty,
  IsString,
  Max,
  Min,
  validateSync,
} from 'class-validator';

/** 서버가 인식하는 실행 환경. */
export enum NodeEnv {
  Development = 'development',
  Test = 'test',
  Production = 'production',
}

/**
 * 기반 서버 실행에 반드시 필요한 환경변수만 검증한다.
 * JWT, Firebase, Clova, OpenAI 값은 해당 기능을 구현할 때 필수로 승격한다.
 */
export class EnvironmentVariables {
  @IsEnum(NodeEnv, {
    message: 'NODE_ENV 는 development, test, production 중 하나여야 합니다.',
  })
  NODE_ENV!: NodeEnv;

  @Type(() => Number)
  @IsInt({ message: 'PORT 는 정수여야 합니다.' })
  @Min(1, { message: 'PORT 는 1 이상이어야 합니다.' })
  @Max(65535, { message: 'PORT 는 65535 이하여야 합니다.' })
  PORT!: number;

  @IsString()
  @IsNotEmpty({ message: 'DATABASE_URL 이 비어 있습니다.' })
  DATABASE_URL!: string;

  @IsString()
  @IsNotEmpty({ message: 'REDIS_URL 이 비어 있습니다.' })
  REDIS_URL!: string;

  @Type(() => Number)
  @IsInt({ message: 'SERVICE_DAY_START_HOUR 는 정수여야 합니다.' })
  @Min(0, { message: 'SERVICE_DAY_START_HOUR 는 0 이상이어야 합니다.' })
  @Max(23, { message: 'SERVICE_DAY_START_HOUR 는 23 이하여야 합니다.' })
  SERVICE_DAY_START_HOUR!: number;
}

/**
 * ConfigModule 의 validate 훅.
 * 실패해도 값 자체는 절대 출력하지 않고 키 이름과 위반 사유만 알린다.
 */
export function validateEnv(
  config: Record<string, unknown>,
): EnvironmentVariables {
  const validated = plainToInstance(EnvironmentVariables, config, {
    enableImplicitConversion: false,
  });

  const errors = validateSync(validated, {
    skipMissingProperties: false,
    forbidUnknownValues: false,
  });

  if (errors.length > 0) {
    const reasons = errors
      .map((error) => {
        const constraints = Object.values(error.constraints ?? {}).join(', ');
        return `- ${error.property}: ${constraints}`;
      })
      .join('\n');
    throw new Error(
      `환경변수 검증에 실패했습니다. .env.example 을 참고해 값을 채우세요.\n${reasons}`,
    );
  }

  return validated;
}
