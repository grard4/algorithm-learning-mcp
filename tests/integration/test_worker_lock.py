import subprocess
import sys
from pathlib import Path
from sync import acquire_worker_lock


def test_lock_excludes_other_process_then_releases(tmp_path):
    path=tmp_path/'worker.lock'
    first=acquire_worker_lock(path)
    assert first is not None
    code="from sync import acquire_worker_lock; import sys; h=acquire_worker_lock(sys.argv[1]); print(h is None)"
    try:
        result=subprocess.run([sys.executable,'-c',code,str(path)],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=30)
        assert result.returncode==0 and result.stdout.strip()=='True',result.stderr
    finally:
        first.close()
    second=acquire_worker_lock(path)
    assert second is not None
    second.close()
