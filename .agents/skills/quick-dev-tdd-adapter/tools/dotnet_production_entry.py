"""ADR-0041: bounded static .NET binding for pytest RED admission.

This does not execute .NET, infer a test outcome, or replace CER/TRX assertions.
Only literal shell-free dotnet test calls to a real test project and a frozen
C# test source calling an actual declared owner are supported.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from runtime_evidence import safe_relative


def _file(root: Path, ref: str) -> Path:
    path = root / safe_relative(ref)
    if path.is_symlink() or not path.is_file():
        raise ValueError(".NET binding file missing or unsafe: " + ref)
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(".NET binding path escapes repository")
    return resolved


def _code(source: str) -> str:
    source = re.sub(r'(?s)(?P<q>"{3,}).*?(?P=q)', ' ', source)
    return re.sub(r'/\*.*?\*/|//[^\n]*|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', source, flags=re.S)


def _dotnet_calls(tree):
    modules, aliases = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.asname or a.name for a in node.names if a.name == 'subprocess')
        elif isinstance(node, ast.ImportFrom) and node.module == 'subprocess':
            aliases.update(a.asname or a.name for a in node.names if a.name == 'run')
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        fn = node.func
        supported = (isinstance(fn, ast.Name) and fn.id in aliases) or (
            isinstance(fn, ast.Attribute) and fn.attr == 'run'
            and isinstance(fn.value, ast.Name) and fn.value.id in modules)
        if not supported or not isinstance(node.args[0], (ast.List, ast.Tuple)):
            continue
        if not any(k.arg == 'shell' and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords):
            continue
        argv = [x.value if isinstance(x, ast.Constant) and isinstance(x.value, str) else None for x in node.args[0].elts]
        if len(argv) < 5 or argv[:2] != ['dotnet', 'test'] or not argv[2] or not argv[2].endswith('.csproj'):
            continue
        if argv.count('--filter') != 1 or argv.count('--logger') != 1:
            continue
        i, j = argv.index('--filter'), argv.index('--logger')
        if i+1 >= len(argv) or j+1 >= len(argv) or not argv[i+1] or not argv[j+1]:
            continue
        selector = argv[i+1]
        if not selector.startswith('FullyQualifiedName=') or not re.fullmatch(r'[A-Za-z_][\w.]*', selector.split('=', 1)[1]):
            continue
        if argv[j+1] != 'trx' and not argv[j+1].startswith('trx;'):
            continue
        yield argv[2], selector.split('=', 1)[1]


def _project_owners(root, project_ref, owners):
    project = _file(root, project_ref)
    try:
        xml = ET.parse(project).getroot()
    except ET.ParseError as exc:
        raise ValueError('.NET test project is not valid XML') from exc
    tags = [(x.tag.rsplit('}', 1)[-1], x) for x in xml.iter()]
    if not any(tag == 'IsTestProject' and (node.text or '').strip().lower() == 'true' for tag, node in tags):
        return []
    references = []
    for tag, node in tags:
        if tag != 'ProjectReference':
            continue
        raw = node.get('Include', '').replace('\\', '/')
        candidate = project.parent / raw
        target = candidate.resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError('.NET project reference escapes repository')
        if target.is_file() and not candidate.is_symlink():
            references.append(target.parent)
    result = []
    for owner in owners:
        if not owner.endswith('.cs'):
            continue
        path = _file(root, owner)
        if not any(path.is_relative_to(folder) for folder in references):
            continue
        code = _code(path.read_text(encoding='utf-8'))
        ns = re.search(r'\bnamespace\s+([\w.]+)', code)
        names = re.findall(r'\b(?:class|struct|record)\s+(?:(?:class|struct)\s+)?([A-Za-z_]\w*)', code)
        for name in names:
            result.append((owner, ns.group(1) if ns else '', name))
    return result


def _test_calls_owner(code, namespace, name):
    qualified = re.escape(namespace + '.' + name) if namespace else re.escape(name)
    imported = not namespace or bool(re.search(r'\busing\s+'+re.escape(namespace)+r'\s*;', code))
    type_pattern = '(?:'+qualified+('|' + re.escape(name) if imported else '')+')'
    if re.search(r'\b(?:class|struct|record)\s+'+re.escape(name)+r'\b', code):
        return False
    if re.search(r'\bnew\s+'+type_pattern+r'\s*\(', code) or re.search(r'\b'+type_pattern+r'\s*\.\s*\w+\s*\(', code):
        return True
    return name == 'Program' and bool(re.search(r'\bWebApplicationFactory\s*<\s*'+type_pattern+r'\s*>', code)) and bool(re.search(r'\bCreate(?:Default)?Client\s*\(', code))


def dotnet_bindings(*, workspace, selected, parsed):
    owners = selected.get('production_owners', [])
    refs = [p for p in selected.get('execution_snapshot_paths', []) if p.endswith('.cs') and p not in owners]
    bindings = []
    for py_ref, _source, tree in parsed:
        for project_ref, fqn in _dotnet_calls(tree):
            project = _file(workspace, project_ref)
            parts = fqn.rsplit('.', 2)
            if len(parts) != 3:
                continue
            namespace, cls, method = parts
            production = _project_owners(workspace, project_ref, owners)
            for ref in refs:
                path = _file(workspace, ref)
                if not path.is_relative_to(project.parent):
                    continue
                code = _code(path.read_text(encoding='utf-8'))
                if not re.search(r'\bnamespace\s+'+re.escape(namespace)+r'\s*[;{]', code):
                    continue
                if not re.search(r'\bclass\s+'+re.escape(cls)+r'\b', code):
                    continue
                if not re.search(r'\[\s*(?:Fact|Theory)(?:\s*\([^\]]*\))?\s*\][\s\S]{0,300}?\b'+re.escape(method)+r'\s*\(', code):
                    continue
                if re.search(r'\bAssert\.(?:True\s*\(\s*false\b|False\s*\(\s*true\b|Fail\s*\()', code):
                    raise ValueError('.NET test contains unconditional failure: '+ref)
                for owner, owner_ns, name in production:
                    if _test_calls_owner(code, owner_ns, name):
                        bindings.append({'production_owner':owner,'module':owner_ns+'.'+name,'test_ref':py_ref,'dotnet_test_ref':ref,'test_project':project_ref,'fully_qualified_name':fqn})
    return bindings
