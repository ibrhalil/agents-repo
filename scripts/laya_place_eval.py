#!/usr/bin/env python3
"""Offline, synthetic-only note-placement shadow evaluation; never writes wiki.

Frozen rubric baseline, source-family grouped splits, calibration-only tuning,
real retrieval shortlists and fail-to-review model adapters. No web-gate changes.
"""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import math
import os
import random
import signal
import sys
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import noma_lib as lib
import noma_place as place
from laya_eval import ece, pct
from noma_policy import PolicyError, SignalParser, payload_digest, publish, relative

ACTIONS = ('create', 'merge', 'split', 'noop', 'review')
DESCRIPTIONS = {
    'create': 'a distinct topic or purpose with no equivalent existing note',
    'merge': 'new knowledge, example or independent provenance for the same topic and purpose',
    'split': 'separately reusable ideas in one existing note, preserving all knowledge',
    'noop': 'all knowledge, context and provenance already represented; no changes needed',
    'review': 'unresolved contradiction, missing information, locked note or uncertain comparison',
}
FAMILIES = (
    'connection pooling', 'DNS resolver', 'SQL migrations', 'Kafka consumers', 'HTTP cache',
    'TLS certificates', 'database indexing', 'Redis eviction', 'file backups', 'clock synchronization',
    'memory allocation', 'thread scheduling', 'database replication', 'message retries', 'API pagination',
    'distributed tracing', 'log rotation', 'content encoding', 'locale formatting', 'date parsing',
    'session cookies', 'password hashing', 'OAuth refresh', 'service discovery', 'load balancing',
    'CPU profiling', 'heap snapshots', 'disk compaction', 'batch ingestion', 'schema evolution',
    'binary serialization', 'search ranking', 'text normalization', 'image resizing', 'audio sampling',
    'video transcoding', 'queue fairness', 'transaction isolation', 'deadlock detection', 'rate limiting',
    'network MTU', 'packet routing', 'filesystem journaling', 'storage quotas', 'object lifecycle',
    'deployment rollback', 'feature flags', 'health probes', 'dependency locking', 'build reproducibility',
)
ACCEPTANCE = {'recall_at_8': 0.95, 'macro_f1': 0.80, 'min_class_f1': 0.70,
              'end_to_end': 0.75, 'false_merge': 0.01, 'noop_loss': 0,
              'ece': 0.10, 'brier': 0.30, 'selective_accuracy': 0.95,
              'selective_coverage': 0.60, 'stability': 0.95, 'fallback': 1.00,
              'warm_p95_ms': 3000}
MISS_GROUPS = {'family-13-split', 'family-49-merge'}
MAX_LEN, HEAD_MAX_LEN = 2048, 256


def synthetic_note(title, topic, purpose, claims, origins, locked=False):
    text = ('---\ntitle: ' + json.dumps(title) + '\ntype: concept\nstage: done\nscope: systems\n'
            'status: unverified\ncreated: 2026-10-01T00:00:00+03:00\n'
            'updated: 2026-10-01T00:00:00+03:00\n' + ('locked: true\n' if locked else '')
            + '---\n# ' + title + '\n## Links\n[[systems]]\n## Summary\n' + topic
            + ': ' + purpose + '.\n## Details\n' + '\n'.join(claims) + '\n')
    return {'title': title, 'topic': topic, 'purpose': purpose, 'claims': claims,
            'origins': origins, 'locked': locked, 'unit_purposes': [purpose],
            'facts': {'resource_policy': 'bounded'}, 'text': text}


def translate_claim(text, language):
    if language != 'tr':
        return text
    return (text.replace('bounded resources require explicit configuration.', 'sınırlı kaynaklar açık yapılandırma gerektirir.')
            .replace('retry policy also requires a separately documented exception.', 'yeniden deneme ayrı belgelenen bir istisna gerektirir.')
            .replace('diagnosis distinguishes transient and persistent failure.', 'teşhis geçici ve kalıcı arızayı ayırır.')
            .replace('unlimited resources are required (contradicts the existing bounded rule).',
                     'sınırsız kaynak gerekir; mevcut sınırlı kaynak iddiasıyla çelişir.'))


def dataset():
    examples = []
    for family, topic in enumerate(FAMILIES):
        for action in ACTIONS:
            group = f'family-{family:02d}-{action}'
            paths = ['wiki/note-a.md', 'wiki/note-b.md']
            random.Random(f'placement-{family}').shuffle(paths)
            target_path, distractor_path = paths
            base_claim = f'{topic}: bounded resources require explicit configuration.'
            new_claim = f'{topic}: retry policy also requires a separately documented exception.'
            purpose = 'configuration'
            source_claims = [base_claim]
            source_origins = ['report-a']
            corpus = {target_path: synthetic_note(topic, topic, purpose, [base_claim], ['report-a'])}
            if action == 'create':
                purpose = 'incident diagnosis'
                source_claims = [f'{topic}: diagnosis distinguishes transient and persistent failure.']
                source_origins = ['report-b']
            elif action == 'merge':
                source_claims = [base_claim] if family % 2 else [base_claim, new_claim]
                source_origins = ['report-b']
            elif action == 'split':
                corpus[target_path]['claims'] += [new_claim]
                corpus[target_path]['text'] += new_claim + '\n'
                corpus[target_path]['unit_purposes'].append('retry operation')
                source_claims += [new_claim]
            elif action == 'review':
                corpus[target_path]['locked'] = family % 2 == 0
                source_claims = [f'{topic}: unlimited resources are required (contradicts the existing bounded rule).']
                source_origins = ['report-b']
            # Same project and broad words, distinct topic: a retrieval distractor.
            distractor = FAMILIES[(family + 1) % len(FAMILIES)]
            corpus[distractor_path] = synthetic_note(topic + ' Atlas project', distractor, 'configuration',
                                                     ['Atlas project shares the same scope.'], ['report-c'])
            concepts = topic.split()[:4]
            if len(concepts) < 2:
                concepts += ['configuration']
            miss = group in MISS_GROUPS
            if miss:
                # Hide the real target from the actual first shortlist; never add gold back.
                for n in range(9):
                    corpus[f'wiki/contender-{n}.md'] = synthetic_note(topic, distractor, purpose,
                                                                    [topic + ' unrelated operation'], ['report-c'])
            for language in ('tr', 'en'):
                localized = copy.deepcopy(corpus)
                detail = ('Yöntem: sınırı yapılandır. Örnek: limit=10. İstisna: retry ayrı. Belirsizlik: ortam sınanmadı.'
                          if language == 'tr' else
                          'Method: configure limit. Example: limit=10. Exception: retry is separate. Uncertainty: environment untested.')
                for path, value in localized.items():
                    claims = [translate_claim(claim, language) for claim in value['claims']]
                    value['claims'] = claims + [detail]
                    # Keep the real title: rendering the slug as the title breaks
                    # the intended impartial contender ordering in miss fixtures.
                    rendered = synthetic_note(value['title'], value['topic'], value['purpose'],
                                              value['claims'], value['origins'], value['locked'])
                    value['text'] = rendered['text']
                notes = {p: value['text'].encode() for p, value in localized.items()}
                hits = place.retrieve(notes, concepts, limit=8)
                for length in ('short', 'long'):
                    source = {'topic': topic, 'purpose': purpose,
                              'claims': [translate_claim(claim, language) for claim in source_claims] + [detail],
                              'origins': source_origins,
                              'unit_purposes': ['configuration', 'retry operation'] if action == 'split' else [purpose],
                              'facts': {'resource_policy': 'unlimited' if action == 'review' else 'bounded'}}
                    intro = ('Kaynak ile aday notların konu, amaç, bilgi ve dayanağını karşılaştır.'
                             if language == 'tr' else 'Compare topic, purpose, claims and provenance of source and candidate notes.')
                    examples.append({'id': group + '-' + language + '-' + length,
                                     'source_group': group, 'family': f'family-{family:02d}',
                                     'lang': language, 'length': length, 'intro': intro,
                                     'detail': (detail + '\n') * (4 if length == 'long' else 1),
                                     'source': source, 'notes': localized, 'concepts': concepts,
                                     'shortlist': hits,
                                     'gold_action': action,
                                     'gold_target': target_path if action in ('merge', 'split', 'noop') else 'none',
                                     'valuable': action != 'noop', 'retrieval_miss_case': miss})
    return examples


def grouped_split(examples, seed=42):
    families = sorted({ex['family'] for ex in examples})
    random.Random(seed).shuffle(families)
    boundaries = (round(len(families) * 0.5), round(len(families) * 0.7))
    groups = {'train': set(families[:boundaries[0]]),
              'calib': set(families[boundaries[0]:boundaries[1]]),
              'test': set(families[boundaries[1]:])}
    return {name: [ex for ex in examples if ex['family'] in family_set]
            for name, family_set in groups.items()}


def rubric_baseline(example):
    source = example['source']
    candidates = [hit['path'] for hit in example['shortlist']]
    matching = [path for path in candidates if example['notes'][path]['topic'] == source['topic']
                and example['notes'][path]['purpose'] == source['purpose']]
    if not matching:
        return 'create', 'none'
    target = matching[0]
    note = example['notes'][target]
    if note['locked']:
        return 'review', 'none'
    if any(source['facts'][key] != value for key, value in note['facts'].items() if key in source['facts']):
        return 'review', 'none'
    if len(set(note['unit_purposes'])) > 1:
        return 'split', target
    if set(source['claims']) <= set(note['claims']) and set(source['origins']) <= set(note['origins']):
        return 'noop', target
    return 'merge', target


def questions(example, variant=0):
    targets = {'none': 'No existing note is suitable, or an agent review is required.'}
    targets.update({hit['path']: example['notes'][hit['path']]['topic'] + ': '
                    + example['notes'][hit['path']]['purpose'] for hit in example['shortlist']})
    actions = dict(DESCRIPTIONS)
    if variant == 1:
        actions = dict(reversed(list(actions.items())))
        targets = dict(reversed(list(targets.items())))
    prompt = ('Which placement action preserves knowledge, purpose and provenance?'
              if variant != 2 else 'Select the appropriate source-to-note operation without losing context.')
    return {'placement_action': {'type': 'choice', 'instructions': prompt, 'criteria': actions},
            'placement_target': {'type': 'choice', 'instructions': 'Which actual candidate note should receive the source?',
                                 'criteria': targets}}


def state_text(example):
    # Gold and retrieval-miss flags are never included in model inputs.
    notes = {hit['path']: {k: v for k, v in example['notes'][hit['path']].items() if k != 'text'}
             for hit in example['shortlist']}
    return example['intro'] + '\n' + json.dumps({'source': example['source'], 'candidates': notes},
                                               ensure_ascii=False) + '\n' + example['detail']


def scale(probabilities, temperature):
    values = {key: max(float(value), 1e-12) ** (1 / temperature)
              for key, value in probabilities.items()}
    total = sum(values.values())
    return {key: value / total for key, value in values.items()}


def fit_calibration(rows):
    usable = [row for row in rows if row['reason'] is None]
    if not usable:
        return {'temperature': 1.0, 'target_temperature': 1.0, 'threshold': None, 'n': 0, 'target_n': 0}
    def loss(temperature):
        return sum(-math.log(max(scale(row['action_probs'], temperature).get(row['gold_action'], 0), 1e-12))
                   for row in usable) / len(usable)
    temperature = min((0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0), key=loss)
    target_rows = [row for row in usable if row['gold_target'] in row['target_probs']]
    def target_loss(temperature):
        return sum(-math.log(max(scale(row['target_probs'], temperature)[row['gold_target']], 1e-12))
                   for row in target_rows) / max(len(target_rows), 1)
    target_temperature = min((0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0), key=target_loss) if target_rows else 1.0
    threshold = None
    for candidate in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0):
        selected = [row for row in usable if pair_score(row, temperature, target_temperature) >= candidate]
        if selected and sum(row['action'] == row['gold_action'] and row['target'] == row['gold_target']
                            for row in selected) / len(selected) >= ACCEPTANCE['selective_accuracy']:
            threshold = candidate
            break
    return {'temperature': temperature, 'target_temperature': target_temperature,
            'threshold': threshold, 'n': len(usable), 'target_n': len(target_rows)}


def pair_score(row, temperature, target_temperature):
    # Minimum of predicted head probabilities, not a joint probability.
    action_conf = scale(row['action_probs'], temperature)[row['action']]
    target_probs = row.get('target_probs')
    return min(action_conf, scale(target_probs, target_temperature)[row['target']]) if target_probs else action_conf


def normalize(raw, example, variant=0):
    usage = raw.get('usage', {})
    if usage.get('truncated') or usage.get('state_tokens_dropped', 0) or usage.get('truncated_questions'):
        raise PolicyError('TRUNCATION')
    for stats in usage.get('options', {}).values():
        if stats.get('distinct', stats.get('total')) != stats.get('total'):
            raise PolicyError('OPTION-COLLAPSE')
    answer = raw['answers']
    action, target = answer['placement_action']['choice'], answer['placement_target']['choice']
    expected = questions(example, variant)
    distributions = []
    for key in ('placement_action', 'placement_target'):
        probs = answer[key]['probabilities']
        allowed = set(expected[key]['criteria'])
        if set(probs) != allowed or any(not math.isfinite(float(v)) or not 0 <= float(v) <= 1 for v in probs.values()):
            raise PolicyError('PROBABILITIES')
        if abs(sum(float(v) for v in probs.values()) - 1.0) > 0.02:
            raise PolicyError('PROBABILITIES')
        distributions.append({k: float(v) for k, v in probs.items()})
    if action not in ACTIONS or target not in expected['placement_target']['criteria']:
        raise PolicyError('ANSWER')
    if raw.get('routing', {}).get('model') != 'multilingual':
        raise PolicyError('ROUTE')
    if (action in ('create', 'review')) != (target == 'none'):
        raise PolicyError('ACTION-TARGET')
    return action, target, distributions[0], distributions[1]


def predict(router, example, variant=0, preflight=None, deadline=10.0):
    t0 = time.perf_counter()
    reason, probabilities, target_probs, model_ms, usage = None, {}, {}, None, {}
    action, target, error_kind = 'review', 'none', None
    def timeout(signum, frame):
        raise TimeoutError
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, deadline)
        text, qs = state_text(example), questions(example, variant)
        if preflight is not None:
            preflight(text, qs)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            model_start = time.perf_counter()
            raw = router.predict(text, qs, model='multilingual', lang=example['lang'],
                                 max_len=MAX_LEN, head_max_len=HEAD_MAX_LEN)
            model_ms = (time.perf_counter() - model_start) * 1000
        usage = raw.get('usage', {})
        action, target, probabilities, target_probs = normalize(raw, example, variant)
    except PolicyError as exc:
        reason = exc.rule
    except TimeoutError:
        reason = 'TIMEOUT'
    except Exception as exc:
        reason = 'MODEL-FAILURE'
        error_kind = type(exc).__name__
    finally:
        if old_handler is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    return {'id': example['id'], 'family': example['family'], 'lang': example['lang'],
            'length': example['length'], 'action': action, 'target': target,
            'action_probs': probabilities, 'target_probs': target_probs, 'reason': reason,
            'error_kind': error_kind, 'miss': example['retrieval_miss_case'],
            'gold_action': example['gold_action'], 'gold_target': example['gold_target'],
            'valuable': example['valuable'], 'shortlist': [h['path'] for h in example['shortlist']],
            'model_ms': model_ms, 'usage': usage,
            'latency_ms': (time.perf_counter() - t0) * 1000}


def metrics(rows, calibration):
    count = len(rows)
    per_class = {}
    for action in ACTIONS:
        tp = sum(row['reason'] is None and row['gold_action'] == action and row['action'] == action for row in rows)
        fp = sum(row['gold_action'] != action and row['action'] == action for row in rows)
        fn = sum(row['gold_action'] == action and (row['action'] != action or row['reason'] is not None) for row in rows)
        precision, recall = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
        per_class[action] = {'precision': precision, 'recall': recall,
                             'f1': 2 * precision * recall / max(precision + recall, 1e-12),
                             'support': tp + fn, 'predicted': tp + fp}
    scored, brier, selected, target_scored, target_brier = [], [], [], [], []
    for row in rows:
        if row['reason'] is not None or not row.get('action_probs'):
            continue
        probs = scale(row['action_probs'], calibration['temperature'])
        confidence = probs[row['action']]
        correct = row['action'] == row['gold_action']
        scored.append((correct, confidence))
        brier.append(sum((probs[action] - int(action == row['gold_action'])) ** 2 for action in ACTIONS))
        if row.get('target_probs'):
            target_probs = scale(row['target_probs'], calibration.get('target_temperature', 1.0))
            target_scored.append((row['target'] == row['gold_target'], target_probs[row['target']]))
            target_brier.append(sum((target_probs.get(key, 0) - int(key == row['gold_target'])) ** 2
                                    for key in set(target_probs) | {row['gold_target']}))
        if (calibration['threshold'] is not None
                and pair_score(row, calibration['temperature'], calibration.get('target_temperature', 1.0)) >= calibration['threshold']):
            selected.append(row)
    target_rows = [row for row in rows if row['gold_target'] != 'none']
    target_hits = [row for row in target_rows if row['gold_target'] in row['shortlist']]
    end_to_end = lambda row: row['reason'] is None and row['action'] == row['gold_action'] and row['target'] == row['gold_target']
    false = {}
    for action in ('merge', 'create', 'split'):
        predictions = [row for row in rows if row['action'] == action]
        false[action] = {'errors': sum(not end_to_end(row) for row in predictions),
                         'n': len(predictions),
                         'rate': sum(not end_to_end(row) for row in predictions) / len(predictions) if predictions else None}
    return {'n': count, 'macro_f1': sum(v['f1'] for v in per_class.values()) / len(ACTIONS),
            'per_class': per_class, 'end_to_end': sum(end_to_end(row) for row in rows) / max(count, 1),
            'retrieval': {'recall_at_8': len(target_hits) / max(len(target_rows), 1),
                          'targets': len(target_rows), 'misses': len(target_rows) - len(target_hits),
                          'target_accuracy_given_hit': sum(row['target'] == row['gold_target'] for row in target_hits) / max(len(target_hits), 1)},
            'false_actions': false,
            'noop_loss': sum(row['action'] == 'noop' and row['valuable'] for row in rows),
            'ece': ece(scored), 'brier': sum(brier) / len(brier) if brier else None,
            'target_ece': ece(target_scored),
            'target_brier': sum(target_brier) / len(target_brier) if target_brier else None,
            'target_calibration_n': len(target_scored),
            'confusion': {gold: dict(Counter(row['action'] if row['reason'] is None else 'fallback'
                                            for row in rows if row['gold_action'] == gold)) for gold in ACTIONS},
            'high_confidence_error': sum(not correct and conf >= 0.9 for correct, conf in scored),
            'high_confidence_n': sum(conf >= 0.9 for _, conf in scored),
            'selective_accuracy': sum(end_to_end(row) for row in selected) / len(selected) if selected else None,
            'selective_coverage': len(selected) / max(count, 1),
            'fallbacks': dict(Counter(row['reason'] for row in rows if row['reason'] is not None)),
            'pipeline_latency_ms': {'p50': pct([row['latency_ms'] for row in rows], 50),
                                    'p95': pct([row['latency_ms'] for row in rows], 95)},
            'warm_latency_ms': {'p50': pct([row['model_ms'] for row in rows if row.get('model_ms') is not None], 50),
                                'p95': pct([row['model_ms'] for row in rows if row.get('model_ms') is not None], 95)},
            'input_tokens': sum(row.get('usage', {}).get('input_tokens', 0) for row in rows),
            'forward_calls': sum(row.get('model_ms') is not None for row in rows)}


def model_identity(root, path):
    relative(path)
    directory = root / path
    required = ('model.safetensors', 'rl_agent_config.json', 'encoder/config.json',
                'tokenizer/tokenizer_config.json', 'tokenizer/tokenizer.json')
    if not directory.is_dir() or directory.is_symlink():
        raise PolicyError('MODEL-PATH')
    if any(parent.is_symlink() for parent in directory.parents if parent != root.parent):
        raise PolicyError('MODEL-PATH')
    tokenizer = json.loads((directory / 'tokenizer/tokenizer_config.json').read_text())
    if tokenizer.get('tokenizer_class') in (None, 'TokenizersBackend') or isinstance(tokenizer.get('extra_special_tokens'), list):
        raise PolicyError('TOKENIZER-REWRITE')
    if any(not (directory / name).is_file() for name in required):
        raise PolicyError('MODEL-ARTIFACT')
    hashes = {}
    for artifact in sorted(directory.rglob('*')):
        if artifact.is_dir():
            continue
        name = artifact.relative_to(directory).as_posix()
        target = directory / name
        if not target.is_file() or target.is_symlink() or target.parent.is_symlink():
            raise PolicyError('MODEL-ARTIFACT')
        sha = hashlib.sha256()
        with target.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(block)
        hashes[name] = sha.hexdigest()
    return {'path': path, 'files': hashes, 'digest': payload_digest(hashes)}


def run(root, model_path, output):
    if (root / output).exists():
        raise PolicyError('OUTPUT-EXISTS')
    if version('laya') != '0.3.24':
        raise PolicyError('LAYA-VERSION')
    examples = dataset()
    split = grouped_split(examples)
    identity = model_identity(root, model_path)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false')
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from laya import Router
        from laya.common import build_head, encode_text, render_options, serialize_state, state_room
        router = Router(models={'multilingual': str(root / model_path)}, preload=False,
                        max_loaded=1, device='cpu', sha256_digests={'multilingual': identity['files']})
        router.preload(['multilingual'])
        agent = router.load('multilingual')
    cold_load_ms = (time.perf_counter() - t0) * 1000
    def preflight(text, qs):
        for question in qs.values():
            q = {'t': question['type'], 'ins': question['instructions'], 'crit': question['criteria']}
            _, markers, stats = build_head(agent.tok, q, HEAD_MAX_LEN)
            if (len(markers) != len(render_options(q)) or stats['options_distinct'] != stats['options']):
                raise PolicyError('OPTION-COLLAPSE')
            ids = encode_text(agent.tok, serialize_state(text).replace(agent.tok.mask_token, ' '),
                              add_special_tokens=False)['input_ids']
            if len(ids) > state_room(agent.tok, q, MAX_LEN, HEAD_MAX_LEN):
                raise PolicyError('TRUNCATION')
    # Tokenizer-only validation before any calibration/test prediction.
    for ex in split['calib'] + split['test']:
        for variant in (0, 1, 2):
            preflight(state_text(ex), questions(ex, variant))
    calibration_rows = [predict(router, ex, preflight=preflight) for ex in split['calib']]
    calibration = fit_calibration(calibration_rows)
    test_rows, variant_rows, stability, order_stability, wording_stability = [], [], [], [], []
    for ex in split['test']:
        primary = predict(router, ex, preflight=preflight)
        variants = [predict(router, ex, variant=i, preflight=preflight) for i in (1, 2)]
        test_rows.append(primary)
        variant_rows.append(variants)
        agreements = [primary['reason'] is None and row['reason'] is None
                      and (row['action'], row['target']) == (primary['action'], primary['target']) for row in variants]
        order_stability.append(agreements[0])
        wording_stability.append(agreements[1])
        stability.append(all(agreements))
    baseline_rows = []
    for ex in split['test']:
        started = time.perf_counter()
        action, target = rubric_baseline(ex)
        row = {'id': ex['id'], 'action': action, 'target': target,
                             'gold_action': ex['gold_action'], 'gold_target': ex['gold_target'],
                             'valuable': ex['valuable'], 'reason': None,
                             'latency_ms': (time.perf_counter() - started) * 1000,
                             'shortlist': [h['path'] for h in ex['shortlist']]}
        baseline_rows.append(row)
    measured = metrics(test_rows, calibration)
    baseline_measured = metrics(baseline_rows, calibration)
    measured['stability'] = sum(stability) / len(stability)
    measured['order_stability'] = sum(order_stability) / len(order_stability)
    measured['wording_stability'] = sum(wording_stability) / len(wording_stability)
    injected = []
    class BrokenRouter:
        def predict(self, *args, **kwargs):
            raise TimeoutError
    injected.append(predict(BrokenRouter(), split['test'][0]))
    for bad in ({}, {'usage': {'truncated': True}},
                {'usage': {'options': {'a': {'total': 2, 'distinct': 1}}}}):
        class BadRouter:
            def predict(self, *args, **kwargs):
                return bad
        injected.append(predict(BadRouter(), split['test'][0]))
    measured['injected_fallback'] = sum(row['reason'] is not None and row['action'] == 'review' for row in injected) / len(injected)
    requirements = {
        'retrieval': measured['retrieval']['recall_at_8'] >= ACCEPTANCE['recall_at_8'],
        'macro_f1': measured['macro_f1'] >= ACCEPTANCE['macro_f1'],
        'per_class': all(v['f1'] >= ACCEPTANCE['min_class_f1'] for v in measured['per_class'].values()),
        'end_to_end': measured['end_to_end'] >= ACCEPTANCE['end_to_end'],
        'false_merge': measured['false_actions']['merge']['rate'] is not None and measured['false_actions']['merge']['rate'] <= ACCEPTANCE['false_merge'],
        'noop_loss': measured['noop_loss'] == 0,
        'ece': measured['ece'] is not None and measured['ece'] <= ACCEPTANCE['ece'],
        'brier': measured['brier'] is not None and measured['brier'] <= ACCEPTANCE['brier'],
        'selectivity': measured['selective_accuracy'] is not None and measured['selective_accuracy'] >= ACCEPTANCE['selective_accuracy']
                       and measured['selective_coverage'] >= ACCEPTANCE['selective_coverage'],
        'stability': measured['stability'] >= ACCEPTANCE['stability'],
        'fallback': measured['injected_fallback'] == 1.0,
        'latency': measured['warm_latency_ms']['p95'] is not None and measured['warm_latency_ms']['p95'] <= ACCEPTANCE['warm_p95_ms'],
    }
    if identity != model_identity(root, model_path):
        raise PolicyError('MODEL-CHANGED')
    report = {'version': 1, 'dataset_digest': payload_digest(examples),
              'schema_digest': payload_digest(DESCRIPTIONS), 'checkpoint': identity,
              'laya_version': version('laya'), 'device': 'cpu', 'language_pin': 'per-example',
              'max_len': MAX_LEN, 'head_max_len': HEAD_MAX_LEN,
              'model_dtype': str(next(agent.model.parameters()).dtype),
              'source_groups': 250, 'families': 50, 'split_sizes': {k: len(v) for k, v in split.items()},
              'acceptance': ACCEPTANCE, 'calibration': calibration, 'cold_load_ms': cold_load_ms,
              'test': measured, 'baseline': baseline_measured,
              'slices': {key: metrics([r for r in test_rows if r[field] == key], calibration)
                         for field, values in (('lang', ('tr', 'en')), ('length', ('short', 'long'))) for key in values},
              'requirements': requirements, 'decision': 'rejected' if not all(requirements.values()) else 'inconclusive',
              'baseline_delta': {'macro_f1': measured['macro_f1'] - baseline_measured['macro_f1'],
                                  'end_to_end': measured['end_to_end'] - baseline_measured['end_to_end']},
              'limitations': ['Synthetic templates and frozen rule baseline; no real-note generalization claim.',
                              'Low error-rate support cannot establish automatic-write safety.',
                              'Long states may fall back to agent review; no content is discarded.'],
              'calibration_rows': calibration_rows, 'test_rows': test_rows, 'variant_rows': variant_rows}
    publish(root, output, (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode(), exclusive=True)
    return {'path': output, 'n': len(test_rows), 'decision': report['decision'],
            'macro_f1': measured['macro_f1'], 'end_to_end': measured['end_to_end'],
            'requirements_passed': sum(requirements.values()), 'requirements': len(requirements)}


def main(argv=None):
    ap = SignalParser(description=__doc__)
    ap.add_argument('mode', choices=('describe', 'run'))
    ap.add_argument('--model-dir', default='models/laya-ft')
    ap.add_argument('--out')
    try:
        args = ap.parse_args(argv)
        if args.mode == 'describe':
            data = grouped_split(dataset())
            result = {'examples': sum(len(v) for v in data.values()),
                      'source_groups': 250, 'families': 50,
                      'split_sizes': {k: len(v) for k, v in data.items()}, 'acceptance': ACCEPTANCE}
        else:
            if not args.out or not args.out.startswith(('tmp/', 'plans/')) or not args.model_dir.startswith('models/'):
                raise PolicyError('OUTPUT-PATH')
            result = run(lib.ROOT, args.model_dir, args.out)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'blocked', 'rules': [exc.rule if isinstance(exc, PolicyError) else 'PILOT']}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
