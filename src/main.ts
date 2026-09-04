import { pathToFileURL } from 'node:url';
import {
  HttpStatus,
  Logger,
  ValidationPipe,
  type INestApplication,
  type ValidationError,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { AppModule } from './app.module.js';
import { AppException } from './common/exceptions/app.exception.js';
import {
  AllExceptionsFilter,
  notFoundHandler,
} from './common/filters/all-exceptions.filter.js';
import { ResponseInterceptor } from './common/interceptors/response.interceptor.js';

const GLOBAL_PREFIX = 'v1';
const DEFAULT_PORT = 8000;

/**
 * ValidationPipe 오류를 API 명세 v1 형식으로 바꾼다.
 * details.fields 에 필드별 메시지를 담아 모바일이 어느 칸이 틀렸는지 알 수 있게 한다.
 */
function validationExceptionFactory(errors: ValidationError[]): AppException {
  const fields: Record<string, string[]> = {};

  const collect = (list: ValidationError[], prefix = ''): void => {
    for (const error of list) {
      const path =
        prefix === '' ? error.property : `${prefix}.${error.property}`;
      const messages = Object.values(error.constraints ?? {});
      if (messages.length > 0) {
        fields[path] = messages;
      }
      if (error.children !== undefined && error.children.length > 0) {
        collect(error.children, path);
      }
    }
  };

  collect(errors);

  return new AppException(
    'VALIDATION_ERROR',
    HttpStatus.BAD_REQUEST,
    '요청 형식이 올바르지 않습니다.',
    { fields },
  );
}

/**
 * main.ts 와 e2e 테스트가 동일한 설정을 쓰도록 분리했다.
 * 여기에 없는 전역 설정이 생기면 e2e 가 실제 동작과 어긋난다.
 *
 * 마지막에 app.init() 까지 수행한다. 매칭되지 않은 경로용 404 핸들러는
 * 라우트가 모두 등록된 뒤에 붙어야 하기 때문이다.
 */
export async function configureApp(app: INestApplication): Promise<void> {
  const config = app.get(ConfigService);

  app.setGlobalPrefix(GLOBAL_PREFIX);

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
      transformOptions: { enableImplicitConversion: true },
      exceptionFactory: validationExceptionFactory,
    }),
  );
  app.useGlobalInterceptors(new ResponseInterceptor());
  app.useGlobalFilters(new AllExceptionsFilter());
  app.enableShutdownHooks();

  configureCors(app, config);
  configureSwagger(app);

  await app.init();
  app.use(notFoundHandler);
}

function configureCors(app: INestApplication, config: ConfigService): void {
  const isProduction = config.get<string>('NODE_ENV') === 'production';

  if (!isProduction) {
    // Flutter web(flutter run -d chrome) 개발용.
    app.enableCors({ origin: true, credentials: true });
    return;
  }

  const origins = (config.get<string>('CORS_ORIGINS') ?? '')
    .split(',')
    .map((origin) => origin.trim())
    .filter((origin) => origin.length > 0);

  // 운영에서 허용 origin 이 명시되지 않으면 CORS 를 열지 않는다.
  if (origins.length > 0) {
    app.enableCors({ origin: origins, credentials: true });
  }
}

function configureSwagger(app: INestApplication): void {
  const document = SwaggerModule.createDocument(
    app,
    new DocumentBuilder()
      .setTitle('P2J API')
      .setDescription(
        'P2J 서버 API. 응답은 { data }, 오류는 { error: { code, message, details } } 형식이다.',
      )
      .setVersion('v1')
      .addBearerAuth()
      .build(),
  );

  SwaggerModule.setup(`${GLOBAL_PREFIX}/docs`, app, document, {
    jsonDocumentUrl: `${GLOBAL_PREFIX}/docs-json`,
  });
}

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);
  await configureApp(app);

  const port = app.get(ConfigService).get<number>('PORT') ?? DEFAULT_PORT;
  await app.listen(port);

  new Logger('Bootstrap').log(
    `P2J 서버 시작 — http://localhost:${port}/${GLOBAL_PREFIX} (문서: /${GLOBAL_PREFIX}/docs)`,
  );
}

// 테스트가 이 파일을 import 할 때는 서버를 띄우지 않는다.
const entrypoint = process.argv[1];
if (
  entrypoint !== undefined &&
  import.meta.url === pathToFileURL(entrypoint).href
) {
  await bootstrap();
}
