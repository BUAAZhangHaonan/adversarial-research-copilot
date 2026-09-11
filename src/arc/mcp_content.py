"""Preserve document coordinates while reusing MCP text pages as source evidence."""
import re


def decoded_page(body, arguments, kind):
    if kind == 'paper':
        text = body.get('markdown') or ''
        span = body.get('range') or {}
        start = span.get('start', 0)
        end = span.get('end', start + len(text))
        identity = body.get('document_id')
        revision = body.get('document_revision')
        representation = f'scholaranalysis:{identity}:{revision}:{body.get("mode", "text")}'
    else:
        text = body.get('text') or ''
        start = body.get('offset', arguments.get('offset', 0))
        end = start + len(text)
        identity = body.get('resource_id')
        revision = body.get('version')
        representation = f'webresearch:{identity}:{revision}'
    total = body.get('total_chars')
    if (not isinstance(text, str) or type(start) is not int or type(end) is not int
            or type(total) is not int or start < 0 or end != start + len(text) or end > total):
        raise ValueError('MCP_TEXT_RANGE_INVALID')
    if not identity or not revision:
        raise ValueError('MCP_TEXT_REVISION_MISSING')
    return dict(content=text, content_start_char=start, content_complete=start == 0 and end == total,
                content_total_chars=total, representation_id=representation)


def extend_cached_page(store, item):
    """Only contiguous, agreeing text extends a prefix. Gaps remain explicit fragments."""
    start = item.get('content_start_char', 0)
    representation = item.get('representation_id')
    if start == 0 or not representation:
        return item
    previous = store.source_by_representation(representation)
    if previous is not None and previous.content_path:
        cached = store.read_artifact(previous.content_path)
        if (previous.content_start_char == 0 and start <= len(cached)
                and previous.content_total_chars == item['content_total_chars']):
            text = item['content']
            overlap = min(len(cached) - start, len(text))
            if cached[start:start + overlap] != text[:overlap]:
                raise ValueError('MCP_PAGE_CONTENT_CHANGED_WITHOUT_REVISION')
            joined = cached + text[overlap:]
            return {**item, 'content': joined, 'content_start_char': 0,
                    'content_complete': len(joined) == item['content_total_chars']}
    return {**item, 'representation_id': representation + f':fragment:{start}', 'content_complete': False}


def paper_title(paper, text, identity, url):
    if (paper.get('title') or '').strip():
        return paper['title']
    if text and identity and re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-zA-Z][a-zA-Z.\-]*/\d{7})v[1-9]\d*', identity):
        return 'arXiv ' + identity
    if text and url and not identity:
        heading = re.search(r'^#\s+(.{1,300})$', text, re.MULTILINE)
        return heading[1].strip() if heading else 'Document: ' + url
    return None
