"""Path-free public projections. Never mutate stored diagnostic/evidence records.

Text redaction is conservative: path-looking prose may be masked. It is not a
general secret scanner. Pagination must use the projected text's offsets.
"""
import json
import re
from kb import digest

_PRIVATE = {'cwd', 'source_path', 'archive_path', 'file_path', 'filename',
            'directory', 'working_directory', 'home'}
# Preserve web links, but remove file URIs, drive paths, UNC and POSIX paths.
# Spaces within directory components are allowed; trailing prose is not consumed.
_PATH = re.compile(
    r'https?://[^\s<>"`]+|'
    r'(?:file://[\\/]*|[A-Za-z]:[\\/]+|\\\\(?=[^\s\\/])|(?<![\w:/\\])/+)'
    r'(?=[^\s\\/])(?:[^\r\n<>"`|]*[\\/])?[^\s<>"`|,;\\/]+'
)


def source_id(value):
    return digest(str(value))


def public_text(text):
    return _PATH.sub(lambda m: m[0] if m[0].startswith(('https://', 'http://'))
                     else '[local-path:' + source_id(m[0])[:16] + ']', text)


def public_response(value, depth=0):
    # Historical JSON is not constrained by current input schemas. Fail closed
    # before recursion exhaustion; do not return partially traversed raw content.
    if depth > 64:
        return '[redacted-depth-limit]'
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in _PRIVATE or key.lower().endswith(('_path', '_cwd')):
                if key == 'source_path' and item and 'source_id' not in value:
                    result['source_id'] = source_id(item)
                continue
            result[public_text(key)] = public_response(item, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [public_response(item, depth + 1) for item in value]
    if isinstance(value, str):
        # Audit columns may contain JSON inside JSON, including nested strings.
        if value.lstrip().startswith(('{', '[', '"')):
            try:
                decoded = json.loads(value)
            except (ValueError, RecursionError):
                pass
            else:
                return json.dumps(public_response(decoded, depth + 1), ensure_ascii=False)
        return public_text(value)
    return value
