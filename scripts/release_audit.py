"""离线发布检查：仅输出相对路径和命中类型，不打印秘密内容。"""
from pathlib import Path
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".release-audit" / "final-check"
PATTERNS = {
    "credential_literal": re.compile(rb"(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"),
    "assigned_secret": re.compile(rb"(?i)(?:api[_-]?key|password|access[_-]?token)\s*[:=]\s*[\"'](?!example|placeholder|your|test|dummy)[A-Za-z0-9_+/=-]{24,}[\"']"),
    "personal_windows_path": re.compile(rb"(?i)(?:[C-Z]:[\\/]+Users[\\/]+(?!you(?:[\\/]|rname)|Public[\\/]|Default[\\/])[^\\/\s\"']+|[DEG]:[\\/]+[^\s\"'<>]+)"),
    "email": re.compile(rb"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "uuid": re.compile(rb"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
}

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)

def findings(data):
    return {k: len(v.findall(data)) for k, v in PATTERNS.items() if v.search(data)}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    release = sorted(set(x.decode() for x in git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0") if x))
    work = []
    links = []
    disallowed = []
    for name in release:
        p = ROOT / name
        if not p.is_file():
            disallowed.append({"file": name, "reason": "missing or not a file"});continue
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT):
            links.append(name);continue
        if p.suffix.lower() in {".sqlite3", ".db", ".log", ".pyc", ".pyd", ".exe", ".zip"} or name.startswith((".venv/", ".release-audit/", "archives/", "backups/")):
            disallowed.append({"file": name, "reason": "private/runtime artifact"})
        hits = findings(p.read_bytes())
        if hits:work.append({"file": name, "hits": hits})
    staged = []
    index_paths = []
    for entry in git("ls-files", "--stage", "-z").split(b"\0"):
        if not entry:continue
        head, name = entry.split(b"\t", 1); mode, oid, stage = head.split()
        index_paths.append(name.decode())
        hits = findings(git("cat-file", "blob", oid.decode()))
        if hits:staged.append({"file": name.decode(), "hits": hits})
    objects=[];object_counts=collections.Counter()
    for line in git("cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype)").splitlines():
        oid,kind=line.decode().split();object_counts[kind]+=1
        if kind in {"blob", "commit", "tag"}:
            hits=findings(git("cat-file", kind, oid))
            if hits:objects.append({"object":oid,"type":kind,"hits":hits})
    ignored=collections.Counter();ignored_hits=collections.Counter();ignored_files=[];skipped=[]
    # .git 的压缩对象已在上方解压扫描；其配置和日志在此单独扫描。
    release_set=set(release)
    for folder,dirs,files in os.walk(ROOT,followlinks=False):
        base=Path(folder)
        dirs[:]=[x for x in dirs if not (base/x).is_symlink()]
        for name in files:
            p=base/name;rel=p.relative_to(ROOT).as_posix()
            if rel in release_set or rel.startswith('.git/objects/') or rel=='.git/index':continue
            if p.is_symlink() or not p.resolve().is_relative_to(ROOT):skipped.append(rel);continue
            group=rel.split('/')[0];ignored[group]+=1
            try:
                hits=findings(p.read_bytes())
            except OSError:
                skipped.append(rel);continue
            if hits:
                ignored_hits.update(hits);ignored_files.append({'file':rel,'hits':hits})
    result={'date':datetime.now(timezone.utc).isoformat(),'release_files':len(release),'staged_files':len(index_paths),'git_objects':dict(object_counts),'working_tree_candidates':work,'staged_candidates':staged,'git_object_candidates':objects,'ignored_file_counts':dict(ignored),'ignored_pattern_counts':dict(ignored_hits),'blocked_artifacts':disallowed,'links':links,'unread_files':skipped}
    (OUT/'privacy-full.json').write_text(json.dumps(dict(result,ignored_candidates=ignored_files),ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'release-paths.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
    return int(bool(work or staged or objects or disallowed or links or skipped))

if __name__=='__main__':sys.exit(main())
