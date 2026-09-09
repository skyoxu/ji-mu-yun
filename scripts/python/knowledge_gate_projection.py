"""Independent execution/publication/review projection (ADR-0059/ADR-0060)."""
from __future__ import annotations
try:
    from .skill_input_protocol import relative
except ImportError:
    from skill_input_protocol import relative

KNOWLEDGE_PREFIXES = ('knowledge/', 'scripts/python/knowledge_', 'scripts/python/_knowledge_',
                      'scripts/python/prune_knowledge_', '.agents/skills/maintain-knowledge-base/')


def project_knowledge_gates(*, catalog_stale, read_set_same, source_bytes_same,
                            authority_same=True, publication_integrity_valid=True,
                            lkg_valid=True, required_sources_present=True, changed_paths=()):
    flags = (catalog_stale, read_set_same, source_bytes_same, authority_same,
             publication_integrity_valid, lkg_valid, required_sources_present)
    if any(type(v) is not bool for v in flags):
        raise ValueError('Knowledge gate facts must be boolean')
    paths = [relative(p) for p in changed_paths]
    self_change = any(p.startswith(KNOWLEDGE_PREFIXES) or p == 'scripts/python/knowledge_gate_projection.py' for p in paths)
    failure = next((code for valid, code in (
        (publication_integrity_valid, 'publication-integrity-failure'),
        (lkg_valid, 'invalid-lkg'), (required_sources_present, 'required-source-missing'),
        (authority_same, 'authority-drift'), (read_set_same, 'selection-drift')) if not valid), None)
    review = self_change or not authority_same or not read_set_same
    if failure:
        route = 'repair-required'
    elif self_change:
        route = 'review-required'
    elif not source_bytes_same:
        route = 'successor-refresh'
    elif catalog_stale:
        route = 'degraded-continuation'
    else:
        route = 'ready'
    return {'route': route, 'execution_allowed': not failure and not review,
            'publication_allowed': False,
            'publication_gate': 'blocked' if failure or review else 'explicit-publication-required',
            'review_required': review, 'failure': failure, 'authorizes': []}


def observe_knowledge(repository_root, freeze_path, *, selection_hash):
    """Derive gate facts from bound source data, never caller success flags.

    Direct-source mode is explicitly non-Knowledge authority. Locator mode
    reuses the existing publication/LKG and source verification implementation.
    Neither branch writes a Knowledge artifact.
    """
    from pathlib import Path
    try:
        from .skill_input_protocol import contained, digest, identity, read_json
    except ImportError:
        from skill_input_protocol import contained, digest, identity, read_json
    freeze_path = Path(freeze_path)
    freeze = read_json(freeze_path)
    if freeze.get('schema_version') == 'skill-input-direct-source-freeze.v2':
        if set(freeze) != {'schema_version', 'sourceSelectionHash', 'authorizes'} or freeze['authorizes'] != [] or freeze['sourceSelectionHash'] != selection_hash:
            raise ValueError('direct-source freeze selection mismatch')
        return {'mode': 'direct-sources', 'catalog_stale': False, 'source_refreshed': False, 'context_hash': identity(freeze)}
    if freeze.get('schema_version') not in {'jimuyun.vdd-knowledge-freeze.v1', 'jimuyun.knowledge-consumer-freeze.v1'} or freeze.get('authorizes') != []:
        raise ValueError('unsupported Knowledge freeze')
    context_path = contained(freeze_path.parent, freeze['context_path'])
    context_path.resolve().relative_to(Path(repository_root).resolve())
    raw = context_path.read_bytes()
    context = read_json(context_path)
    if digest(raw) != freeze['context_sha256']:
        raise ValueError('Knowledge freeze context hash mismatch')
    try:
        from .knowledge_context_validation import validate_context, validate_catalog_freshness, refresh_context_read_set
    except ImportError:
        from knowledge_context_validation import validate_context, validate_catalog_freshness, refresh_context_read_set
    error = validate_context(context, repository_root=Path(repository_root), verify_catalog=True, verify_sources=False, require_selection=True)
    if error:
        raise ValueError('Knowledge context blocked: ' + error)
    refreshed = refresh_context_read_set(context, Path(repository_root))
    error = validate_context(refreshed, repository_root=Path(repository_root), verify_catalog=True, verify_sources=True, require_selection=True)
    if error:
        raise ValueError('Knowledge source verification blocked: ' + error)
    freshness = validate_catalog_freshness(Path(repository_root))
    if freshness not in (None, 'catalog_stale'):
        raise ValueError('Knowledge publication blocked: ' + freshness)
    return {'mode': 'locator', 'catalog_stale': freshness == 'catalog_stale',
            'source_refreshed': identity(context) != identity(refreshed), 'context_hash': identity(refreshed)}
