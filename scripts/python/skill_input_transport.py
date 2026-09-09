"""Bounded deterministic pages and identity-bound continuations (ADR-0060)."""
from __future__ import annotations
try:
    from .skill_input_protocol import digest, identity, check_hash
except ImportError:
    from skill_input_protocol import digest, identity, check_hash


def plan_transport(page_bytes, max_snapshot_bytes, *, content_hash, selection_hash=None, max_retries=2):
    for value in (page_bytes, max_snapshot_bytes):
        if type(value) is not int or value <= 0:
            raise ValueError('transport budget must be a positive integer')
    if type(max_retries) is not int or not 0 <= max_retries <= 10:
        raise ValueError('retry budget is invalid')
    check_hash(content_hash)
    check_hash(selection_hash or content_hash)
    return {'page_bytes': page_bytes, 'max_snapshot_bytes': max_snapshot_bytes,
            'pages': (max_snapshot_bytes + page_bytes - 1) // page_bytes,
            'content_hash': content_hash, 'selection_hash': selection_hash or content_hash,
            'next_offset': 0, 'max_retries': max_retries}


def resume_transport(plan, *, content_hash, selection_hash=None):
    if not isinstance(plan, dict) or plan.get('content_hash') != content_hash or plan.get('selection_hash') != (selection_hash or content_hash):
        raise ValueError('stale continuation')
    return {**plan, 'resumed': True}


def pages_for(sources, *, page_bytes, max_snapshot_bytes):
    if type(page_bytes) is not int or page_bytes < 4:
        raise ValueError('page budget cannot preserve UTF-8')
    if type(max_snapshot_bytes) is not int or max_snapshot_bytes <= 0:
        raise ValueError('snapshot budget is invalid')
    if sum(len(v) for v in sources.values()) > max_snapshot_bytes:
        raise ValueError('snapshot exceeds byte budget')
    pages = []
    for path, raw in sorted(sources.items()):
        raw.decode('utf-8')
        start, line = 0, 1
        while start < len(raw) or not raw and start == 0:
            end = min(start + page_bytes, len(raw))
            while end < len(raw) and end > start and raw[end] & 0xC0 == 0x80:
                end -= 1
            content = raw[start:end]
            pages.append({'source_path': path, 'source_sha256': digest(raw),
                          'start_byte': start, 'end_byte': end, 'start_line': line,
                          'end_line': line + content.count(b'\n'), 'content_sha256': digest(content)})
            if end == len(raw):
                break
            start, line = end, line + content.count(b'\n')
    return pages


def continuation(plan, pages, *, next_page=0, retry_count=0):
    if type(next_page) is not int or not 0 <= next_page <= len(pages):
        raise ValueError('invalid continuation offset')
    if type(retry_count) is not int or not 0 <= retry_count <= plan['max_retries']:
        raise ValueError('retry budget exhausted')
    return {'plan_hash': identity(plan), 'pages_hash': identity(pages),
            'next_page': next_page, 'retry_count': retry_count}


def validate_continuation(token, plan, pages):
    if not isinstance(token, dict) or token != continuation(plan, pages, next_page=token.get('next_page'), retry_count=token.get('retry_count')):
        raise ValueError('stale or conflicting continuation')
    return token['next_page']
