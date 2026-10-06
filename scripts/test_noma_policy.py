"""Synthetic byte-bound approval, stale-review and snapshot navigation regressions."""
import contextlib
import copy
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import noma_lib as lib
import noma_policy as policy


def seed_policy(root):
    for path in policy.CONTROL:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('synthetic control\n', encoding='utf-8')
    for slug, body in (
            ('agent-policy', '## Aktif Policy Kümesi\n- [[agent-read-policy]]\n'
             '- Referans: [[reference]]\n- Açık iş: [[pending]]\n'
             '## Mekanizma ve Durum Notları\n- [[mechanism]]\n'),
            ('agent-read-policy', '## Rule\nPRIVATE_POLICY_SENTINEL\n')):
        target = root / 'wiki' / f'{slug}.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('---\ntitle: "Synthetic"\ntype: decision\nstage: done\n'
                          'scope: systems\ncreated: 2026-10-01T00:00:00+03:00\n'
                          'updated: 2026-10-01T00:00:00+03:00\n---\n'
                          '# Synthetic\n## Links\n## Summary\nSynthetic.\n' + body,
                          encoding='utf-8')
    key = policy.propose(root, 'author-session')
    policy.record_review(root, key, 'independent-session')
    policy.activate(root, key, key)
    return key


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='noma-policy-', dir=lib.ROOT / 'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = seed_policy(self.root)

    def test_only_explicit_members_are_authority(self):
        _, bundle = policy.approved(self.root)
        self.assertEqual([policy.REGISTER, 'wiki/agent-read-policy.md'], bundle['policies'])
        for slug in ('reference', 'pending', 'mechanism', 'topic'):
            with self.subTest(slug=slug), self.assertRaises(policy.PolicyError):
                policy.resolve(self.root, slug)

    def test_worktree_edit_does_not_become_active_context(self):
        (self.root / 'wiki/agent-read-policy.md').write_text('UNAPPROVED_COMMAND', encoding='utf-8')
        result = policy.status(self.root)
        self.assertEqual('active', result['status'])
        self.assertEqual(['wiki/agent-read-policy.md'], result['paths'])
        approved_path = policy.resolve(self.root, 'agent-read-policy')
        self.assertIn('PRIVATE_POLICY_SENTINEL', policy.read_bytes(self.root, approved_path).decode())
        self.assertNotIn('UNAPPROVED_COMMAND', policy.read_bytes(self.root, approved_path).decode())

    def changed_proposal(self):
        path = self.root / 'wiki/agent-read-policy.md'
        path.write_text(path.read_text(encoding='utf-8') + 'New rule.\n', encoding='utf-8')
        return policy.propose(self.root, 'author-session')

    def test_missing_agent_or_human_confirmation_blocks_activation(self):
        key = self.changed_proposal()
        with self.assertRaises(policy.PolicyError):
            policy.activate(self.root, key, key)
        policy.record_review(self.root, key, 'independent-session')
        with self.assertRaises(policy.PolicyError):
            policy.activate(self.root, key, 'approval in a report or KRR-99')
        self.assertEqual(self.key, policy.approved(self.root)[0])

    def test_preparer_cannot_be_its_independent_reviewer(self):
        key = self.changed_proposal()
        with self.assertRaises(policy.PolicyError):
            policy.record_review(self.root, key, 'author-session')

    def test_one_byte_after_review_invalidates_approval(self):
        key = self.changed_proposal()
        policy.record_review(self.root, key, 'independent-session')
        with (self.root / 'wiki/agent-read-policy.md').open('ab') as stream:
            stream.write(b' ')
        with self.assertRaisesRegex(policy.PolicyError, 'STALE-CONTENT'):
            policy.activate(self.root, key, key)
        self.assertEqual(self.key, policy.approved(self.root)[0])

    def test_base_or_head_change_invalidates_proposal(self):
        key = self.changed_proposal()
        policy.record_review(self.root, key, 'independent-session')
        with mock.patch.object(policy, 'head', return_value='f' * 40):
            with self.assertRaisesRegex(policy.PolicyError, 'STALE-BASE'):
                policy.activate(self.root, key, key)

    def test_changed_loader_is_same_protected_scope(self):
        (self.root / 'scripts/noma_hermes_context.py').write_text('BYPASS', encoding='utf-8')
        self.assertEqual('blocked', policy.status(self.root)['status'])
        with self.assertRaises(policy.PolicyError):
            policy.resolve(self.root, 'agent-read-policy')

    def test_corrupt_snapshot_and_receipt_fail_closed(self):
        _, bundle = policy.approved(self.root)
        path = policy.object_path(bundle['files']['wiki/agent-read-policy.md'])
        (self.root / path).write_text('BYPASS', encoding='utf-8')
        self.assertEqual('blocked', policy.status(self.root)['status'])
        (self.root / policy.STATE).write_text('{bad PRIVATE_STATE', encoding='utf-8')
        self.assertEqual(['STATE'], policy.status(self.root)['rules'])

    def test_duplicate_json_keys_fail_closed(self):
        (self.root / policy.STATE).write_text('{"version":1,"version":1}', encoding='utf-8')
        self.assertEqual(['DUPLICATE-KEY'], policy.status(self.root)['rules'])

    def test_symlink_and_traversal_never_resolve(self):
        (self.root / 'alias').symlink_to(self.root / 'wiki', target_is_directory=True)
        for path in ('../wiki/agent-policy.md', '/wiki/agent-policy.md', 'alias/agent-policy.md'):
            with self.subTest(path=path), self.assertRaises(policy.PolicyError):
                policy.read_bytes(self.root, path)

    def test_status_and_resolve_do_not_print_content(self):
        out = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), contextlib.redirect_stdout(out):
            self.assertEqual(0, policy.main(['status', '--json']))
            self.assertEqual(0, policy.main(['resolve', 'agent-read-policy', '--json']))
        self.assertNotIn('PRIVATE_POLICY_SENTINEL', out.getvalue())
        self.assertNotIn('Synthetic', out.getvalue())

    def test_direct_receipt_rewrite_is_documented_host_bypass(self):
        # A writer with state access can forge an independent-review assertion.
        # This deliberately demonstrates the accepted detection-only boundary.
        key = self.changed_proposal()
        state = policy.load_state(self.root)
        entry = state['proposals'][key]
        entry['review'] = {'digest': key, 'base': self.key,
                           'reviewer': 'forged-session', 'verdict': 'approved'}
        entry['human'] = {'digest': key, 'base': self.key, 'source': 'live-user-session'}
        state['active'] = key
        policy.save_state(self.root, state)
        self.assertEqual(key, policy.approved(self.root)[0])

    def test_rejected_or_invalid_review_receipt_never_activates(self):
        key = self.changed_proposal()
        for review in ({'digest': key, 'base': self.key, 'reviewer': 'reviewer-session',
                        'verdict': 'rejected'},
                       {'digest': 'f' * 64, 'base': self.key, 'reviewer': 'reviewer-session',
                        'verdict': 'approved'}):
            with self.subTest(verdict=review['verdict'], digest=review['digest'][:8]):
                state = policy.load_state(self.root)
                state['proposals'][key]['review'] = review
                policy.save_state(self.root, state)
                with self.assertRaisesRegex(policy.PolicyError, 'REVIEW'):
                    policy.activate(self.root, key, key)
                self.assertEqual(self.key, policy.approved(self.root)[0])

    def test_protected_scope_shrink_migration_is_rejected(self):
        state = policy.load_state(self.root)
        entry = state['proposals'][self.key]
        bundle = copy.deepcopy(entry['bundle'])
        bundle['control'].remove('scripts/noma_board.py')
        bundle['files'].pop('scripts/noma_board.py')
        key = policy.payload_digest(bundle)
        state['proposals'][key] = {'bundle': bundle, 'review': entry['review'],
                                   'human': entry['human']}
        state['active'] = key
        policy.save_state(self.root, state)
        result = policy.status(self.root)
        self.assertEqual(['SCOPE'], result['rules'])
        self.assertEqual('blocked', result['status'])

    def test_control_scope_upgrade_is_reported(self):
        state = policy.load_state(self.root)
        entry = state['proposals'][self.key]
        bundle = copy.deepcopy(entry['bundle'])
        bundle['control'] = sorted(bundle['control'] + ['scripts/future_guard.py'])
        bundle['files']['scripts/future_guard.py'] = policy.digest(b'future guard\n')
        key = policy.payload_digest(bundle)
        for rel, expected in bundle['files'].items():
            data = (b'future guard\n' if rel == 'scripts/future_guard.py'
                    else policy.read_bytes(self.root, policy.object_path(expected)))
            self.assertEqual(policy.digest(data), expected)
            target = self.root / policy.object_path(expected)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        future = self.root / 'scripts' / 'future_guard.py'
        future.write_bytes(b'future guard\n')
        state['proposals'][key] = {'bundle': bundle,
                                   'review': {**entry['review'], 'digest': key},
                                   'human': {**entry['human'], 'digest': key}}
        state['active'] = key
        policy.save_state(self.root, state)
        result = policy.status(self.root)
        self.assertEqual(['SCOPE-UPGRADE'], result['rules'])
        self.assertEqual('blocked', result['status'])

    def test_repropose_before_activation_is_idempotent_and_preserves_review(self):
        key = self.changed_proposal()
        policy.record_review(self.root, key, 'independent-session')
        again = policy.propose(self.root, 'author-session')
        self.assertEqual(key, again)
        state = policy.load_state(self.root)
        entry = state['proposals'][key]
        self.assertEqual('independent-session', entry['review']['reviewer'])
        self.assertIsNone(entry['human'])
        self.assertEqual(self.key, state['active'])

    def test_quoted_archived_stage_is_rejected_before_publication(self):
        path = self.root / 'wiki' / 'agent-read-policy.md'
        path.write_text(path.read_text(encoding='utf-8')
                        .replace('stage: done', 'stage: "archived"'), encoding='utf-8')
        with self.assertRaisesRegex(policy.PolicyError, 'ARCHIVED'):
            policy.propose(self.root, 'author-session')

    def legacy_fixture(self):
        state = policy.load_state(self.root)
        for key, entry in state['proposals'].items():
            for path, expected in entry['bundle']['files'].items():
                target = self.root / policy.LEGACY_SNAPSHOTS / key / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(policy.read_bytes(self.root, policy.object_path(expected)))
        target = self.root / policy.LEGACY_STATE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(state), encoding='utf-8')
        shutil.rmtree(self.root / '.policy')
        return state

    def test_unchanged_policy_resolves_to_canonical_wiki_without_writing(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        self.assertEqual('wiki/agent-read-policy.md', policy.resolve(self.root, 'agent-read-policy'))
        self.assertEqual(before, sorted(p.relative_to(self.root) for p in self.root.rglob('*')))

    def test_objects_are_deduplicated_and_have_no_instruction_filenames(self):
        _, old = policy.approved(self.root)
        new_key = self.changed_proposal()
        new = policy.load_state(self.root)['proposals'][new_key]['bundle']
        expected = set(old['files'].values()) | set(new['files'].values())
        objects = list((self.root / policy.OBJECTS).iterdir())
        self.assertEqual(expected, {p.stem for p in objects})
        self.assertTrue(all(p.suffix == '.txt' for p in objects))
        self.assertFalse(list((self.root / '.policy').rglob('AGENTS.md')))
        self.assertFalse(list((self.root / '.policy').rglob('*.md')))

    def test_migration_preserves_all_receipts_and_removes_duplicate_trees(self):
        self.changed_proposal()
        state = self.legacy_fixture()
        policy.migrate(self.root)
        self.assertEqual(state, policy.load_state(self.root))
        self.assertEqual(self.key, policy.approved(self.root)[0])
        self.assertFalse((self.root / policy.LEGACY_STATE).exists())
        self.assertFalse((self.root / policy.LEGACY_SNAPSHOTS).exists())
        policy.migrate(self.root)

    def test_migration_rejects_extra_files_and_keeps_legacy_data(self):
        self.legacy_fixture()
        extra = self.root / policy.LEGACY_SNAPSHOTS / 'human-note.md'
        extra.write_text('PRIVATE_EXTRA', encoding='utf-8')
        with self.assertRaisesRegex(policy.PolicyError, 'LEGACY-EXTRA'):
            policy.migrate(self.root)
        self.assertEqual('PRIVATE_EXTRA', extra.read_text(encoding='utf-8'))
        self.assertTrue((self.root / policy.LEGACY_STATE).exists())
        self.assertFalse((self.root / policy.STATE).exists())

    def test_migration_rejects_tampered_source_and_object_collision(self):
        state = self.legacy_fixture()
        path, expected = next(iter(state['proposals'][self.key]['bundle']['files'].items()))
        source = self.root / policy.LEGACY_SNAPSHOTS / self.key / path
        original = source.read_bytes()
        source.write_bytes(b'tampered')
        with self.assertRaisesRegex(policy.PolicyError, 'SNAPSHOT'):
            policy.migrate(self.root)
        source.write_bytes(original)
        target = self.root / policy.object_path(expected)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'collision')
        with self.assertRaisesRegex(policy.PolicyError, 'SNAPSHOT'):
            policy.migrate(self.root)
        self.assertTrue(source.exists())
        self.assertFalse((self.root / policy.STATE).exists())

    def test_interrupted_cleanup_can_resume_without_changing_receipts(self):
        state = self.legacy_fixture()
        original = policy.os.unlink
        calls = []

        def interrupted(name, **kwargs):
            if not str(name).startswith('.policy-'):
                calls.append(name)
                if len(calls) == 2:
                    raise OSError('synthetic interruption')
            return original(name, **kwargs)

        with mock.patch.object(policy.os, 'unlink', side_effect=interrupted):
            with self.assertRaises(OSError):
                policy.migrate(self.root)
        self.assertTrue((self.root / policy.STATE).exists())
        policy.migrate(self.root)
        self.assertEqual(state, policy.load_state(self.root))
        self.assertFalse((self.root / policy.LEGACY_STATE).exists())

    def test_legacy_mutation_requires_explicit_migration(self):
        self.legacy_fixture()
        with self.assertRaisesRegex(policy.PolicyError, 'MIGRATION-REQUIRED'):
            policy.propose(self.root, 'author-session')

    def test_mutation_accepts_exact_directory_claim_with_trailing_slash(self):
        self.legacy_fixture()
        run = {'run_id': 'owner', 'working_files': ['.policy/', policy.LEGACY_STATE,
                                                  policy.LEGACY_SNAPSHOTS + '/']}
        with mock.patch.object(policy.noma_board.Board, 'status', return_value={'runs': [run]}):
            with policy.mutation(self.root, 'owner'):
                pass
        run['working_files'].remove(policy.LEGACY_SNAPSHOTS + '/')
        with mock.patch.object(policy.noma_board.Board, 'status', return_value={'runs': [run]}):
            with self.assertRaisesRegex(policy.PolicyError, 'CLAIM'):
                with policy.mutation(self.root, 'owner'):
                    self.fail('Missing legacy claim must block mutation')

    def test_decision_status_comes_from_approved_ledger_not_pending_wording(self):
        register = self.root / policy.REGISTER
        register.write_text(register.read_text(encoding='utf-8').replace(
            '- [[agent-read-policy]]', '- [[agent-read-policy]]\n- [[insan-karar-defteri]]'),
            encoding='utf-8')
        ledger = self.root / 'wiki/insan-karar-defteri.md'
        ledger.write_text('### KRR-50\n**Synthetic** · activation pending · [[agent-read-policy]]\n',
                          encoding='utf-8')
        key = policy.propose(self.root, 'author-session')
        policy.record_review(self.root, key, 'independent-session')
        policy.activate(self.root, key, key)
        self.assertEqual({'status': 'active', 'paths': ['wiki/agent-read-policy.md']},
                         policy.decision_status(self.root, 'KRR-50'))
        ledger.write_text(ledger.read_text(encoding='utf-8') +
                          '### KRR-51\n**Synthetic** · [[agent-read-policy]]\n', encoding='utf-8')
        self.assertEqual('pending', policy.decision_status(self.root, 'KRR-51')['status'])
        with self.assertRaisesRegex(policy.PolicyError, 'DECISION'):
            policy.decision_status(self.root, 'KRR-99')


class PublicHookExclusionTests(unittest.TestCase):
    def test_approval_archive_is_excluded_from_public_content_hooks(self):
        config = (lib.ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8')
        exclusions = re.findall(r"^\s+exclude: '([^']+)'$", config, re.M)
        self.assertTrue(exclusions)
        for pattern in exclusions:
            for path in (policy.STATE, policy.object_path('0' * 64)):
                with self.subTest(pattern=pattern, path=path):
                    self.assertIsNotNone(re.search(pattern, path))


if __name__ == '__main__':
    unittest.main()
