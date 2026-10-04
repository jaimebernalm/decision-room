"""Provider size regressions, with synthetic growing evidence and no network."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from decision_room.agent.schema_limits import bound_enums, enum_count, validate_enum_limits
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.research_context import prompt_context
from decision_room.agent.research_contract import validate_research_action
from decision_room.agent.research_continuity import ContinuityAction
from test_research_continuity import fixtures, action, ref, closure
import test_model_strict_schemas as strict_tests
from test_model_strict_schemas import assert_strict_objects


class SchemaLimitTests(unittest.TestCase):
    def test_guard_counts_duplicate_occurrences_and_boundary(self):
        schema = {'anyOf': [{'enum': ['same'] * 500}, {'enum': ['same'] * 500}]}
        self.assertEqual(enum_count(schema), 1000)
        validate_enum_limits(schema)
        schema['anyOf'].append({'enum': ['extra']})
        with self.assertRaisesRegex(ValueError, '1001 enum values'):
            validate_enum_limits(schema)

    def test_exact_patterns_preserve_literals_and_do_not_mutate_small_schemas(self):
        values = [f'key_{i}' for i in range(1001)] + ['a.b', 'a|b', '[x]', 'x\\y', '', 'line\nend', 'a"b']
        original = {'type': 'string', 'enum': values}
        bounded = bound_enums(original)
        v = Draft202012Validator(bounded)
        for value in values:
            self.assertTrue(v.is_valid(value), value)
        for value in ['unknown', 'key_0\n', 'axb', 'a', 'b', 'x', 1, None]:
            self.assertFalse(v.is_valid(value), repr(value))
        self.assertEqual(original, {'type': 'string', 'enum': values})
        small = {'type': 'string', 'enum': ['a', 'b']}
        self.assertEqual(bound_enums(small), small)

    def test_large_string_enum_limit_is_checked_even_below_1000_values(self):
        schema = {'type': 'string', 'enum': [f'{i:03}' + 'x' * 60 for i in range(251)]}
        with self.assertRaisesRegex(ValueError, '15000'):
            validate_enum_limits(schema)
        validate_enum_limits(bound_enums(schema))

    def test_uncompactable_overflow_stops_before_http_or_credentials(self):
        schema = {'type': 'object', 'properties': {'n': {'type': 'integer', 'enum': list(range(1001))}},
                  'required': ['n'], 'additionalProperties': False}
        client = ModelClient(ModelSettings('test', protocol='openai', base_url='https://api.openai.com/v1'))
        with patch('decision_room.agent.model.httpx.Client') as http:
            with self.assertRaisesRegex(ValueError, '1001 enum values'):
                client._generate({}, None, 'test', schema)
            http.assert_not_called()

    def test_1200_accumulated_keys_fit_wire_and_keep_validator_parity(self):
        s, o, b = fixtures()
        observations = []
        for i in range(15):
            obs = deepcopy(o[0]); obs.update(execution_id=f'e{i}', step=i+1)
            obs['result']['metrics'] = {f'm_{i}_{j}': j for j in range(80)}
            observations.append(obs)
        b.update(max_executions=30, max_attempts_per_investigation=30, max_context_bytes=300000)
        context = prompt_context(s, observations, [], b, 15)
        self.assertEqual(sum(len(o['result']['metrics']) for o in context['observations']), 1200)
        client = ModelClient(ModelSettings('test'))
        with patch.object(client, '_generate', return_value=({}, {})) as generated:
            client.generate_research(context)
        self.assertGreater(enum_count(generated.call_args.args[3]), 1000)
        context['business_context'] = {'retrievals': [], 'profile': {'name': 'Synthetic'}}
        schema = strict_tests.StrictProviderSchemaTests().capture('generate_research', context)
        assert_strict_objects(self, schema)
        self.assertLessEqual(enum_count(schema), 1000)
        validator = Draft202012Validator(schema)
        for i in range(15):
            a = ContinuityAction.model_validate(action('record_candidate',
                evidence_refs=[ref(f'e{i}', metrics=[f'm_{i}_79'])], closure=closure())).model_dump()
            validator.validate({'decision': {**a, 'retrieval': None}})
            validate_research_action(a, s, observations, [], b)
            for invalid in ('invented', f'm_{(i+1)%15}_79', f'm_{i}_79\n'):
                bad = deepcopy(a); bad['evidence_refs'][0]['metric_keys'] = [invalid]
                self.assertFalse(validator.is_valid({'decision': {**bad, 'retrieval': None}}))
                with self.assertRaises(ValueError):
                    validate_research_action(bad, s, observations, [], b)
        for branch in schema['properties']['decision']['anyOf']:
            self.assertEqual(branch['properties']['metric_keys']['maxItems'], 0)
            self.assertNotIn('enum', branch['properties']['metric_keys']['items'])
