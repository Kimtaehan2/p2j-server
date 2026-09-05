"""v1 라우터 묶음. 새 엔드포인트 파일을 만들면 여기에 include 한다."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
