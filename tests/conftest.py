import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os
import uuid

pytest_plugins = ('pytest_asyncio',)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/pitchmind_test"
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def test_client(db_session):
    from app.main import app
    from app.dependencies.db import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        id=uuid.uuid4(),
        email=f"user_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("testpassword"),
        name="Test User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_admin(db_session):
    from app.models.user import User
    from app.core.security import hash_password
    admin = User(
        id=uuid.uuid4(),
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("adminpassword"),
        name="Test Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


@pytest.fixture
def test_token(test_user):
    from app.core.security import create_access_token
    return create_access_token({
        "user_id": str(test_user.id),
        "role": test_user.role,
        "email": test_user.email
    })


@pytest.fixture
def test_admin_token(test_admin):
    from app.core.security import create_access_token
    return create_access_token({
        "user_id": str(test_admin.id),
        "role": test_admin.role,
        "email": test_admin.email
    })


@pytest.fixture
def mock_claude(mocker):
    import json
    import pathlib
    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "claude_response.json"
    fixture_data = json.loads(fixture_path.read_text())
    return mocker.patch("app.services.claude.call_claude",
                        return_value=(fixture_data, 1000))


@pytest.fixture
def claude_fixture_slides():
    import json
    import pathlib
    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "claude_response.json"
    data = json.loads(fixture_path.read_text())
    return data.get("slides", data) if isinstance(data, dict) else data
