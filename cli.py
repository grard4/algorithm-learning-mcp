import argparse,json,sys,contextlib
from pathlib import Path
from kb import KB,KBError

def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True)
 a=sub.add_parser('call');a.add_argument('tool');a.add_argument('--args-file',type=Path)
 a=sub.add_parser('backup');a.add_argument('path',type=Path)
 a=sub.add_parser('restore');a.add_argument('backup',type=Path);a.add_argument('destination',type=Path)
 a=sub.add_parser('verify');args=p.parse_args()
 if args.cmd=='call':
  import server
  allowed=set(server.TOOLS)
  if args.tool not in allowed:raise ValueError('未知工具')
  payload=json.loads(args.args_file.read_text(encoding='utf-8-sig')) if args.args_file else {}
  result=getattr(server,args.tool)(**payload)
 elif args.cmd=='backup':result={'backup':KB().backup(args.path)}
 elif args.cmd=='restore':
  import sqlite3,os,tempfile,uuid
  if args.destination.exists():raise ValueError('恢复必须指定不存在的新文件，避免覆盖正在运行的库')
  fd,temporary=tempfile.mkstemp(prefix='.restore-',dir=args.destination.parent)
  os.close(fd)
  try:
   with contextlib.closing(sqlite3.connect(args.backup.resolve().as_uri()+'?mode=ro',uri=True)) as src:
    if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or src.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('备份损坏或外键无效')
    with contextlib.closing(sqlite3.connect(temporary)) as dst:
     src.backup(dst)
     if dst.execute("SELECT 1 FROM sqlite_master WHERE name='r3_meta'").fetchone():
      import notifications
      dst.row_factory=sqlite3.Row
      notifications.health(dst)
      dst.execute('UPDATE r3_meta SET epoch=? WHERE singleton=1',(str(uuid.uuid4()),))
      dst.commit()
     if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or dst.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('恢复验证失败')
   os.link(temporary,args.destination)
  finally:
   os.unlink(temporary)
  result={'restored':str(args.destination),'activation':'验证后停止后台进程，并将 ALGORITHM_KB 指向恢复文件'}
 else:
  from kb import digest
  k=KB();bad=[]
  for a in k.rows('SELECT * FROM archives'):
   if digest(Path(a['path']).read_bytes())!=a['sha256']:bad.append(a['path'])
  result={'integrity':k.rows('PRAGMA integrity_check'),'foreign_keys':k.rows('PRAGMA foreign_key_check'),'bad_archives':bad}
 # JSON escapes preserve Unicode values even when a redirected console uses ASCII/cp1252.
 print(json.dumps(result,ensure_ascii=True,indent=2))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  from errors import error_response
  print(json.dumps(error_response(exc),ensure_ascii=True))
  sys.exit(1)
