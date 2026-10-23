from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User, get_db
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(tags=["账号"])


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_\u4e00-\u9fa5]+$")
    password: str = Field(min_length=4, max_length=64)
    nickname: str | None = Field(default=None, max_length=16)


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    nickname: str
    yuanbao: int


def _serialize(user: User) -> dict:
    return {"id": user.id, "username": user.username, "nickname": user.nickname, "yuanbao": user.yuanbao}


@router.post("/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(409, "这个用户名已经被人占了，换一个吧")

    user = User(
        username=payload.username,
        nickname=payload.nickname or payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id), "user": _serialize(user)}


@router.post("/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "用户名或密码不对")
    return {"token": create_token(user.id), "user": _serialize(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _serialize(user)


class RechargeIn(BaseModel):
    amount: int = Field(gt=0, le=1_000_000)


@router.post("/me/recharge")
def recharge(payload: RechargeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """模拟充值：本模拟器不发财，只发元宝。"""
    user.yuanbao += payload.amount
    db.add(user)
    db.commit()
    return {"yuanbao": user.yuanbao, "gained": payload.amount}
