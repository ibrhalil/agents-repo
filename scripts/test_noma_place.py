"""Real synthetic files for reviewed merge/create/split/noop and coverage checks."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import noma_lib as lib
import noma_place as place
from noma_policy import digest


def note(slug, body, parents='[[systems]]', updated='2026-10-01T00:00:00+03:00', lock=''):
    return ('---\ntitle: "' + slug + '"\ntype: concept\nstage: done\nscope: systems\n'
            'status: unverified\ncreated: 2026-10-01T00:00:00+03:00\nupdated: ' + updated
            + '\n' + lock + '---\n# ' + slug + '\n## Links\n' + parents
            + '\n## Summary\n' + slug + '.\n## Details\n' + body + '\n')


def bind(ticket, post=False):
    ticket['post_review' if post else 'pre_review'] = {
        'digest': place.review_digest(ticket), 'verdict': 'accepted',
        'extraction_complete': True, 'source_target_compared': True,
        'coverage_compared': True, 'summary_consistent': True, 'old_context_preserved': True}


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='noma-place-', dir=lib.ROOT / 'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'wiki').mkdir()
        (self.root / 'tmp').mkdir()
        self.write('wiki/systems.md', note('systems', 'System hub.', parents=''))
        self.before = note('connection-pool', 'Old pool limit: 10. Source A.')
        self.write('wiki/connection-pool.md', self.before)
        self.write('wiki/dns.md', note('dns', 'DNS caches host lookups.'))
        self.source = 'Pool method: limit 10. Example: max_pool=10. Exception: no limit on retries.\n'
        self.write('tmp/source.txt', self.source)
        self.after = note('connection-pool', 'Old pool limit: 10. Source A.\n' + self.source
                          + 'Source B; uncertainty: retry timing unknown.',
                          updated='2026-10-02T00:00:00+03:00')
        self.ticket = self.ticket_for()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')

    def ticket_for(self):
        existing = place.corpus(self.root)
        concepts = ['connection', 'pool']
        hits = place.retrieve(existing, concepts)
        source_bytes = self.source.encode()
        section_hash = digest(place.section(self.after.encode(), 'Details'))
        ticket = {
            'version': 1, 'corpus': {p: digest(b) for p, b in existing.items()},
            'sources': [{'id': 'source-b', 'path': 'tmp/source.txt', 'sha256': digest(source_bytes),
                         'unit_ids': ['pool-example'], 'provenance_ids': ['source-b-origin'],
                         'sections': [{'id': 'method', 'start': 0, 'end': len(source_bytes),
                                       'sha256': digest(source_bytes), 'unit_ids': ['pool-example']}]}],
            'units': [{'id': 'pool-example', 'topic': 'pool limits', 'purpose': 'configuration',
                       'source_sections': ['source-b.method']}],
            'retrieval': [{'unit': 'pool-example', 'concepts': concepts, 'results': hits}],
            'decisions': [{'unit': 'pool-example', 'action': 'merge', 'target': 'wiki/connection-pool.md',
                           'basis': 'source-target-comparison', 'reason': 'New example for same configuration.',
                           'new_information': True, 'new_provenance': True,
                           'comparisons': [{'path': h['path'], 'read': True,
                                            'topic_same': True, 'purpose_same': True} for h in hits]}],
            'coverage': [{'unit': 'pool-example', 'path': 'wiki/connection-pool.md',
                          'heading': 'Details', 'sha256': section_hash}],
            'provenance_coverage': [{'provenance': 'source-b-origin', 'path': 'wiki/connection-pool.md',
                                     'heading': 'Details', 'sha256': section_hash}],
            'outputs': [{'path': 'wiki/connection-pool.md', 'before': self.before, 'after': self.after}]}
        bind(ticket)
        return ticket

    def apply_reviewed(self, ticket=None):
        ticket = ticket or self.ticket
        for output in ticket['outputs']:
            self.write(output['path'], output['after'])
        bind(ticket, post=True)

    def test_merge_preserves_old_context_and_source_absent_answers(self):
        self.assertEqual('ready', place.check(self.ticket, self.root)['result'])
        self.apply_reviewed()
        self.assertEqual('verified_reviewed', place.check(self.ticket, self.root, post=True)['result'])
        (self.root / 'tmp/source.txt').unlink()
        text = (self.root / 'wiki/connection-pool.md').read_text(encoding='utf-8')
        for answer in ('Old pool limit: 10. Source A.', 'max_pool=10',
                       'no limit on retries', 'retry timing unknown', 'Source B'):
            self.assertIn(answer, text)
        self.assertNotEqual('verified_reviewed', place.check(self.ticket, self.root, post=True)['result'])

    def test_off_topic_and_lexical_only_merge_require_review(self):
        decision = self.ticket['decisions'][0]
        decision['comparisons'][0]['topic_same'] = False
        bind(self.ticket)
        self.assertIn('OFF-TOPIC-MERGE', place.check(self.ticket, self.root)['rules'])
        decision['basis'] = 'shared-project-keywords'
        bind(self.ticket)
        self.assertIn('COMPARISON-REQUIRED', place.check(self.ticket, self.root)['rules'])

    def test_fabricated_shortlist_and_changed_corpus_are_not_evidence(self):
        self.ticket['retrieval'][0]['results'].append({'path': 'wiki/dns.md', 'score': 999, 'match': 'exact'})
        bind(self.ticket)
        self.assertIn('RETRIEVAL-MISMATCH', place.check(self.ticket, self.root)['rules'])
        self.write('wiki/connection-pool-extra.md', note('connection-pool-extra', 'New contender.'))
        self.assertIn('STALE-CORPUS', place.check(self.ticket, self.root)['rules'])

    def test_source_edit_and_review_content_edit_are_detected(self):
        self.write('tmp/source.txt', self.source + 'More knowledge.\n')
        self.assertIn('STALE-SOURCE', place.check(self.ticket, self.root)['rules'])
        self.ticket['units'][0]['purpose'] = 'changed'
        self.assertIn('UNBOUND-REVIEW', place.check(self.ticket, self.root)['rules'])

    def test_missing_unit_or_new_provenance_never_counts_as_complete(self):
        self.ticket['coverage'] = []
        self.ticket['provenance_coverage'] = []
        bind(self.ticket)
        result = place.check(self.ticket, self.root)
        self.assertIn('UNIT-COVERAGE', result['rules'])
        self.assertIn('PROVENANCE-COVERAGE', result['rules'])

    def test_same_bytes_new_origin_are_not_noop(self):
        self.ticket['decisions'][0].update(action='noop', new_information=False,
                                            new_provenance=True, context_represented=True)
        bind(self.ticket)
        self.assertIn('NOOP-LOSS', place.check(self.ticket, self.root)['rules'])

    def test_noop_is_idempotent_and_read_only(self):
        self.ticket['outputs'][0]['after'] = self.before
        self.ticket['decisions'][0].update(action='noop', new_information=False,
                                            new_provenance=False, context_represented=True)
        for coverage in ('coverage', 'provenance_coverage'):
            self.ticket[coverage][0]['sha256'] = digest(place.section(self.before.encode(), 'Details'))
        bind(self.ticket)
        initial = place.corpus(self.root)
        for _ in range(2):
            self.assertEqual('ready', place.check(self.ticket, self.root)['result'])
        self.assertEqual(initial, place.corpus(self.root))

    def test_size_only_split_is_refused(self):
        self.ticket['decisions'][0].update(action='split', independent_topic=False,
                                            independent_purpose=False, independent_use=False)
        bind(self.ticket)
        self.assertIn('SIZE-ONLY-SPLIT', place.check(self.ticket, self.root)['rules'])

    def test_independent_create_and_split_apply_reviewed_real_outputs(self):
        ticket = copy.deepcopy(self.ticket)
        child = 'wiki/pool-retry.md'
        after = note('pool-retry', self.source)
        ticket['outputs'] = [{'path': child, 'before': None, 'after': after}]
        ticket['decisions'][0].update(action='create', target=child, outputs=[child], retrieval_sufficient=True)
        for comparison in ticket['decisions'][0]['comparisons']:
            comparison['purpose_same'] = False
        for field in ('coverage', 'provenance_coverage'):
            ticket[field][0].update(path=child, sha256=digest(place.section(after.encode(), 'Details')))
        bind(ticket)
        self.assertEqual('ready', place.check(ticket, self.root)['result'])
        self.apply_reviewed(ticket)
        self.assertEqual('verified_reviewed', place.check(ticket, self.root, post=True)['result'])

        # Fresh fixture snapshot; split preserves the pool fact in its hub and
        # puts the independently referenced retry method in a proper child.
        split = self.ticket_for()
        hub = note('connection-pool', 'Old pool limit: 10. Source A.\n[[pool-retry]]',
                   updated='2026-10-02T00:00:00+03:00')
        retry = note('pool-retry', self.source, parents='[[connection-pool]]',
                     updated='2026-10-02T00:00:00+03:00')
        split['outputs'] = [{'path': 'wiki/connection-pool.md', 'before': self.before, 'after': hub},
                            {'path': child, 'before': after, 'after': retry}]
        split['decisions'][0].update(action='split', outputs=['wiki/connection-pool.md', child], independent_use=True)
        for field in ('coverage', 'provenance_coverage'):
            split[field][0].update(path=child, sha256=digest(place.section(retry.encode(), 'Details')))
        bind(split)
        self.assertEqual('ready', place.check(split, self.root)['result'])
        self.apply_reviewed(split)
        self.assertEqual('verified_reviewed', place.check(split, self.root, post=True)['result'])
        self.assertIn('Old pool limit: 10', (self.root / 'wiki/connection-pool.md').read_text())
        self.assertEqual(['connection-pool'], place.index_from_bytes(place.corpus(self.root))['pool-retry']['parents'])

    def test_successful_merge_then_same_source_is_idempotent_noop(self):
        self.apply_reviewed()
        self.before = self.after
        again = self.ticket_for()
        again['decisions'][0].update(action='noop', new_information=False,
                                     new_provenance=False, context_represented=True)
        bind(again)
        initial = place.corpus(self.root)
        self.assertEqual('ready', place.check(again, self.root)['result'])
        self.apply_reviewed(again)
        self.assertEqual('verified_reviewed', place.check(again, self.root, post=True)['result'])
        self.assertEqual(initial, place.corpus(self.root))

    def test_changed_noop_fails_both_check_and_verify(self):
        self.ticket['decisions'][0].update(action='noop', new_information=False,
                                            new_provenance=False, context_represented=True)
        bind(self.ticket)
        self.assertIn('UNEXPLAINED-OUTPUT', place.check(self.ticket, self.root)['rules'])
        self.apply_reviewed()
        self.assertIn('UNEXPLAINED-OUTPUT', place.check(self.ticket, self.root, post=True)['rules'])

    def test_outputless_merge_and_unexplained_extra_edits_fail(self):
        self.ticket['outputs'] = []
        bind(self.ticket)
        self.assertIn('ACTION-OUTPUT', place.check(self.ticket, self.root)['rules'])

    def test_empty_links_and_fenced_fake_headings_parse_as_markdown(self):
        data = note('systems', '```md\n## Details\nExample\n```', parents='').replace(
            '## Links\n\n## Summary', '## Links\n## Summary').encode()
        place.transition(None, data)
        self.assertEqual([], place.index_from_bytes({'wiki/systems.md': data})['systems']['parents'])
        self.assertIn(b'Example', place.section(data, 'Details'))

    def test_locked_base_cannot_be_unlocked_in_the_planned_output(self):
        locked = self.before.replace('---\n#', 'locked: true\n---\n#')
        self.write('wiki/connection-pool.md', locked)
        self.ticket['outputs'][0]['before'] = locked
        bind(self.ticket)
        self.assertEqual(['LOCKED-TARGET'], place.check(self.ticket, self.root)['rules'])

    def test_status_or_created_change_requires_review(self):
        for field, value in (('status: unverified', 'status: established'),
                             ('created: 2026-10-01', 'created: 2026-09-30')):
            ticket = copy.deepcopy(self.ticket)
            ticket['outputs'][0]['after'] = self.after.replace(field, value)
            bind(ticket)
            self.assertIn('IMMUTABLE-METADATA', place.check(ticket, self.root)['rules'])

    def test_updated_same_instant_with_other_timezone_is_not_a_bump(self):
        self.ticket['outputs'][0]['after'] = self.after.replace(
            'updated: 2026-10-02T00:00:00+03:00', 'updated: 2026-09-30T21:00:00Z')
        bind(self.ticket)
        self.assertEqual(['UPDATED'], place.check(self.ticket, self.root)['rules'])

    def test_post_edit_unknown_bytes_and_broken_links_are_detected(self):
        self.apply_reviewed()
        self.write('wiki/connection-pool.md', self.after + 'Unreviewed fact.\n')
        self.assertIn('UNREVIEWED-OUTPUT', place.check(self.ticket, self.root, post=True)['rules'])
        self.ticket['outputs'][0]['after'] = self.after + '[[missing-note]]\n'
        bind(self.ticket)
        self.assertIn('BROKEN-LINK', place.check(self.ticket, self.root)['rules'])

    def test_source_symlink_and_path_traversal_are_refused(self):
        (self.root / 'tmp/alias.txt').symlink_to(self.root / 'tmp/source.txt')
        for path in ('tmp/../tmp/source.txt', 'tmp/alias.txt'):
            self.ticket['sources'][0]['path'] = path
            bind(self.ticket)
            self.assertEqual('review', place.check(self.ticket, self.root)['result'])

    def test_mixed_noop_and_merge_batch_reviews_each_output(self):
        dns_body = (self.root / 'wiki/dns.md').read_bytes()
        dns_details = digest(place.section(dns_body, 'Details'))
        ticket = copy.deepcopy(self.ticket)
        dns_source = 'DNS caches host lookups.\n'
        self.write('tmp/source-dns.txt', dns_source)
        src = dns_source.encode()
        ticket['sources'].append({'id': 'source-dns', 'path': 'tmp/source-dns.txt',
                                  'sha256': digest(src), 'unit_ids': ['dns-fact'],
                                  'provenance_ids': ['source-dns-origin'],
                                  'sections': [{'id': 'fact', 'start': 0, 'end': len(src),
                                                'sha256': digest(src), 'unit_ids': ['dns-fact']}]})
        ticket['units'].append({'id': 'dns-fact', 'topic': 'dns cache', 'purpose': 'lookup',
                                'source_sections': ['source-dns.fact']})
        dns_hits = place.retrieve(place.corpus(self.root), ['dns', 'cache'])
        ticket['retrieval'].append({'unit': 'dns-fact', 'concepts': ['dns', 'cache'],
                                    'results': dns_hits})
        ticket['decisions'].append({'unit': 'dns-fact', 'action': 'noop', 'target': 'wiki/dns.md',
                                    'basis': 'source-target-comparison',
                                    'reason': 'Already represented by the existing note.',
                                    'new_information': False, 'new_provenance': False,
                                    'context_represented': True,
                                    'comparisons': [{'path': h['path'], 'read': True,
                                                     'topic_same': True, 'purpose_same': True}
                                                    for h in dns_hits]})
        ticket['coverage'].append({'unit': 'dns-fact', 'path': 'wiki/dns.md',
                                   'heading': 'Details', 'sha256': dns_details})
        ticket['provenance_coverage'].append({'provenance': 'source-dns-origin',
                                              'path': 'wiki/dns.md',
                                              'heading': 'Details', 'sha256': dns_details})
        bind(ticket)
        self.assertEqual('ready', place.check(ticket, self.root)['result'])
        # A noop unit must not smuggle an unexplained output into the same batch.
        dns_after = note('dns', 'DNS caches host lookups.\nSeen again.',
                         updated='2026-10-02T00:00:00+03:00')
        ticket['outputs'].append({'path': 'wiki/dns.md',
                                  'before': dns_body.decode('utf-8'), 'after': dns_after})
        bind(ticket)
        self.assertIn('UNEXPLAINED-OUTPUT', place.check(ticket, self.root)['rules'])

    def test_two_sources_with_same_bytes_keep_both_provenance(self):
        ticket = copy.deepcopy(self.ticket)
        self.write('tmp/source-copy.txt', self.source)
        src = self.source.encode()
        section_hash = digest(place.section(self.after.encode(), 'Details'))
        ticket['sources'].append({'id': 'source-c', 'path': 'tmp/source-copy.txt',
                                  'sha256': digest(src), 'unit_ids': ['pool-example'],
                                  'provenance_ids': ['source-c-origin'],
                                  'sections': [{'id': 'method', 'start': 0, 'end': len(src),
                                                'sha256': digest(src), 'unit_ids': ['pool-example']}]})
        ticket['units'][0]['source_sections'].append('source-c.method')
        ticket['provenance_coverage'].append({'provenance': 'source-c-origin',
                                              'path': 'wiki/connection-pool.md',
                                              'heading': 'Details', 'sha256': section_hash})
        bind(ticket)
        result = place.check(ticket, self.root)
        self.assertEqual('ready', result['result'])
        self.assertEqual([], result['rules'])

    def test_multisection_multibyte_source_maps_units_by_byte_spans(self):
        first = 'Yöntem: havuz sınırı yapılandırılır; limit=10. Örnek: max_pool=10.\n'
        second = 'İkinci bölüm: yeniden deneme ayrıca ele alınmalıdır. İstisna: zaman aşımı.\n'
        data = (first + second).encode('utf-8')
        split = len(first.encode('utf-8'))
        self.write('tmp/source-tr.txt', (first + second))
        ticket = copy.deepcopy(self.ticket)
        ticket['sources'][0].update(
            path='tmp/source-tr.txt', sha256=digest(data),
            unit_ids=['pool-config', 'pool-retry'],
            provenance_ids=['source-tr-origin'],
            sections=[{'id': 'method', 'start': 0, 'end': split,
                       'sha256': digest(data[:split]), 'unit_ids': ['pool-config']},
                      {'id': 'retry', 'start': split, 'end': len(data),
                       'sha256': digest(data[split:]), 'unit_ids': ['pool-retry']}])
        ticket['units'] = [
            {'id': 'pool-config', 'topic': 'pool limits', 'purpose': 'configuration',
             'source_sections': ['source-b.method']},
            {'id': 'pool-retry', 'topic': 'pool retries', 'purpose': 'retry handling',
             'source_sections': ['source-b.retry']}]
        hits = place.retrieve(place.corpus(self.root), ['connection', 'pool'])
        ticket['retrieval'] = [{'unit': unit, 'concepts': ['connection', 'pool'],
                                'results': hits} for unit in ('pool-config', 'pool-retry')]
        comparisons = [{'path': h['path'], 'read': True, 'topic_same': True,
                        'purpose_same': True} for h in hits]
        ticket['decisions'] = [
            {'unit': 'pool-config', 'action': 'merge', 'target': 'wiki/connection-pool.md',
             'basis': 'source-target-comparison', 'reason': 'Config detail for same topic.',
             'new_information': True, 'new_provenance': True, 'comparisons': comparisons},
            {'unit': 'pool-retry', 'action': 'merge', 'target': 'wiki/connection-pool.md',
             'basis': 'source-target-comparison', 'reason': 'Retry exception for same topic.',
             'new_information': True, 'new_provenance': True, 'comparisons': comparisons}]
        section_hash = digest(place.section(self.after.encode(), 'Details'))
        ticket['coverage'] = [{'unit': unit, 'path': 'wiki/connection-pool.md',
                               'heading': 'Details', 'sha256': section_hash}
                              for unit in ('pool-config', 'pool-retry')]
        ticket['provenance_coverage'] = [{'provenance': 'source-tr-origin',
                                          'path': 'wiki/connection-pool.md',
                                          'heading': 'Details', 'sha256': section_hash}]
        bind(ticket)
        result = place.check(ticket, self.root)
        self.assertEqual('ready', result['result'])
        self.assertEqual([], result['rules'])

    def test_table_and_secret_exception_sections_are_reviewed_not_dropped(self):
        table = 'Ayar | Değer\n--- | ---\nlimit | 10\nörnek | max_pool=10\n'
        secret = 'TOKEN=SECRET_VALUE_123\n'
        data = (table + secret).encode('utf-8')
        split = len(table.encode('utf-8'))
        self.write('tmp/source-table.txt', table + secret)
        ticket = copy.deepcopy(self.ticket)
        ticket['sources'][0].update(
            path='tmp/source-table.txt', sha256=digest(data),
            sections=[{'id': 'table', 'start': 0, 'end': split,
                       'sha256': digest(data[:split]), 'unit_ids': ['pool-example']},
                      {'id': 'secret', 'start': split, 'end': len(data),
                       'sha256': digest(data[split:]), 'unit_ids': [],
                       'reviewed_exception': 'secret value represented as placeholder'}])
        ticket['units'][0]['source_sections'] = ['source-b.table']
        self.after = note('connection-pool',
                          'Old pool limit: 10. Source A.\nAyar | Değer\n--- | ---\nlimit | 10\n'
                          'örnek | max_pool=10\nSource B; TOKEN=<redacted>.',
                          updated='2026-10-02T00:00:00+03:00')
        ticket['outputs'][0]['after'] = self.after
        section_hash = digest(place.section(self.after.encode(), 'Details'))
        ticket['coverage'][0]['sha256'] = section_hash
        ticket['provenance_coverage'][0]['sha256'] = section_hash
        bind(ticket)
        result = place.check(ticket, self.root)
        self.assertEqual('ready', result['result'])
        self.assertNotIn('SECTION-UNMAPPED', result['rules'])
        self.assertIn('örnek | max_pool=10', self.after)
        self.assertNotIn('SECRET_VALUE_123', self.after)

    def test_unreadable_external_attachment_stays_review(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['sources'].append({'id': 'att', 'path': 'tmp/missing-attachment.bin',
                                  'sha256': '0' * 64, 'unit_ids': ['pool-example'],
                                  'provenance_ids': ['att-origin'],
                                  'sections': []})
        bind(ticket)
        result = place.check(ticket, self.root)
        self.assertEqual('review', result['result'])

    def test_merge_into_policy_register_requires_authority_review(self):
        body = '\n## Aktif Policy Kümesi\n- [[agent-read-policy]]\n'
        register = note('agent-policy', 'Mevcut kural.', parents='')
        after = note('agent-policy', 'Mevcut kural.\n' + self.source, parents='',
                     updated='2026-10-02T00:00:00+03:00')
        register += body
        after += body
        self.write('wiki/agent-policy.md', register)
        ticket = self.ticket_for()
        ticket['outputs'][0] = {'path': 'wiki/agent-policy.md', 'before': register, 'after': after}
        ticket['decisions'][0]['target'] = 'wiki/agent-policy.md'
        section_hash = digest(place.section(after.encode(), 'Details'))
        ticket['coverage'][0].update(path='wiki/agent-policy.md', sha256=section_hash)
        ticket['provenance_coverage'][0].update(path='wiki/agent-policy.md', sha256=section_hash)
        bind(ticket)
        self.assertIn('POLICY-AUTHORITY-REVIEW', place.check(ticket, self.root)['rules'])

    def test_create_on_existing_target_requires_review(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['decisions'][0].update(action='create', target='wiki/connection-pool.md',
                                      outputs=['wiki/connection-pool.md'],
                                      retrieval_sufficient=True)
        bind(ticket)
        self.assertIn('CREATE-REVIEW', place.check(ticket, self.root)['rules'])

    def test_effectless_merge_fires_action_no_effect(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['outputs'][0]['after'] = self.before
        for field in ('coverage', 'provenance_coverage'):
            ticket[field][0]['sha256'] = digest(place.section(self.before.encode(), 'Details'))
        bind(ticket)
        self.assertIn('ACTION-NO-EFFECT', place.check(ticket, self.root)['rules'])

    def test_split_child_without_hub_link_fires_split_direction(self):
        ticket = copy.deepcopy(self.ticket)
        hub = note('connection-pool', 'Old pool limit: 10. Source A.',
                   updated='2026-10-02T00:00:00+03:00')
        child = note('pool-retry', self.source, parents='[[systems]]',
                     updated='2026-10-02T00:00:00+03:00')
        ticket['outputs'] = [{'path': 'wiki/connection-pool.md', 'before': self.before, 'after': hub},
                             {'path': 'wiki/pool-retry.md', 'before': None, 'after': child}]
        ticket['decisions'][0].update(action='split', target='wiki/connection-pool.md',
                                      outputs=['wiki/connection-pool.md', 'wiki/pool-retry.md'],
                                      independent_use=True)
        for field in ('coverage', 'provenance_coverage'):
            ticket[field][0].update(path='wiki/pool-retry.md',
                                    sha256=digest(place.section(child.encode(), 'Details')))
        bind(ticket)
        self.assertIn('SPLIT-DIRECTION', place.check(ticket, self.root)['rules'])

    def test_unresolved_contradiction_requires_agent_review(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['decisions'][0]['unresolved'] = True
        bind(ticket)
        result = place.check(ticket, self.root)
        self.assertIn('AGENT-REVIEW-REQUIRED', result['rules'])
        self.assertEqual('review', result['result'])

    def test_unit_without_any_retrieval_run_fires_retrieval_required(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['retrieval'] = []
        bind(ticket)
        self.assertIn('RETRIEVAL-REQUIRED', place.check(ticket, self.root)['rules'])

    def test_coverage_outside_decision_target_fires_coverage_target(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['coverage'][0].update(
            path='wiki/dns.md',
            sha256=digest(place.section((self.root / 'wiki/dns.md').read_bytes(), 'Details')))
        bind(ticket)
        self.assertIn('COVERAGE-TARGET', place.check(ticket, self.root)['rules'])

    def test_reviewed_exception_bytes_copied_into_output_fire_transfer(self):
        ticket = copy.deepcopy(self.ticket)
        secret = 'PASSWORD=TOP_SECRET_9\n'
        source = self.source + secret
        self.write('tmp/source.txt', source)
        data = source.encode()
        start = len(self.source.encode())
        ticket['sources'][0].update(sha256=digest(data))
        ticket['sources'][0]['sections'].append(
            {'id': 'secret', 'start': start, 'end': len(data),
             'sha256': digest(data[start:]), 'unit_ids': [],
             'reviewed_exception': 'secret value'})
        after = self.after + secret
        ticket['outputs'][0]['after'] = after
        section_hash = digest(place.section(after.encode(), 'Details'))
        ticket['coverage'][0]['sha256'] = section_hash
        ticket['provenance_coverage'][0]['sha256'] = section_hash
        bind(ticket)
        self.assertIn('EXCEPTION-TRANSFER', place.check(ticket, self.root)['rules'])

    def test_merge_with_uncompared_extra_output_fails_check_and_verify(self):
        ticket = copy.deepcopy(self.ticket)
        dns_before = (self.root / 'wiki/dns.md').read_text(encoding='utf-8')
        dns_after = note('dns', 'DNS caches host lookups.\nExtra edit.',
                         updated='2026-10-02T00:00:00+03:00')
        ticket['outputs'].append({'path': 'wiki/dns.md',
                                  'before': dns_before, 'after': dns_after})
        ticket['decisions'][0]['outputs'] = ['wiki/connection-pool.md', 'wiki/dns.md']
        bind(ticket)
        result = place.check(ticket, self.root)
        self.assertIn('ACTION-OUTPUT', result['rules'])
        self.assertEqual('review', result['result'])
        self.apply_reviewed(ticket)
        result = place.check(ticket, self.root, post=True)
        self.assertIn('ACTION-OUTPUT', result['rules'])
        self.assertNotEqual('verified_reviewed', result['result'])

    def test_split_with_duplicated_target_path_fails_check_and_verify(self):
        ticket = copy.deepcopy(self.ticket)
        hub = note('connection-pool', 'Old pool limit: 10. Source A.\n[[pool-retry]]',
                   updated='2026-10-02T00:00:00+03:00')
        retry = note('pool-retry', self.source, parents='[[connection-pool]]',
                     updated='2026-10-02T00:00:00+03:00')
        ticket['outputs'] = [{'path': 'wiki/connection-pool.md', 'before': self.before, 'after': hub},
                             {'path': 'wiki/pool-retry.md', 'before': None, 'after': retry}]
        ticket['decisions'][0].update(action='split', target='wiki/connection-pool.md',
                                      outputs=['wiki/connection-pool.md', 'wiki/connection-pool.md'],
                                      independent_use=True)
        for field in ('coverage', 'provenance_coverage'):
            ticket[field][0].update(path='wiki/pool-retry.md',
                                    sha256=digest(place.section(retry.encode(), 'Details')))
        bind(ticket)
        result = place.check(ticket, self.root)
        self.assertIn('SPLIT-OUTPUT', result['rules'])
        self.assertEqual('review', result['result'])
        self.apply_reviewed(ticket)
        result = place.check(ticket, self.root, post=True)
        self.assertIn('SPLIT-OUTPUT', result['rules'])
        self.assertNotEqual('verified_reviewed', result['result'])

    def test_cli_diagnostics_do_not_leak_ticket_contents(self):
        self.write('tmp/ticket.json', '{"private":"PRIVATE_TICKET_SENTINEL"}')
        out = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), contextlib.redirect_stdout(out):
            self.assertEqual(1, place.main(['check', '--ticket', 'tmp/ticket.json', '--json']))
        self.assertNotIn('PRIVATE_TICKET_SENTINEL', out.getvalue())
        self.assertEqual({'result': 'invalid', 'rules': ['TICKET']}, json.loads(out.getvalue()))

    def test_private_cli_argument_errors_are_redacted_on_both_streams(self):
        out, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(error):
            self.assertEqual(1, place.main(['candidates', '--concepts', '-PRIVATE_ARG_SENTINEL']))
        self.assertNotIn('PRIVATE_ARG_SENTINEL', out.getvalue() + error.getvalue())


if __name__ == '__main__':
    unittest.main()
