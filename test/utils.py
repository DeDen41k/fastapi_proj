from sqlalchemy import create_engine, StaticPool, text
from sqlalchemy.orm import sessionmaker
from database import Base, Todos, Users
from fastapi.testclient import TestClient
from main import app, bcrypt_context
import pytest

SQLALCHEMY_DATABASE_URL = "sqlite:///test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL,
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    return {"id": 1, "username": "Den", "user_role": 'admin'}


client = TestClient(app)


@pytest.fixture
def test_todo():
    todo = Todos(
        title="Test Todo",
        description="Test description",
        priority=5,
        complete=False,
        owner_id=1
    )

    db = TestingSessionLocal()
    db.add(todo)
    db.commit()
    yield todo
    with engine.connect() as connection:
        connection.execute(text('DELETE FROM todos;'))
        connection.commit()


@pytest.fixture
def test_user():
    user = Users(
        email='dedenistoma139@gmail.com',
        username='dedenistoma139',
        first_name='Denis',
        last_name='Toma',
        password=bcrypt_context.hash('parol'),
        is_active=True,
        role='admin',
        phone_number='+380 96 321 8381'
    )
    db = TestingSessionLocal()
    db.add(user)
    db.commit()
    yield user
    with engine.connect() as connection:
        connection.execute(text('DELETE FROM users;'))
        connection.commit()


