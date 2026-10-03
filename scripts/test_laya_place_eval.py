"""Model-free placement evaluation integrity and fallback regressions."""
import copy
import unittest

import laya_place_eval as evaluation
from noma_policy import PolicyError


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = evaluation.dataset()

    def test_family_chunks_languages_and_paraphrases_never_cross_splits(self):
        split = evaluation.grouped_split(self.examples)
        self.assertEqual({'train': 500, 'calib': 200, 'test': 300}, {k: len(v) for k, v in split.items()})
        groups = {k: {ex['family'] for ex in values} for k, values in split.items()}
        for a, b in (('train', 'calib'), ('train', 'test'), ('calib', 'test')):
            self.assertFalse(groups[a] & groups[b])
        self.assertEqual(250, len({ex['source_group'] for ex in self.examples}))

    def test_real_shortlist_miss_is_not_repaired_using_gold(self):
        misses = [ex for ex in self.examples if ex['retrieval_miss_case']]
        self.assertTrue(misses)
        self.assertTrue(all(ex['gold_target'] not in {h['path'] for h in ex['shortlist']} for ex in misses))
        self.assertTrue(all(ex['gold_target'] not in evaluation.questions(ex)['placement_target']['criteria'] for ex in misses))
        # Miss coverage is represented in both calibration and test partitions.
        split = evaluation.grouped_split(self.examples)
        for part in ('calib', 'test'):
            self.assertTrue(any(ex['retrieval_miss_case'] for ex in split[part]),
                            f'{part} partition lacks retrieval-miss coverage')

    def test_model_state_contains_no_labels_or_gold_target_flags(self):
        state = evaluation.state_text(self.examples[0])
        for forbidden in ('gold_action', 'gold_target', 'retrieval_miss_case', 'valuable'):
            self.assertNotIn(forbidden, state)

    def test_frozen_baseline_uses_evidence_not_gold(self):
        ex = copy.deepcopy(self.examples[0])
        answer = evaluation.rubric_baseline(ex)
        ex.update(gold_action='review', gold_target='invented')
        self.assertEqual(answer, evaluation.rubric_baseline(ex))

    def row(self, **overrides):
        row = {'action': 'merge', 'target': 'wiki/topic-note.md', 'reason': None,
               'action_probs': {'merge': 0.90, 'create': 0.025, 'split': 0.025, 'noop': 0.025, 'review': 0.025},
               'target_probs': {'wiki/topic-note.md': 0.85, 'none': 0.15},
               'gold_action': 'create', 'gold_target': 'none', 'valuable': True,
               'shortlist': ['wiki/topic-note.md'], 'latency_ms': 10}
        row.update(overrides)
        return row

    def test_wrong_prediction_confidence_is_not_derived_from_gold(self):
        result = evaluation.metrics([self.row()], {'temperature': 1, 'threshold': 0.8})
        self.assertEqual(1, result['high_confidence_error'])
        self.assertGreater(result['brier'], 1)
        self.assertEqual(1, result['false_actions']['merge']['errors'])
        self.assertEqual(0, result['end_to_end'])

    def test_wrong_target_is_false_merge_even_with_right_action(self):
        result = evaluation.metrics([self.row(gold_action='merge', gold_target='wiki/other.md')],
                                    {'temperature': 1, 'threshold': 0.8})
        self.assertEqual(1, result['retrieval']['misses'])
        self.assertEqual(1, result['false_actions']['merge']['errors'])

    def test_forced_fallback_review_is_not_credited_as_model_accuracy(self):
        row = self.row(action='review', gold_action='review', target='none', reason='TRUNCATION')
        result = evaluation.metrics([row], {'temperature': 1, 'threshold': 0.8})
        self.assertEqual(0, result['end_to_end'])
        self.assertEqual(0, result['per_class']['review']['f1'])
        self.assertEqual(0, result['selective_coverage'])

    def test_timeout_missing_fields_and_truncation_fall_back_without_throwing(self):
        for payload in (None, {}, {'usage': {'truncated': True}},
                        {'usage': {'options': {'a': {'total': 2, 'distinct': 1}}}}):
            class FakeRouter:
                def predict(self, *args, **kwargs):
                    if payload is None:
                        raise TimeoutError
                    return payload
            result = evaluation.predict(FakeRouter(), self.examples[0])
            self.assertEqual('review', result['action'])
            self.assertIsNotNone(result['reason'])

    def test_calibration_only_uses_the_rows_supplied_to_it(self):
        rows = [self.row(gold_action='merge', gold_target='wiki/topic-note.md')]
        calibration = evaluation.fit_calibration(rows)
        self.assertEqual(1, calibration['n'])
        self.assertEqual(1, calibration['target_n'])
        self.assertGreaterEqual(calibration['temperature'], 0.5)
        self.assertLessEqual(calibration['temperature'], 5)
        self.assertGreaterEqual(calibration['target_temperature'], 0.5)
        self.assertLessEqual(calibration['target_temperature'], 5)
        # Held-out outcomes are not an argument to the calibration function.
        self.assertEqual(calibration, evaluation.fit_calibration(copy.deepcopy(rows)))

    def test_nan_probability_is_not_a_valid_decision(self):
        ex = self.examples[0]
        raw = {'usage': {}, 'routing': {'model': 'multilingual'}, 'answers': {
            'placement_action': {'choice': 'create', 'probabilities': {a: float('nan') for a in evaluation.ACTIONS}},
            'placement_target': {'choice': 'none', 'probabilities': {'none': 1}}}}
        with self.assertRaises(PolicyError):
            evaluation.normalize(raw, ex)

    def test_real_alarm_deadline_fires_timeout_fallback(self):
        import time
        class SleepingRouter:
            def predict(self, *args, **kwargs):
                time.sleep(0.5)
                return {}
        result = evaluation.predict(SleepingRouter(), self.examples[0], deadline=0.1)
        self.assertEqual(('review', 'none', 'TIMEOUT'),
                         (result['action'], result['target'], result['reason']))

    def test_error_code_payload_falls_back_without_raising(self):
        class ErrorCodeRouter:
            def predict(self, *args, **kwargs):
                return {'error': {'code': 'HEAD-OVERFLOW', 'message': 'PRIVATE_ERROR_DETAIL'}}
        result = evaluation.predict(ErrorCodeRouter(), self.examples[0])
        self.assertEqual(('review', 'none', 'MODEL-FAILURE'),
                         (result['action'], result['target'], result['reason']))

    def consistent_raw(self, action_choice, target_choice):
        ex = self.examples[0]
        targets = evaluation.questions(ex)['placement_target']['criteria']
        return {'usage': {}, 'routing': {'model': 'multilingual'}, 'answers': {
            'placement_action': {'choice': action_choice,
                                 'probabilities': {a: 1 / len(evaluation.ACTIONS) for a in evaluation.ACTIONS}},
            'placement_target': {'choice': target_choice,
                                 'probabilities': {t: 1 / len(targets) for t in targets}}}}

    def test_empty_selection_choice_falls_back_to_review(self):
        payload = self.consistent_raw('', 'none')
        class EmptyChoiceRouter:
            def predict(self, *args, **kwargs):
                return payload
        result = evaluation.predict(EmptyChoiceRouter(), self.examples[0])
        self.assertEqual(('review', 'none', 'ANSWER'),
                         (result['action'], result['target'], result['reason']))

    def test_inconsistent_action_target_pair_is_rejected(self):
        payload = self.consistent_raw('create', self.examples[0]['shortlist'][0]['path'])
        class MismatchRouter:
            def predict(self, *args, **kwargs):
                return payload
        result = evaluation.predict(MismatchRouter(), self.examples[0])
        self.assertEqual(('review', 'none', 'ACTION-TARGET'),
                         (result['action'], result['target'], result['reason']))

    def test_all_fallback_variants_stay_identical_empty_review_rows(self):
        class DeadRouter:
            def predict(self, *args, **kwargs):
                raise TimeoutError
        rows = [evaluation.predict(DeadRouter(), self.examples[0], variant=i) for i in (0, 1, 2)]
        for row in rows:
            self.assertEqual(('review', 'none', 'TIMEOUT'),
                             (row['action'], row['target'], row['reason']))
            self.assertEqual({}, row['action_probs'])
            self.assertEqual({}, row['target_probs'])

    def test_calibration_without_qualifying_threshold_returns_none(self):
        rows = [self.row(gold_action='create', gold_target='wiki/other.md')]
        calibration = evaluation.fit_calibration(rows)
        self.assertIsNone(calibration['threshold'])

    def test_non_multilingual_route_is_rejected(self):
        raw = self.consistent_raw('merge', 'none')
        raw['routing']['model'] = 'legacy'
        with self.assertRaisesRegex(PolicyError, 'ROUTE'):
            evaluation.normalize(raw, self.examples[0])

    def test_grouped_split_is_deterministic(self):
        first = evaluation.grouped_split(self.examples)
        second = evaluation.grouped_split(self.examples)
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
