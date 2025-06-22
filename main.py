import os
from datetime import timedelta, datetime, timezone
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from database import *
from pydantic import BaseModel, Field, ValidationError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import logging


SECRET_KEY = os.environ.get('SECRET_KEY')

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory="templates")


bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='token')


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def authenticate_user(username: str, password: str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return None
    if not bcrypt_context.verify(password, user.password):
        return False
    return user


def create_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {"sub": username, "id": user_id, "role": role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({"exp": expires})
    token = jwt.encode(encode, SECRET_KEY, algorithm="HS256")
    return token


async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        if not token or token == "undefined":
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        user_role: str = payload.get("role")
        if username is None or user_id is None:
            return None
        return {"username": username, "id": user_id, 'user_role': user_role}

    except JWTError as e:
        print(f"JWT decoding error: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]



# Validation Fields (Pydantic)

class TodoRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=3, max_length=500)
    priority: int = Field(gt=0, lt=6)
    complete: bool


class UserRequest(BaseModel):
    email: str = Field()
    username: str = Field(min_length=3, max_length=32)
    first_name: str = Field(min_length=3, max_length=32)
    last_name: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=4, max_length=20)
    is_active: bool = Field(default=True)
    role: str = Field()
    phone_number: str = Field()


class PasswordVerification(BaseModel):
    password: str
    new_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# Endpoints

@app.get("/healthy")
def healthy():
    return {"status": "healthy"}



# Todos

@app.get("/todo/{id}", status_code=status.HTTP_200_OK)
async def get_todo(user: user_dependency, db: db_dependency, id: int):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed")

    todo = (db.query(Todos).filter(Todos.id == id).filter(Todos.owner_id == user.get("id")).first())
    if todo is not None:
        return todo
    else:
        raise HTTPException(404, "Todo Not Found")


@app.post("/create-todo", status_code=status.HTTP_201_CREATED)
async def create_todo(user: user_dependency, db: db_dependency, todo_request: TodoRequest):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed")
    todo = Todos(**todo_request.dict(), owner_id=user.get("id"))
    db.add(todo)
    db.commit()


@app.put("/edit-todo/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_todo(user: user_dependency, db: db_dependency, id: int, todo_request: TodoRequest):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed")

    todo = (db.query(Todos).filter(Todos.id == id).filter(Todos.owner_id == user.get("id")).first())
    if todo is None:
        raise HTTPException(404, f"Todo Not Found")
    else:
        todo.title = todo_request.title
        todo.description = todo_request.description
        todo.priority = todo_request.priority
        todo.complete = todo_request.complete
        db.add(todo)
        db.commit()


@app.delete("/delete-todo/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(user: user_dependency, db: db_dependency, id: int):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed")
    elif user.get("user_role") != 'admin':
        raise HTTPException(status_code=403, detail="Uh-uh")

    todo = (db.query(Todos).filter(Todos.id == id).filter(Todos.owner_id == user.get("id")).first())
    if todo is None:
        raise HTTPException(404, "Todo Not Found")
    else:
        db.query(Todos).filter(Todos.id == id).filter(Todos.owner_id == user.get("id")).delete()
        db.commit()



# Authorization and Authentication / User action

@app.post("/create-user", status_code=status.HTTP_201_CREATED)
async def create_user(request: Request, db: db_dependency):
    try:
        # Log the raw request data
        raw_data = await request.json()
        logging.debug(f"Raw request data: {raw_data}")

        # Attempt to parse the request
        user_request = UserRequest(**raw_data)

        user = Users(
            email=user_request.email,
            username=user_request.username,
            first_name=user_request.first_name,
            last_name=user_request.last_name,
            password=bcrypt_context.hash(user_request.password),
            role=user_request.role,
            is_active=True,
            phone_number=user_request.phone_number
        )
        db.add(user)
        db.commit()

    except ValidationError as ve:
        # Log the details of the validation error
        logging.error(f"Validation error: {ve.errors()}")
        raise HTTPException(status_code=422, detail=ve.errors())
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")



@app.get("/get-user", status_code=status.HTTP_200_OK)
async def get_user(db: db_dependency, user: user_dependency):
    if user is None:
        raise HTTPException(401, "Authentication failed")

    return db.query(Users).filter(Users.id == user.get("id")).first()


@app.put("/update-password", status_code=status.HTTP_200_OK)
async def change_password(db: db_dependency, user: user_dependency, password_verification: PasswordVerification):
    if user is None:
        raise HTTPException(401, "Failed authentication")
    user_model = db.query(Users).filter(Users.id == user.get("id")).first()

    if not bcrypt_context.verify(password_verification.password, user_model.password):
        raise HTTPException(401, "Error on ur mama")
    user_model.password = bcrypt_context.hash(password_verification.new_password)
    db.add(user_model)
    db.commit()


@app.put("/update-phone-number", status_code=status.HTTP_200_OK)
async def update_phone_number(db: db_dependency, user: user_dependency, phone_number: str):
    if user is None:
        raise HTTPException(401, "Failed authentication")
    user_model = db.query(Users).filter(Users.id == user.get("id")).first()
    user_model.phone_number = phone_number
    db.add(user_model)
    db.commit()


@app.post("/token")
async def create_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        return "Failed authentication"
    token = create_token(user.username, user.id, user.role, timedelta(minutes=180))

    return {'access_token': token, "token_type": "Bearer"}


def redirect_to_login():
    redirect_response = RedirectResponse(url="/login-page", status_code=status.HTTP_302_FOUND)
    redirect_response.delete_cookie(key="access_token")
    return redirect_response


## Pages ###


@app.get('/')
def home():
    return RedirectResponse(url='/todo-page', status_code=status.HTTP_302_FOUND)


@app.get('/login-page')
def render_login_page(request: Request):
    return templates.TemplateResponse('login.html', {"request": request})


@app.get('/register-page')
def render_register_page(request: Request):
    return templates.TemplateResponse('register.html', {"request": request})


@app.get('/todo-page')
async def render_todo_page(request: Request, db: db_dependency):
    try:
        user = await get_current_user(request.cookies.get('access_token'))
        if user is None:
            return redirect_to_login()

        todos = db.query(Todos).filter(Todos.owner_id == user.get('id')).all()

        return templates.TemplateResponse('todo.html', {"request": request, "todos": todos, "user": user})

    except:
        redirect_to_login()


@app.get('/add-todo-page')
async def add_todo_page(request: Request, db: db_dependency):
    try:
        user = await get_current_user(request.cookies.get('access_token'))
        if user is None:
            return redirect_to_login()

        return templates.TemplateResponse("add-todo.html", {"request": request, 'user': user})

    except:
        return redirect_to_login()


@app.get('/edit-todo-page/{todo_id}')
async def edit_todo_page(request: Request, db: db_dependency, todo_id: int):
    try:
        user = await get_current_user(request.cookies.get('access_token'))
        if user is None:
            return redirect_to_login()

        todo = db.query(Todos).filter(Todos.id == todo_id).first()

        return templates.TemplateResponse("edit-todo.html", {"request": request, 'todo': todo, 'user': user})

    except:
        return redirect_to_login()


