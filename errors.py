"""Stable external errors; diagnostics never interpolate exception text or paths."""
import logging
import sqlite3
from kb import KBError

LOG = logging.getLogger('algorithm-learning.errors')


def error_response(exc):
    if isinstance(exc, KBError):
        # These codes historically used caller IDs as messages. Never echo them.
        messages={'NOT_FOUND':'请求的实体不存在','EVIDENCE_NOT_FOUND':'引用的归档消息不存在',
                  'SOURCE_AMBIGUOUS':'存在多个匹配来源；请核实来源关联',
                  'VALIDATION_ERROR':'学习成果校验失败；请依据 details 修正字段'}
        LOG.warning('code=%s type=KBError',exc.code)
        error = {'code': exc.code, 'message': messages.get(exc.code,exc.message)}
        if exc.details is not None:
            error['details'] = exc.details
        return {'ok': False, 'error': error}
    if isinstance(exc, PermissionError):
        code, message = 'PERMISSION_DENIED', '没有访问所需本地资源的权限'
    elif isinstance(exc, FileNotFoundError):
        code, message = 'SOURCE_UNAVAILABLE', '所需本地资源不存在或已不可用'
    elif isinstance(exc, sqlite3.IntegrityError):
        code, message = 'CONSTRAINT', '数据违反完整性约束'
    elif isinstance(exc, sqlite3.Error):
        code, message = 'DATABASE', '数据库操作失败；检查存储与锁状态'
    elif isinstance(exc, OSError):
        code, message = 'STORAGE_UNAVAILABLE', '本地存储操作失败'
    elif isinstance(exc, (ValueError, TypeError, KeyError, RecursionError)):
        code, message = 'INVALID_INPUT', '输入格式或类型不符合接口要求'
    else:
        code, message = 'INTERNAL_ERROR', '内部操作失败；请依据错误码检查服务日志'
    # Only machine-readable fields; no traceback, exception repr, filename or SQL.
    native = getattr(exc, 'sqlite_errorcode', None) if isinstance(exc, sqlite3.Error) else getattr(exc, 'errno', None)
    LOG.warning('code=%s type=%s native_code=%s', code, type(exc).__name__, native)
    error = {'code': code, 'message': message}
    if code == 'DATABASE':
        error['retryable'] = native is not None and (native & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    return {'ok': False, 'error': error}
