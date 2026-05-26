"""
注册 / 登录 / 登出（Cookie Session，不返回 token 给 JS）
"""
from fastapi import APIRouter, Request, Depends

from docpaws.api.deps import get_auth_service
from docpaws.api.response import success
from docpaws.api.schemas.auth import RegisterRequest, LoginRequest, UserPublic
from docpaws.usecases.auth_service import AuthService

router = APIRouter()


def _session_login(request: Request, user_id: str) -> None:
    request.session.clear()
    request.session["user_id"] = user_id


@router.post("/auth/register")
def api_register(
    request: Request,
    req: RegisterRequest,
    svc: AuthService = Depends(get_auth_service),
):
    user = svc.register(email=str(req.email), username=req.username, password=req.password)
    _session_login(request, user.id)
    data = UserPublic(id=user.id, email=user.email, username=user.username).model_dump()
    return success(data=data, request_id=request.state.request_id)


@router.post("/auth/login")
def api_login(
    request: Request,
    req: LoginRequest,
    svc: AuthService = Depends(get_auth_service),
):
    user = svc.login(email=str(req.email), password=req.password)
    _session_login(request, user.id)
    data = UserPublic(id=user.id, email=user.email, username=user.username).model_dump()
    return success(data=data, request_id=request.state.request_id)


@router.post("/auth/logout")
def api_logout(request: Request):
    request.session.clear()
    return success(data={"logged_out": True}, request_id=request.state.request_id)
