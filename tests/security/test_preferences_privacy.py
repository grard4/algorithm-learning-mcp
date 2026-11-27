import os
import preferences


def test_private_path_not_returned(tmp_path,monkeypatch):
    path=tmp_path/'private-user-name.md'
    path.write_text('synthetic preference',encoding='utf-8')
    monkeypatch.setenv('ALGORITHM_PREFERENCES',str(path))
    result=preferences.read_preferences()
    assert result['text']=='synthetic preference'
    assert 'private-user-name' not in str(result)


def test_same_size_mtime_replacement_reloads(tmp_path,monkeypatch):
    path=tmp_path/'preferences.md'
    path.write_text('first',encoding='utf-8')
    monkeypatch.setenv('ALGORITHM_PREFERENCES',str(path))
    assert preferences.read_preferences()['text']=='first'
    stamp=path.stat()
    path.write_text('other',encoding='utf-8')
    os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    assert preferences.read_preferences()['text']=='other'


def test_stat_permission_error_is_sanitized(monkeypatch):
    class Unreadable:
        def stat(self):raise PermissionError('private-location')
    monkeypatch.setattr(preferences,'preference_path',lambda:Unreadable())
    result=preferences.read_preferences()
    assert result['status']=='unavailable'
    assert 'private-location' not in str(result)
