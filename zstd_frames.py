"""Bounded frame slicing, without decompression or speculative frame decoding.

Wire format: facebook/zstd doc/zstd_compression_format.md (RFC 8878 section 3).
The zstandard 0.25.0 decoder remains authoritative for block contents/checksums.
Only one complete, counted frame is ever handed to stream_reader.
"""
from kb import KBError
import input_limits as limits


def frames(raw):
    pos = count = 0

    def require(end):
        if end > len(raw):
            raise KBError('INVALID_LOG', '压缩日志帧不完整')

    while pos < len(raw):
        if count >= limits.EVENTS:
            limits.too_large('压缩帧超过数量预算')
        count += 1
        start = pos
        require(pos + 4)
        magic = int.from_bytes(raw[pos:pos + 4], 'little')
        pos += 4
        if 0x184D2A50 <= magic <= 0x184D2A5F:
            require(pos + 4)
            length = int.from_bytes(raw[pos:pos + 4], 'little')
            pos += 4 + length
            require(pos)
        elif magic == 0xFD2FB528:
            require(pos + 1)
            descriptor = raw[pos]
            if descriptor & 0x08:
                raise KBError('INVALID_LOG', '压缩日志帧保留位无效')
            single = bool(descriptor & 0x20)
            size_flag = descriptor >> 6
            size_bytes = (1 if single else 0, 2, 4, 8)[size_flag]
            pos += 1 + (not single) + (0, 1, 2, 4)[descriptor & 3] + size_bytes
            require(pos)
            while True:
                require(pos + 3)
                header = int.from_bytes(raw[pos:pos + 3], 'little')
                last, kind, size = header & 1, (header >> 1) & 3, header >> 3
                if kind == 3 or size > 128 * 1024:
                    raise KBError('INVALID_LOG', '压缩日志块无效')
                pos += 3 + (1 if kind == 1 else size)
                require(pos)
                if last:
                    break
            if descriptor & 4:
                pos += 4
                require(pos)
        else:
            raise KBError('INVALID_LOG', '压缩日志帧标识无效')
        yield memoryview(raw)[start:pos]
