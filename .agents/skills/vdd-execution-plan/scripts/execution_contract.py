"""ADR-0041: shared path and ownerless-guard rules, without owner inference."""
from pathlib import PurePosixPath


def selector_file_path(value):
    """A pytest node is a selector; only its file belongs in path sets."""
    return value.split("::", 1)[0]


def is_test_path(value):
    if not isinstance(value, str) or "\\" in value or ":" in value:
        return False
    parts = PurePosixPath(value).parts
    if not parts or value.startswith("/") or ".." in parts:
        return False
    return (value.startswith(("tests/", "scripts/sc/tests/", "PhaseA.Platform.Tests/"))
            or (value.startswith(".agents/skills/") and "tests" in parts[3:-1]))


def test_only_surface(item, failures):
    """Execution half of the guard rule; semantic kind is checked separately."""
    paths = [*item.get("allowed_write_paths", []), *item.get("planned_new_files", []),
             *item.get("execution_snapshot_paths", []),
             *(item.get("rollback_scope") or {}).get("production_paths", [])]
    return bool(item.get("production_owners") == [] and item.get("allowed_write_paths")
                and paths and all(is_test_path(p) for p in paths)
                and all(f.get("failure_family") != "expected-red" for f in failures))


def ownerless_guard(item, obligations, failures):
    return bool(test_only_surface(item, failures) and obligations
                and all(o.get("obligation_kind") in {"governance", "constraint"}
                        for o in obligations))


def derive_slice_dependencies(obligations, slices):
    """ADR-0041: derive only exact V1-ID edges, never prose or shared owners."""
    records = {item['obligation_id']: item for item in obligations}
    if len(records) != len(obligations):
        raise ValueError('dependency:duplicate-obligation')
    owners = {}
    graph = {}
    for item in slices:
        sid = item['slice_id']
        if sid in graph:
            raise ValueError('dependency:duplicate-slice')
        graph[sid] = set()
        for oid in item['obligation_ids']:
            if oid not in records or oid in owners:
                raise ValueError('dependency:invalid-obligation-membership')
            owners[oid] = sid
    obligation_graph = {oid: set() for oid in owners}
    for oid, sid in owners.items():
        dependencies = records[oid].get('depends_on', [])
        if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
            raise ValueError('dependency:invalid-v1-edges')
        for dep in dependencies:
            if not dep.startswith('O-'):
                continue
            if dep not in owners:
                raise ValueError('dependency:target-not-in-plan:' + dep)
            obligation_graph[oid].add(dep)
            if owners[dep] != sid:
                graph[sid].add(owners[dep])
    def acyclic(edges):
        visiting, visited = set(), set()
        def visit(node):
            if node in visiting:
                raise ValueError('dependency:cycle')
            if node in visited:
                return
            visiting.add(node)
            for dep in edges[node]:
                visit(dep)
            visiting.remove(node)
            visited.add(node)
        for node in edges:
            visit(node)
    acyclic(obligation_graph)
    acyclic(graph)
    return {sid: sorted(deps) for sid, deps in graph.items()}


def bind_slice_dependencies(slices, expected):
    """ADR-0041: fill omitted fields only; explicit empty/wrong edges reject."""
    if len(slices) != len(expected) or {s['slice_id'] for s in slices} != set(expected):
        raise ValueError('dependency:slice-domain-changed')
    for item in slices:
        wanted = expected[item['slice_id']]
        if 'depends_on' in item:
            actual = item['depends_on']
            if (not isinstance(actual, list) or any(not isinstance(v, str) for v in actual)
                    or len(actual) != len(set(actual)) or sorted(actual) != wanted):
                raise ValueError('dependency:explicit-edges-mismatch:' + item['slice_id'])
    # Validate the entire set before filling any historical omission.
    for item in slices:
        if 'depends_on' not in item:
            item['depends_on'] = list(expected[item['slice_id']])
    return slices


def dependency_revision_impact(before, after, slices):
    """ADR-0041: validate both explicit graphs and close their downstream union."""
    def strict(records):
        ids = [item['obligation_id'] for item in records]
        if len(ids) != len(set(ids)):
            raise ValueError('dependency:duplicate-obligation')
        for item in records:
            edges = item.get('depends_on', [])
            if (not isinstance(edges, list) or any(not isinstance(dep, str) for dep in edges)
                    or len(edges) != len(set(edges)) or not set(edges) <= set(ids)):
                raise ValueError('dependency:invalid-revision-edges')
        return derive_slice_dependencies(records, slices)
    old, new = strict(before), strict(after)
    prior = {o['obligation_id']: o for o in before}
    current = {o['obligation_id']: o for o in after}
    if set(prior) != set(current):
        raise ValueError('dependency:obligation-domain-changed')
    changed = sorted(oid for oid in prior if set(prior[oid].get('depends_on', [])) != set(current[oid].get('depends_on', [])))
    owners = {oid: s['slice_id'] for s in slices for oid in s['obligation_ids']}
    if not set(changed) <= owners.keys():
        raise ValueError('dependency:changed-obligation-has-no-slice')
    affected = {owners[oid] for oid in changed}
    while True:
        expanded = affected | {sid for sid in old if (set(old[sid]) | set(new[sid])) & affected}
        if expanded == affected:
            break
        affected = expanded
    return {'changed_obligation_ids': changed, 'old_slice_dependencies': old,
            'new_slice_dependencies': new, 'affected_slices': sorted(affected)}
