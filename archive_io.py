"""Contained, immutable publication shared by original and normalized archives."""
import os
import re
import tempfile
from kb import KBError, digest


def archive_path(kb, conversation_id, sha, suffix):
    if not isinstance(conversation_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}',conversation_id):
        raise KBError('INVALID_SOURCE_ID','聊天 ID 必须是安全的单一路径组件')
    root=(kb.path.parent/'archives').resolve()
    folder=root/conversation_id
    if folder.resolve().parent!=root:
        raise KBError('INVALID_SOURCE_ID','归档目录不能通过链接越界')
    return folder/(sha+suffix)


def publish(path, raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        try:
            os.link(temporary,path)
        except FileExistsError:
            if digest(path.read_bytes())!=digest(raw):
                raise KBError('ARCHIVE_CORRUPT','已有内容寻址归档校验失败')
    finally:
        os.unlink(temporary)
