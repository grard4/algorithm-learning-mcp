import pytest
import zstandard
import sync
import input_limits as limits
from kb import KBError


@pytest.mark.parametrize('content', [b'', b'x'])
def test_stops_before_decoding_excess_frames(tmp_path, monkeypatch, content):
    frame = zstandard.ZstdCompressor().compress(content)
    path = tmp_path/'many.zst'
    path.write_bytes(frame * 10000)
    monkeypatch.setattr(limits, 'EVENTS', 3)
    real = zstandard.ZstdDecompressor
    seen = []

    class CountingDecoder:
        def __init__(self, **kwargs):
            self.decoder = real(**kwargs)

        def stream_reader(self, source, **kwargs):
            with source.getbuffer() as buffer:
                length = len(buffer)
            seen.append(length)
            assert len(seen) <= 3, 'decoded an over-budget frame'
            assert length == len(frame), 'first decoder received unchecked frames'
            return self.decoder.stream_reader(source, **kwargs)

        def decompressobj(self):
            pytest.fail('second unbounded decompression pass')

    monkeypatch.setattr(sync.zstandard, 'ZstdDecompressor', CountingDecoder)
    with pytest.raises(KBError) as exc:
        sync.read_bytes(path)
    assert exc.value.code == 'TOO_LARGE'
    assert len(seen) == 3


@pytest.mark.parametrize('count', [1, 2, 3])
def test_legal_frame_boundary(tmp_path, monkeypatch, count):
    monkeypatch.setattr(limits, 'EVENTS', 3)
    path = tmp_path/'legal.zst'
    path.write_bytes(zstandard.ZstdCompressor(write_checksum=True).compress(b'abc') * count)
    assert sync.read_bytes(path) == b'abc' * count


@pytest.mark.parametrize('kind', ['truncated', 'invalid', 'mixed', 'output', 'skippable', 'truncated_skip'])
def test_invalid_and_resource_boundaries(tmp_path, monkeypatch, kind):
    frame = zstandard.ZstdCompressor().compress(b'abc' * 1000)
    skip = (0x184D2A50).to_bytes(4, 'little') + (2).to_bytes(4, 'little') + b'ok'
    data = {'truncated': frame[:-1], 'invalid': b'garbage', 'mixed': frame + b'garbage',
            'output': frame, 'skippable': skip + frame, 'truncated_skip': skip[:-1]}[kind]
    path = tmp_path/'input.zst'
    path.write_bytes(data)
    if kind == 'output':
        monkeypatch.setattr(limits, 'DECOMPRESSED_BYTES', 2999)
    if kind == 'skippable':
        assert sync.read_bytes(path) == b'abc' * 1000
    else:
        with pytest.raises(KBError) as exc:
            sync.read_bytes(path)
        assert exc.value.code == ('TOO_LARGE' if kind == 'output' else 'INVALID_LOG')
