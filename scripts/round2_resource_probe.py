"""Isolated resource probes. Each case runs in its own process and temporary DB."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CASES=('normalized_valid','normalized_count','normalized_bytes','normalized_total',
       'raw_file','decompressed','ratio','events','message','valid_compressed')


def peak_rss():
    if os.name=='nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                *[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
                   'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize
    import resource
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform=='darwin' else value*1024


def run_case(case):
    import zstandard
    import input_limits as lim
    from kb import KBError, now
    with tempfile.TemporaryDirectory(prefix='algorithm-round2-resource-') as temp:
        root=Path(temp)
        for key in list(os.environ):
            if key.startswith('ALGORITHM_'):del os.environ[key]
        os.environ.update(ALGORITHM_KB=str(root/'probe.sqlite3'),ALGORITHM_PREFERENCES=str(root/'missing'))
        import server
        import sync
        k=server.kb;k.register('Synthetic','','chat','Synthetic')
        snapshot=lambda:(k.rows('SELECT * FROM messages'),k.rows('SELECT * FROM archives'),k.rows('SELECT * FROM sync_state'),k.rows('SELECT * FROM updates'))
        before=snapshot();input_bytes=0;decoded_bytes=0;event_count=0
        if case.startswith('normalized'):
            m={'role':'user','content':'a'*lim.MESSAGE_BYTES,'timestamp':now()}
            messages=[m]*7
            if case=='normalized_count':messages=[dict(m,content='x')]*(lim.NORMALIZED_MESSAGES+1)
            elif case=='normalized_bytes':messages=[dict(m,content=m['content']+'a')]
            elif case=='normalized_total':messages=[m]*8
            input_bytes=len(json.dumps(messages).encode());event_count=len(messages)
            start=time.perf_counter()
            response=server.record_conversation_update('chat',messages,'probe')
            status='accepted' if response['ok'] else response['error']['code']
        else:
            path=root/'source.jsonl'
            if case=='raw_file':
                with path.open('wb') as f:f.truncate(lim.SOURCE_BYTES+1)
            elif case in ('decompressed','ratio'):
                path=root/'source.zst'
                if case=='decompressed':data=os.urandom(1024*1024)*33
                else:data=b'a'*(2*1024*1024)
                decoded_bytes=len(data);path.write_bytes(zstandard.ZstdCompressor().compress(data));del data
            else:
                event={'type':'session_meta','payload':{'id':'chat'}}
                text='x'*(lim.MESSAGE_BYTES+1) if case=='message' else 'proof'
                message={'type':'response_item','timestamp':now(),'payload':{'type':'message','role':'user','content':[{'type':'text','text':text}]}}
                lines=[json.dumps(event)]
                lines.extend([json.dumps(message)]*(lim.EVENTS if case=='events' else 1))
                data=('\n'.join(lines)+'\n').encode();event_count=len(lines);decoded_bytes=len(data)
                if case=='valid_compressed':path=root/'source.zst';path.write_bytes(zstandard.ZstdCompressor().compress(data))
                else:path.write_bytes(data)
                del lines,data
            input_bytes=path.stat().st_size
            if not decoded_bytes:decoded_bytes=input_bytes
            start=time.perf_counter()
            try:sync.sync_file(k,path);status='accepted'
            except KBError as exc:status=exc.code
        elapsed=time.perf_counter()-start
        same=snapshot()==before
        no_archive=not list((root/'archives').rglob('*.*'))
        expected_accept=case in ('normalized_valid','valid_compressed')
        assert (status=='accepted')==expected_accept,(case,status)
        if not expected_accept:assert same and no_archive,(case,same,no_archive)
        integrity=k.rows('PRAGMA integrity_check')[0]['integrity_check'];fk=k.rows('PRAGMA foreign_key_check')
        assert integrity=='ok' and not fk
        return dict(case=case,input_bytes=input_bytes,decompressed_bytes=decoded_bytes,events=event_count,
            elapsed_seconds=round(elapsed,6),peak_rss_bytes=peak_rss(),status=status,
            database_and_cursor_unchanged=same,no_archive_created=no_archive,integrity=integrity,foreign_key_errors=len(fk))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=CASES);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.case:print(json.dumps(run_case(args.case)))
    else:
        rows=[]
        for case in CASES:
            result=subprocess.run([sys.executable,__file__,'--case',case],cwd=ROOT,capture_output=True,text=True,timeout=60,check=True)
            rows.append(json.loads(result.stdout))
        report={'platform':sys.platform,'python':sys.version.split()[0],
            'memory_scope':'OS peak RSS for entire child, including interpreter imports and synthetic input creation; not a universal memory guarantee',
            'cases':rows}
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))
