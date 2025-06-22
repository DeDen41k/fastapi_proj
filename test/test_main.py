from main import get_db, get_current_user, authenticate_user, create_token, SECRET_KEY
from fastapi import status
from .utils import *
from jose import jwt
from datetime import timedelta
import pytest


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user



def test_read_all_authenticated(test_todo):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [{"complete": False,
                                "title": "Test Todo",
                                "description": "Test description",
                                'id': 1,
                                "owner_id": 1,
                                "priority": 5}]

def test_read_one_authenticated(test_todo):
    response = client.get("/todo/1")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"complete": False,
                                "title": "Test Todo",
                                "description": "Test description",
                                'id': 1,
                                "owner_id": 1,
                                "priority": 5}


def test_read_one_authenticated_not_found(test_todo):
    response = client.get('/todo/999')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Todo Not Found'}


# Testing todos

def test_create_todo(test_todo):
    request_data = {"title": "New Todo",
                    "description": "New description",
                    "complete": False,
                    "priority": 5}
    response = client.post("/create-todo", json=request_data)
    assert response.status_code == 201

    db = TestingSessionLocal()
    model = db.query(Todos).filter(Todos.id == 2).first()
    assert model.title == request_data["title"]
    assert model.description == request_data["description"]


def test_update_todo(test_todo):
    request_data = {
        "title": "Updated Todo",
        'description': "Updated description",
        "complete": True,
        "priority": 3}

    response = client.put("/edit-todo/1", json=request_data)
    assert response.status_code == 204

    db = TestingSessionLocal()
    model = db.query(Todos).filter(Todos.id == 1).first()
    assert model.title == request_data["title"]


def test_delete_todo(test_todo):
    response = client.delete("delete-todo/1")
    assert response.status_code == 204

    db = TestingSessionLocal()
    model = db.query(Todos).filter(Todos.id == 1).first()
    assert model is None


# Testing User

def test_return_user(test_user):
    response = client.get("/get-user")
    assert response.status_code == 200
    assert response.json()['username'] == "dedenistoma139"
    assert response.json()['phone_number'] == "+380 96 321 8381"


def test_change_password(test_user):
    response = client.put('/update-password', json={"password": "parol",
                                                    "new_password": "new test"})
    assert response.status_code == 200


def test_change_phone_number(test_user):
    response = client.put('/update-phone-number', params={'phone_number': '+40 777 777 777'})
    assert response.status_code == 200


# Testing auth

def test_authenticate_user(test_user):
    db = TestingSessionLocal()
    authenticated_user = authenticate_user(test_user.username, 'parol', db)
    assert authenticated_user is not None
    assert authenticated_user.username == test_user.username

    non_existing_user = authenticate_user("yoyeah", 'parol', db)
    assert non_existing_user is None

    wrong_password = authenticate_user(test_user.username, 'yoyeah', db)
    assert wrong_password is False


def test_create_access_token():
    username = 'testuser'
    user_id = 1
    role = 'user'
    expires = timedelta(days=1)

    token = create_token(username, user_id, role, expires)
    decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"],
                               options={"verify_signature": False})

    assert decoded_token["sub"] == username
    assert decoded_token["id"] == user_id
    assert decoded_token["role"] == role


@pytest.mark.asyncio
async def test_get_current_user_token():
    encode = {"sub": 'testuser', 'id': 1, 'role': 'user'}
    token = jwt.encode(encode, SECRET_KEY, algorithm="HS256")

    user = await get_current_user(token=token)
    assert user == {"username": 'testuser', 'id': 1, 'user_role': 'user'}





