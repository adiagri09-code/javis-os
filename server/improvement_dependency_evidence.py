"""Host-private declared-reference evidence from the real bound context manifest.

This is not a grant parser or a complete executable/runtime dependency proof.
Only the semantic service supplies its verified host binding; HTTP/model JSON
must never be accepted as this capture. No discovered path expands that grant.
"""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

import improvement_store as IM
from improvement_cases import output_path
from improvement_skill_patch import reference_inventory
from improvement_trial_context import ContextSource

_LINK = re.compile(r'\]\(([^\s)#]+)(?:#[^\s)]*)?\)')
_EXECUTABLE = {'.py', '.sh', '.ps1', '.exe', '.bat', '.cmd', '.js', '.mjs', '.cjs'}


def _references(raw):
    refs = set(reference_inventory(raw))
    for item in _LINK.findall(raw.decode('utf-8')):
        if '://' not in item and not item.startswith(('mailto:', 'data:')):
            refs.add(item)
    return sorted(refs)


def _key(path):
    return os.path.normcase(str(path)).replace('\\', '/')


def dependency_evidence(capture, canonical_ref, before, after):
    canonical_ref = output_path(canonical_ref)
    roots = _references(before)
    if _references(after) != roots:
        raise ValueError('semantic_dependency_inventory_changed')
    granted = []
    for record in capture['sources']:
        if capture['version'] == 1:
            locator = {key: record[key] for key in ('root', 'relative')}
        elif record.get('kind') == 'file' and record.get('role') == 'protected' and isinstance(record.get('projection'), str):
            locator = record['locator']
        else:
            continue  # Metadata/discovery grants do not grant unprojected file bodies.
        if record['present']:
            granted.append((record, locator))
    nodes, edges, unresolved, active = {}, [], [], set()
    executable = False
    base = PurePosixPath(canonical_ref).parent

    def visit(ref, parent, origin):
        nonlocal executable
        if len(nodes) + len(unresolved) >= 1000:
            raise ValueError('semantic_dependency_graph_too_large')
        normalized = ref.replace('\\', '/')
        names = {_key(normalized), _key(base / normalized), _key(parent / normalized)}
        matches = [(record, locator) for record, locator in granted
            if _key(locator['relative']) in names or _key(Path(locator['root']) / locator['relative']) in names]
        if len(matches) != 1:
            unresolved.append({'reference': ref, 'from': origin, 'reason': 'dependency_ungranted_or_ambiguous'})
            return
        record, locator = matches[0]
        identifier = record['ref']
        edges.append({'from': origin, 'to': identifier})
        if identifier in active:
            unresolved.append({'reference': ref, 'from': origin, 'reason': 'dependency_cycle'})
            return
        if identifier in nodes:
            return
        # Import via module so the same real stable-reader boundary remains testable.
        import improvement_trial_context as context
        from improvement_trial_dashboard import _protected_authority
        root, relative = Path(locator['root']), output_path(locator['relative'])
        try:
            authority = _protected_authority(root, relative)
            observed, text = context._read(ContextSource(identifier, root, relative, record['required']))
            if (observed['hash'] != record['hash'] or observed['identity'] != record['identity']
                    or _protected_authority(root, relative) != authority or text is None):
                raise IM.ConflictError('semantic_dependency_source_changed')
        except (ValueError, OSError, PermissionError) as error:
            raise IM.ConflictError('semantic_dependency_source_changed') from error
        nodes[identifier] = {'ref': identifier, 'relative': relative, 'hash': observed['hash'],
            'identity': observed['identity'], 'authority_hash': IM._hash(authority), 'content': text}
        executable |= PurePosixPath(relative).suffix.lower() in _EXECUTABLE
        active.add(identifier)
        for nested in _references(text.encode('utf-8')):
            visit(nested, PurePosixPath(relative).parent, identifier)
        active.remove(identifier)

    for ref in roots:
        visit(ref, base, 'candidate')
    return {'version': 1, 'verdict': 'unknown' if unresolved or executable else 'pass',
        'coverage': 'declared_reference_graph', 'runtime': 'unsupported_executable_dependency' if executable else 'not_qualified_by_this_check',
        'nodes': [nodes[key] for key in sorted(nodes)], 'edges': edges, 'unresolved': unresolved,
        'references': roots, 'manifest_hash': capture['plan_hash']}
