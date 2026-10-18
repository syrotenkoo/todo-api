from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Optional

# --- 1. Модели данных ---

# Это модель для таблицы в базе данных. Она же используется для ответа API.
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    description: Optional[str] = None
    done: bool = False

# Это модель для входных данных при создании задачи (без id, его генерирует база).
class TaskCreate(SQLModel):
    title: str
    description: Optional[str] = None
    done: bool = False

# Это модель для обновления задачи (все поля опциональны).
class TaskUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    done: Optional[bool] = None


# --- 2. Настройка базы данных ---

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# check_same_thread=False нужен для SQLite, чтобы FastAPI мог обращаться к базе из разных потоков.
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

# Функция для создания таблиц при старте (в учебных целях).
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# Зависимость, которая дает сессию базы данных для каждого запроса.
def get_session():
    with Session(engine) as session:
        yield session


# --- 3. Приложение FastAPI и эндпоинты ---

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# CREATE: Создать новую задачу
@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: TaskCreate, session: Session = Depends(get_session)):
    db_task = Task.model_validate(task)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task

# READ: Получить список всех задач (с возможностью фильтрации по статусу done)
@app.get("/tasks", response_model=list[Task])
def read_tasks(done: Optional[bool] = None, session: Session = Depends(get_session)):
    query = select(Task)
    if done is not None:
        query = query.where(Task.done == done)
    tasks = session.exec(query).all()
    return tasks

# READ: Получить одну задачу по ID
@app.get("/tasks/{task_id}", response_model=Task)
def read_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# UPDATE: Обновить задачу по ID
@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task_update: TaskUpdate, session: Session = Depends(get_session)):
    db_task = session.get(Task, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Обновляем только те поля, которые были переданы
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
        
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task

# DELETE: Удалить задачу по ID
@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()
    return None