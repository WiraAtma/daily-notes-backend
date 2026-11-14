import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import password_hash

TEST_PASSWORD_HASH = password_hash.hash("test-password")


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def users(db_session):
    user_a = User(
        name="User A",
        email="a@example.com",
        password_hash=TEST_PASSWORD_HASH,
    )
    user_b = User(
        name="User B",
        email="b@example.com",
        password_hash=TEST_PASSWORD_HASH,
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    return user_a, user_b


@pytest.fixture
def auth_headers(users):
    from app.core.security import create_access_token

    user_a, user_b = users
    return (
        {"Authorization": f"Bearer {create_access_token(user_a.id)}"},
        {"Authorization": f"Bearer {create_access_token(user_b.id)}"},
    )
