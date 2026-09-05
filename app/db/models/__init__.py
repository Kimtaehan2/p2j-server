"""SQLAlchemy 모델.

Alembic 이 metadata 를 볼 수 있도록 모든 모델을 여기서 import 한다.
새 모델 파일을 만들면 아래 목록에 추가한다. 빠뜨리면 autogenerate 가 테이블 삭제를 제안한다.
"""

from app.db.base import Base
from app.db.models.goal import Goal
from app.db.models.refresh_token import RefreshToken
from app.db.models.todo import Todo
from app.db.models.user import User

__all__ = ["Base", "Goal", "RefreshToken", "Todo", "User"]
