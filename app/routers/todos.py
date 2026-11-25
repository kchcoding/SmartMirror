"""간단한 할 일 목록 (캘린더 일정과 별개로 미러에 같이 표시)."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import database as db

router = APIRouter(prefix="/api/todos", tags=["todos"])


class TodoIn(BaseModel):
    text: str = Field(min_length=1, max_length=100)


@router.get("")
def list_todos():
    return db.list_todos()


@router.post("")
def add_todo(body: TodoIn):
    return {"id": db.add_todo(body.text.strip())}


@router.post("/{todo_id}/toggle")
def toggle_todo(todo_id: int):
    db.toggle_todo(todo_id)
    return {"ok": True}


@router.delete("/{todo_id}")
def delete_todo(todo_id: int):
    db.delete_todo(todo_id)
    return {"ok": True}
