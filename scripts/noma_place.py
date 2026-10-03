#!/usr/bin/env python3
"""Read-only retrieval and byte-bound checks for agent-reviewed note placement.

Semantic extraction and comparison remain agent judgments. A successful check
never certifies source completeness or authorizes a policy/status change.
"""
import argparse
import json
import re
import sys
from datetime import datetime

import noma_lib as lib
from noma_policy import REGISTER, PolicyError, SignalParser, digest, members, payload_digest, read_bytes, unique_object

ACTIONS = ('create', 'merge', 'split', 'noop', 'review')
NOTE_PATH = re.compile(r'wiki/[a-z0-9]+(?:-[a-z0-9]+)*\.md')


def note_path(path):
    if not isinstance(path, str) or not NOTE_PATH.fullmatch(path):
        raise PolicyError('NOTE-PATH')
    return path


def corpus(root):
    directory = root / 'wiki'
    if directory.is_symlink():
        raise PolicyError('NOTE-PATH')
    return {note_path(f'wiki/{p.name}'): read_bytes(root, f'wiki/{p.name}')
            for p in sorted(directory.glob('*.md'))}


def headings(data):
    result, offset, fence = [], 0, None
    for line in data.decode('utf-8').splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None:
            match = re.match(r'^(#{1,6}) (.+?)\s*\n?$', line)
            if match:
                result.append((len(match.group(1)), match.group(2), offset))
        offset += len(line.encode('utf-8'))
    return result


def index_from_bytes(notes):
    idx = {}
    for path, data in sorted(notes.items()):
        text = data.decode('utf-8')
        fm = lib.parse_fm(text) or {}
        clean = lib.strip_code(text)
        try:
            links = lib.strip_code(section(data, 'Links').decode()).partition('\n')[2]
        except PolicyError:
            links = ''
        try:
            summary = lib.strip_code(section(data, 'Summary').decode()).partition('\n')[2]
        except PolicyError:
            summary = ''
        slug = path[5:-3]
        idx[slug] = {'fm': fm, 'tags': [],
                     'parents': lib.LINK_RE.findall(links),
                     'fields': {'slug': lib.fold_tr(slug),
                                'title': lib.fold_tr(fm.get('title', '').strip('"')),
                                'tags': lib.fold_tr(fm.get('tags', '')),
                                'summary': lib.fold_tr(summary),
                                'body': lib.fold_tr(clean)}}
        idx[slug]['tags'] = [t.strip().strip('"') for t in fm.get('tags', '').strip('[]').split(',')]
    return idx


def retrieve(notes, concepts, hub=None, limit=8):
    if (not isinstance(concepts, list) or not 2 <= len(concepts) <= 4
            or any(not isinstance(c, str) or not c.strip() for c in concepts)
            or not isinstance(limit, int) or not 1 <= limit <= 20):
        raise PolicyError('QUERY')
    idx = index_from_bytes(notes)
    if hub is not None and hub not in idx:
        raise PolicyError('HUB')
    slugs = lib.filter_wiki(idx, list(idx), hub=hub)
    terms = lib.search_terms(concepts)
    return [{'path': f'wiki/{slug}.md', 'score': score,
             'match': 'exact' if all(any(t in field for field in idx[slug]['fields'].values())
                                     for t in terms) else 'partial'}
            for score, slug in lib.rank_wiki(idx, slugs, concepts)[:limit]]


def review_digest(ticket):
    return payload_digest({k: v for k, v in ticket.items() if k not in ('pre_review', 'post_review')})


def section(data, heading):
    matches = [match for match in headings(data) if match[0] == 2]
    selected = [i for i, match in enumerate(matches) if match[1] == heading]
    if len(selected) != 1:
        raise PolicyError('SECTION')
    i = selected[0]
    end = matches[i + 1][2] if i + 1 < len(matches) else len(data)
    return data[matches[i][2]:end]


def transition(before, after):
    def fm(data):
        text = data.decode('utf-8')
        fields = lib.parse_fm(text)
        if fields is None:
            raise PolicyError('FRONTMATTER')
        keys = re.findall(r'^([A-Za-z_][\w-]*):', text.split('---', 2)[1], re.M)
        if len(set(keys)) != len(keys):
            raise PolicyError('DUPLICATE-FIELD')
        for key in ('title', 'type', 'stage', 'scope', 'created', 'updated'):
            if not fields.get(key):
                raise PolicyError('FRONTMATTER')
        for key, values in (('type', lib.TYPES), ('stage', lib.STAGES),
                            ('scope', lib.SCOPES), ('status', lib.STATUS)):
            if key in fields and fields[key].strip('"\'') not in values:
                raise PolicyError('ENUM')
        if fields.get('locked', 'false') not in ('true', 'false'):
            raise PolicyError('LOCK')
        stamps = {}
        for key in ('created', 'updated'):
            stamps[key] = datetime.fromisoformat(fields[key].strip('"\'').replace('Z', '+00:00'))
            if stamps[key].tzinfo is None:
                raise PolicyError('DATE')
        if stamps['updated'] < stamps['created']:
            raise PolicyError('DATE')
        structure = headings(data)
        if (len(structure) < 3 or structure[0][0] != 1
                or [h[:2] for h in structure[1:3]] != [(2, 'Links'), (2, 'Summary')]):
            raise PolicyError('STRUCTURE')
        return fields, stamps

    new, times = fm(after)
    if before is not None:
        old, previous = fm(before)
        if before != after:
            if old.get('locked') == 'true':
                raise PolicyError('LOCKED-TARGET')
            if any(old.get(key) != new.get(key) for key in ('created', 'status', 'locked')):
                raise PolicyError('IMMUTABLE-METADATA')
            if times['updated'] <= previous['updated']:
                raise PolicyError('UPDATED')


def check(ticket, root, post=False):
    """Check declared inventories, real retrieval, reviewed bytes and source links."""
    rules = []
    try:
        if type(ticket['version']) is not int or ticket['version'] != 1:
            raise PolicyError('VERSION')
        actual = corpus(root)
        baseline = dict(actual)
        planned = dict(actual)
        output_paths = set()
        for output in ticket['outputs']:
            path = note_path(output['path'])
            if path in output_paths:
                raise PolicyError('DUPLICATE-OUTPUT')
            output_paths.add(path)
            before = output['before'].encode('utf-8') if output['before'] is not None else None
            after = output['after'].encode('utf-8')
            transition(before, after)
            if post:
                if actual.get(path) != after:
                    rules.append('UNREVIEWED-OUTPUT')
                if before is None:
                    baseline.pop(path, None)
                else:
                    baseline[path] = before
            elif actual.get(path) != before:
                rules.append('STALE-TARGET')
            planned[path] = after
        if {p: digest(b) for p, b in baseline.items()} != ticket['corpus']:
            rules.append('STALE-CORPUS')
        if REGISTER in baseline:
            authority = set(members(baseline[REGISTER].decode('utf-8')))
            if output_paths & authority:
                rules.append('POLICY-AUTHORITY-REVIEW')

        units = {unit['id']: unit for unit in ticket['units']}
        if len(units) != len(ticket['units']) or not units:
            raise PolicyError('UNIT-INVENTORY')
        expected, provenance, source_sections = set(), set(), {}
        source_ids = set()
        external_sources = {}
        exception_spans = []
        for source in ticket['sources']:
            if source['id'] in source_ids:
                raise PolicyError('SOURCE-INVENTORY')
            source_ids.add(source['id'])
            if not source['unit_ids'] or not source['provenance_ids']:
                raise PolicyError('SOURCE-INVENTORY')
            path = source['path']
            if not isinstance(path, str) or not path.startswith(('raw/', 'wiki/', 'tmp/')):
                raise PolicyError('SOURCE-PATH')
            data = baseline[path] if path in baseline else read_bytes(root, path)
            if path not in baseline:
                external_sources[path] = digest(data)
            if digest(data) != source['sha256']:
                rules.append('STALE-SOURCE')
            expected.update(source['unit_ids'])
            provenance.update(source['provenance_ids'])
            end = 0
            for span in source['sections']:
                start, stop = span['start'], span['end']
                if (type(start) is not int or type(stop) is not int or start != end
                        or stop <= start or stop > len(data)):
                    raise PolicyError('SOURCE-SECTIONS')
                key = source['id'] + '.' + span['id']
                if key in source_sections or digest(data[start:stop]) != span['sha256']:
                    raise PolicyError('SOURCE-SECTIONS')
                ids = set(span['unit_ids'])
                if not ids and not span.get('reviewed_exception'):
                    rules.append('SECTION-UNMAPPED')
                if not ids and span.get('reviewed_exception'):
                    exception_spans.append(data[start:stop])
                if not ids <= set(source['unit_ids']):
                    raise PolicyError('UNIT-INVENTORY')
                source_sections[key] = ids
                end = stop
            if end != len(data):
                rules.append('SOURCE-INVENTORY-INCOMPLETE')
            represented = set().union(*(source_sections[source['id'] + '.' + part['id']]
                                        for part in source['sections']))
            if represented != set(source['unit_ids']):
                rules.append('SECTION-UNMAPPED')
        if expected != set(units):
            rules.append('EXTRACTION-INCOMPLETE')
        for key, unit in units.items():
            if not unit.get('topic') or not unit.get('purpose') or not unit.get('source_sections'):
                rules.append('EXTRACTION-INCOMPLETE')
            if any(key not in source_sections.get(ref, set()) for ref in unit['source_sections']):
                rules.append('SOURCE-UNIT-MISMATCH')
        for ref, ids in source_sections.items():
            if any(ref not in units.get(key, {}).get('source_sections', []) for key in ids):
                rules.append('SOURCE-UNIT-MISMATCH')

        queries = {}
        for run in ticket['retrieval']:
            actual_hits = retrieve(baseline, run['concepts'], run.get('hub'), run.get('limit', 8))
            if actual_hits != run['results']:
                rules.append('RETRIEVAL-MISMATCH')
            if run['unit'] not in units:
                raise PolicyError('QUERY-UNIT')
            queries.setdefault(run['unit'], set()).update(hit['path'] for hit in actual_hits)
        for unit_id in units:
            if unit_id not in queries:
                rules.append('RETRIEVAL-REQUIRED')
        decisions = {d['unit']: d for d in ticket['decisions']}
        if set(decisions) != set(units) or len(decisions) != len(ticket['decisions']):
            rules.append('DECISION-INCOMPLETE')
        used_outputs = set()
        for key, decision in decisions.items():
            action = decision['action']
            if action not in ACTIONS:
                raise PolicyError('ACTION')
            target = note_path(decision['target']) if decision.get('target') else None
            if action != 'review' and target is None:
                rules.append('TARGET-MISSING')
            effects = decision.get('outputs', [] if action in ('noop', 'review') else [target])
            if (not isinstance(effects, list) or len(effects) != len(set(effects))
                    or any(p not in output_paths for p in effects)):
                rules.append('ACTION-OUTPUT')
            else:
                used_outputs.update(effects)
            if action in ('create', 'merge') and effects != [target]:
                rules.append('ACTION-OUTPUT')
            if action in ('create', 'merge') and target in planned and baseline.get(target) == planned[target]:
                rules.append('ACTION-NO-EFFECT')
            if action == 'split':
                if target not in effects or len(set(effects)) < 2:
                    rules.append('SPLIT-OUTPUT')
                elif any(p != target and target[5:-3] not in index_from_bytes(planned)[p[5:-3]]['parents']
                         for p in effects):
                    rules.append('SPLIT-DIRECTION')
            comparisons = decision.get('comparisons', [])
            compared = {c['path']: c for c in comparisons if c.get('read') is True}
            if (decision.get('basis') != 'source-target-comparison' or not decision.get('reason')
                    or queries.get(key, set()) != set(compared)):
                rules.append('COMPARISON-REQUIRED')
            if action == 'review' or decision.get('unresolved'):
                rules.append('AGENT-REVIEW-REQUIRED')
            elif action == 'merge':
                evidence = compared.get(target, {})
                if (not evidence.get('topic_same') or not evidence.get('purpose_same')
                        or not (decision.get('new_information') or decision.get('new_provenance'))):
                    rules.append('OFF-TOPIC-MERGE')
            elif action == 'create':
                if (target in baseline or not decision.get('retrieval_sufficient')
                        or any(c.get('topic_same') and c.get('purpose_same') for c in comparisons)):
                    rules.append('CREATE-REVIEW')
            elif action == 'split':
                if not (decision.get('independent_topic') or decision.get('independent_purpose')
                        or decision.get('independent_use')):
                    rules.append('SIZE-ONLY-SPLIT')
            elif action == 'noop':
                if (decision.get('new_information') or decision.get('new_provenance')
                        or not decision.get('context_represented') or effects):
                    rules.append('NOOP-LOSS')
            if action in ('merge', 'split', 'noop') and target not in queries.get(key, set()):
                rules.append('RETRIEVAL-MISS')
            if target and target not in planned:
                rules.append('TARGET-MISSING')
        for auxiliary in ticket.get('auxiliary_outputs', []):
            if (not auxiliary.get('reason') or auxiliary.get('path') not in output_paths
                    or auxiliary.get('role') not in ('source-record', 'hub-links')):
                rules.append('AUXILIARY-OUTPUT')
            else:
                used_outputs.add(auxiliary['path'])
        changed_outputs = {p for p in output_paths if baseline.get(p) != planned[p]}
        if not changed_outputs <= used_outputs:
            rules.append('UNEXPLAINED-OUTPUT')

        for blob in exception_spans:
            if blob and any(blob in planned[path] for path in output_paths if path in planned):
                rules.append('EXCEPTION-TRANSFER')

        def coverage(rows, field, needed):
            mapped = set()
            for row in rows:
                key, path = row[field], note_path(row['path'])
                if path not in planned or digest(section(planned[path], row['heading'])) != row['sha256']:
                    rules.append('COVERAGE-SECTION')
                mapped.add(key)
            if mapped != needed:
                rules.append('UNIT-COVERAGE' if field == 'unit' else 'PROVENANCE-COVERAGE')

        coverage(ticket['coverage'], 'unit', expected)
        coverage(ticket['provenance_coverage'], 'provenance', provenance)
        for unit_id, decision in decisions.items():
            related = {row['path'] for row in ticket['coverage'] if row['unit'] == unit_id}
            if decision['action'] in ('merge', 'noop', 'create'):
                if decision.get('target') not in related:
                    rules.append('COVERAGE-TARGET')
            elif decision['action'] == 'split' and not related <= set(decision.get('outputs', [])):
                rules.append('COVERAGE-UNBOUND')
        idx = index_from_bytes(planned)
        tree = {s: set(n['parents']) for s, n in idx.items()}
        incoming = {parent for note in idx.values() for parent in note['parents']}
        roots = {s for s in incoming if s in idx and not idx[s]['parents']}
        colors = {}
        def cycle(node):
            if colors.get(node) == 1:
                return True
            if colors.get(node) == 2:
                return False
            colors[node] = 1
            if any(cycle(p) for p in tree.get(node, set())):
                return True
            colors[node] = 2
            return False
        for path in output_paths:
            slug = path[5:-3]
            for target in lib.LINK_RE.findall(lib.strip_code(planned[path].decode())):
                if target not in idx and target != 'index':
                    rules.append('BROKEN-LINK')
            if not tree[slug] and slug not in roots:
                rules.append('ORPHAN')
            if any(parent not in idx for parent in tree[slug]):
                rules.append('PARENT-MISSING')
            if cycle(slug):
                rules.append('LINK-CYCLE')
        bound = review_digest(ticket)
        review = ticket.get('post_review' if post else 'pre_review', {})
        if (review.get('digest') != bound or review.get('verdict') != 'accepted'
                or not all(review.get(k) is True for k in (
                    'extraction_complete', 'source_target_compared', 'coverage_compared',
                    'summary_consistent', 'old_context_preserved'))):
            rules.append('UNBOUND-REVIEW')
        if corpus(root) != actual or any(digest(read_bytes(root, p)) != value
                                        for p, value in external_sources.items()):
            rules.append('READ-SET-CHANGED')
        return {'result': 'review' if rules else ('verified_reviewed' if post else 'ready'),
                'rules': sorted(set(rules)), 'counts': {'units': len(units), 'outputs': len(output_paths)}}
    except PolicyError as exc:
        return {'result': 'review', 'rules': [exc.rule]}
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError, AttributeError):
        return {'result': 'invalid', 'rules': ['TICKET']}


def main(argv=None):
    ap = SignalParser(description=__doc__)
    ap.add_argument('mode', choices=('candidates', 'check', 'verify'))
    ap.add_argument('--ticket')
    ap.add_argument('--concepts', nargs='+')
    ap.add_argument('--hub')
    ap.add_argument('--limit', type=int, default=8)
    ap.add_argument('--json', action='store_true')
    try:
        args = ap.parse_args(argv)
        if args.mode == 'candidates':
            result = {'results': retrieve(corpus(lib.ROOT), args.concepts, args.hub, args.limit)}
        else:
            if not args.ticket or not args.ticket.startswith(('tmp/', 'plans/')):
                raise PolicyError('TICKET-PATH')
            ticket = json.loads(read_bytes(lib.ROOT, args.ticket), object_pairs_hook=unique_object)
            result = check(ticket, lib.ROOT, post=args.mode == 'verify')
    except (PolicyError, OSError, UnicodeError, ValueError, TypeError, AttributeError):
        result = {'result': 'invalid', 'rules': ['INPUT']}
    print(json.dumps(result))
    return 1 if result.get('result') in ('review', 'invalid') else 0


if __name__ == '__main__':
    sys.exit(main())
