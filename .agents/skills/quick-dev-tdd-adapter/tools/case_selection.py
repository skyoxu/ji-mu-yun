"""ADR-0041: conservative, import-free pytest selection with diagnostic reasons."""
from __future__ import annotations
import ast
from pathlib import Path
from runtime_evidence import safe_relative


class Unsupported(ValueError):
    pass


def literal_nodes(root, targets, required):
    """Narrow only a complete static mapping, preserving declared selector bounds."""
    nodes, covered = [], set()
    try:
        if not required:
            raise Unsupported('no-required-assertions')
        for target in targets:
            ref, separator, explicit = target.partition('::')
            path = Path(root) / safe_relative(ref)
            if path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()):
                raise Unsupported('unsafe-target')
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            constants = {n.targets[0].id: n.value.value for n in tree.body
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}

            def marker_ids(node):
                result = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == 'cer_assertion':
                        for arg in child.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                result.add(arg.value)
                            elif isinstance(arg, ast.Name) and arg.id in constants:
                                result.add(constants[arg.id])
                            else:
                                raise Unsupported('dynamic-marker')
                return result

            def functions(body, prefix='', inherited=frozenset()):
                for n in body:
                    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'pytestmark' for t in n.targets):
                        raise Unsupported('module-or-class-pytestmark')
                    if isinstance(n, ast.ClassDef) and n.name.startswith('Test'):
                        class_path = prefix + n.name
                        if explicit and not (explicit == class_path or explicit.startswith(class_path+'::')):
                            continue
                        if n.bases or n.keywords:
                            raise Unsupported('inherited-test-class')
                        marks = set(inherited)
                        for d in n.decorator_list:
                            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == 'parametrize':
                                raise Unsupported('class-parametrization')
                            marks.update(marker_ids(d))
                        yield from functions(n.body, class_path+'::', marks)
                    elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_'):
                        name = prefix+n.name
                        if explicit and not (name == explicit or explicit.startswith(name+'[') or name.startswith(explicit+'::')):
                            continue
                        yield n, name, set(inherited)

            for function, name, marks in functions(tree.body):
                parameters = []
                for d in function.decorator_list:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == 'parametrize':
                        parameters.append(d)
                    else:
                        marks.update(marker_ids(d))
                base = ref+'::'+name
                cases = []
                if not parameters:
                    cases.append((base, marks))
                else:
                    if len(parameters) != 1:
                        raise Unsupported('stacked-parametrization')
                    param = parameters[0]
                    if len(param.args) != 2 or not isinstance(param.args[1], (ast.List, ast.Tuple)):
                        raise Unsupported('dynamic-parameter-values')
                    if any(k.arg != 'ids' for k in param.keywords):
                        raise Unsupported('unsupported-parametrize-option')
                    explicit_ids = next((k.value for k in param.keywords if k.arg == 'ids'), None)
                    if explicit_ids is not None:
                        try: explicit_ids = ast.literal_eval(explicit_ids)
                        except (ValueError, TypeError): raise Unsupported('dynamic-parameter-ids')
                        if not isinstance(explicit_ids, (list, tuple)) or len(explicit_ids) != len(param.args[1].elts) or any(not isinstance(v,str) or not v for v in explicit_ids):
                            raise Unsupported('unsupported-explicit-ids')
                    seen = set()
                    for i, row in enumerate(param.args[1].elts):
                        row_marks = marker_ids(row)
                        case_id = explicit_ids[i] if explicit_ids is not None else None
                        if isinstance(row, ast.Call) and isinstance(row.func, ast.Attribute) and row.func.attr == 'param':
                            own_id = next((k.value for k in row.keywords if k.arg == 'id'), None)
                            if own_id is not None:
                                if not isinstance(own_id, ast.Constant) or not isinstance(own_id.value, str):
                                    raise Unsupported('dynamic-case-id')
                                case_id = own_id.value
                            values = row.args
                        else:
                            # Closed literals cannot conceal dynamic CER markers.
                            try: ast.literal_eval(row)
                            except (ValueError, TypeError): raise Unsupported('dynamic-parameter-row')
                            values = [row]
                        if not ((marks | row_marks) & required):
                            continue
                        if case_id is None:
                            if len(values)==1 and isinstance(values[0],ast.Constant) and isinstance(values[0].value,str):
                                case_id=values[0].value
                            else:
                                raise Unsupported('implicit-parameter-id')
                        if not case_id.isascii() or case_id in seen or any(c in case_id for c in '[]\\\n\r'):
                            raise Unsupported('ambiguous-parameter-id')
                        seen.add(case_id)
                        cases.append((base+'['+case_id+']',marks | row_marks))
                for node, assertions in cases:
                    if separator and not (node == target or node.startswith(target+'[') or node.startswith(target+'::')):
                        continue
                    if assertions & required:
                        if node not in nodes: nodes.append(node)
                        covered.update(assertions & required)
        if covered != required:
            raise Unsupported('incomplete-assertion-mapping')
        return nodes, 'complete-static-case-mapping'
    except (OSError, SyntaxError, UnicodeError, ValueError, TypeError) as exc:
        return None, str(exc)


def selection_report(runner, semantic, slice_id):
    import json
    bundle = json.loads(semantic.read_text(encoding='utf-8'))
    full, _, _ = runner._descriptor_inputs(bundle, semantic.parent, slice_id, resolve_literal=False)
    selected, _, _ = runner._descriptor_inputs(bundle, semantic.parent, slice_id)
    required = {s for a in bundle['acceptances'] if a['acceptance_id'] in runner._slice(bundle,slice_id)['acceptance_ids'] for s in a['assertion_ids']}
    reason = 'non-static-pytest-command'
    if '-m' in full and full[full.index('-m')+1:full.index('-m')+2] == ['pytest']:
        _, reason = literal_nodes(runner.ROOT, [v for v in full[full.index('-m')+2:] if v != '-q'],required)
    commands = runner._agent_context(semantic.parent,slice_id)['validation_commands']
    return {'schema':'quick-dev.selection-inspection.v1','slice_id':slice_id,'selected_argv':selected,
            'terminal_argv':full,'required_regression_commands':commands,'reason':reason,
            'duplicate_declared_commands':len(commands)-len({tuple(c) for c in commands}),
            'tests_executed':False,'writes_performed':False,'authorizes':[]}
