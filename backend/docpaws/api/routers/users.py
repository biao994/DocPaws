"""
当前用户
"""
from fastapi import APIRouter, Request, Depends

from docpaws.api.deps import get_current_user
from docpaws.api.response import success
from docpaws.api.schemas.auth import UserPublic
from docpaws.domain.models.user import User

router = APIRouter()


@router.get("/users/me")
def api_me(request: Request, current_user: User = Depends(get_current_user)):
    data = UserPublic(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
    ).model_dump()
    return success(data=data, request_id=request.state.request_id)
