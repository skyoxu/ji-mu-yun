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
    paths = [relative(p).casefold() for p in changed_paths]
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
    # Validate the frozen envelope before recomputing derived freshness. Never
    # repair a failed preflight, forged hash, missing decision or widened scope.
    error = validate_context(context, require_selection=True)
    if error:
        raise ValueError('Knowledge context blocked: ' + error)
    preflight = context.get('preflight')
    if isinstance(preflight, dict) and ('knowledge_freshness' in preflight or 'catalog_failure_code' in preflight):
        prior = preflight.get('knowledge_freshness')
        if prior not in {'current', 'degraded'} or preflight.get('catalog_failure_code') != ('catalog_stale' if prior == 'degraded' else None):
            raise ValueError('Knowledge context blocked: preflight_catalog_freshness_invalid')
    freshness = validate_catalog_freshness(Path(repository_root))
    if freshness not in (None, 'catalog_stale'):
        raise ValueError('Knowledge publication blocked: ' + freshness)
    import copy
    successor = copy.deepcopy(context)
    if isinstance(successor.get('preflight'), dict):
        successor['preflight']['knowledge_freshness'] = 'degraded' if freshness == 'catalog_stale' else 'current'
        successor['preflight']['catalog_failure_code'] = freshness
        successor['preflight']['context_sha256'] = identity({k: v for k, v in successor.items() if k != 'preflight'})
    # Even a previously refreshed stale context must match today's published
    # catalog, policy, projection and read-set membership before rehashing bytes.
    error = validate_context(successor, repository_root=Path(repository_root), verify_catalog=True,
                             verify_sources=False, require_selection=True, require_catalog_membership=True)
    if error:
        raise ValueError('Knowledge context blocked: ' + error)
    before_sources = _accepted_sources(successor)
    refreshed = refresh_context_read_set(successor, Path(repository_root))
    error = validate_context(refreshed, repository_root=Path(repository_root), verify_catalog=True,
                             verify_sources=True, require_selection=True, require_catalog_membership=True)
    if error:
        raise ValueError('Knowledge source verification blocked: ' + error)
    if validate_catalog_freshness(Path(repository_root)) != freshness:
        raise ValueError('Knowledge publication changed during successor verification')
    return {'mode': 'locator', 'catalog_stale': freshness == 'catalog_stale',
            'source_refreshed': before_sources != _accepted_sources(refreshed),
            'context_hash': identity(refreshed), 'successor_context': refreshed}


def _accepted_sources(context):
    """Compare source bytes, not derived preflight fields or read-set spelling."""
    accepted = {(d['candidate']['path'], d['candidate']['source_sha256'])
                for d in context['decisions'] if d['decision'] == 'accepted'}
    return sorted((item['path'], item['source_sha256'])
                  for c in context['locator_result']['candidates']
                  if (c['path'], c['source_sha256']) in accepted
                  for item in c.get('read_set', [{'path': c['path'], 'source_sha256': c['source_sha256']}]))
