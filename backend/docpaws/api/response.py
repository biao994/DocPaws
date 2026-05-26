"""
统一响应结构 + 错误码体系
- 成功响应：{ request_id, data }
- 错误响应：{ request_id, error_code, message, user_hint }
"""
from typing import Any


class ErrorCode:
    """错误码枚举"""
    # 4xx 客户端错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    KB_NOT_FOUND = "KB_NOT_FOUND"
    KB_EMPTY = "KB_EMPTY"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"
    FEEDBACK_NOT_FOUND = "FEEDBACK_NOT_FOUND"
    MESSAGE_NOT_FOUND = "MESSAGE_NOT_FOUND"
    ANSWER_NOT_FOUND = "ANSWER_NOT_FOUND"
    INDEX_NOT_READY = "INDEX_NOT_READY"
    INDEX_FAILED = "INDEX_FAILED"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    NAME_CONFLICT = "NAME_CONFLICT"

    # 5xx 服务端错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SEARCH_SERVICE_UNAVAILABLE = "SEARCH_SERVICE_UNAVAILABLE"

    # 200 特殊情况
    NO_HIT = "NO_HIT"


# 错误码 -> HTTP 状态码 映射
ERROR_CODE_TO_STATUS = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.EMAIL_ALREADY_REGISTERED: 409,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.FILE_NOT_FOUND: 404,
    ErrorCode.KB_NOT_FOUND: 404,
    ErrorCode.KB_EMPTY: 404,
    ErrorCode.JOB_NOT_FOUND: 404,
    ErrorCode.CONVERSATION_NOT_FOUND: 404,
    ErrorCode.MESSAGE_NOT_FOUND: 404,
    ErrorCode.ANSWER_NOT_FOUND: 404,
    ErrorCode.FEEDBACK_NOT_FOUND: 404,
    ErrorCode.INDEX_NOT_READY: 409,
    ErrorCode.INDEX_FAILED: 409,
    ErrorCode.DUPLICATE_REQUEST: 409,
    ErrorCode.NAME_CONFLICT: 409,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SEARCH_SERVICE_UNAVAILABLE: 503,
    ErrorCode.NO_HIT: 200,
}

# 错误码 -> 用户提示映射
ERROR_CODE_TO_HINT = {
    ErrorCode.VALIDATION_ERROR: "请求参数不合法",
    ErrorCode.UNAUTHORIZED: "请先登录",
    ErrorCode.AUTH_INVALID_CREDENTIALS: "邮箱或密码错误",
    ErrorCode.FORBIDDEN: "你没有访问该资源的权限",
    ErrorCode.EMAIL_ALREADY_REGISTERED: "该邮箱已注册",
    ErrorCode.DOCUMENT_NOT_FOUND: "文档不存在或已被删除",
    ErrorCode.FILE_NOT_FOUND: "文件不存在或已被删除",
    ErrorCode.KB_NOT_FOUND: "知识库不存在",
    ErrorCode.KB_EMPTY: "知识库为空,请先上传文档",
    ErrorCode.JOB_NOT_FOUND: "任务不存在",
    ErrorCode.CONVERSATION_NOT_FOUND: "会话不存在",
    ErrorCode.MESSAGE_NOT_FOUND: "消息不存在",
    ErrorCode.FEEDBACK_NOT_FOUND: "反馈不存在",
    ErrorCode.ANSWER_NOT_FOUND: "答案不存在",
    ErrorCode.INDEX_NOT_READY: "文档正在处理中，请稍后再试",
    ErrorCode.INDEX_FAILED: "文档处理失败，请重新上传",
    ErrorCode.DUPLICATE_REQUEST: "请勿重复提交",
    ErrorCode.NAME_CONFLICT: "该位置已存在同名文档，请选择替换或保留全部",
    ErrorCode.INTERNAL_ERROR: "系统繁忙，请稍后重试",
    ErrorCode.SEARCH_SERVICE_UNAVAILABLE: "检索服务暂时不可用，请稍后重试",
    ErrorCode.NO_HIT: "知识库中没有找到相关内容",
}


def success(data: Any, request_id: str) -> dict:
    """构建成功响应"""
    return {"request_id": request_id, "data": data}


def error(
    error_code: str,
    message: str | None = None,
    user_hint: str | None = None,
    request_id: str = "",
    details: Any = None,
) -> dict:
    """构建错误响应"""
    if user_hint is None:
        user_hint = ERROR_CODE_TO_HINT.get(error_code, "")
    if message is None:
        message = user_hint or error_code

    out: dict = {
        "request_id": request_id,
        "error_code": error_code,
        "message": message,
        "user_hint": user_hint,
    }
    if details is not None:
        out["details"] = details
    return out


def get_status_code(error_code: str) -> int:
    """获取错误码对应的 HTTP 状态码"""
    return ERROR_CODE_TO_STATUS.get(error_code, 500)
