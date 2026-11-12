"""Kiểm chứng retry bị giới hạn và timeline không bị bỏ dở khi trả lời."""
import json
import unittest
from unittest.mock import patch

from agent import run_agent
from bonus.tools import BonusTools
from bonus_policy import BonusPolicy
from test_lab import FakeProvider, final, tool_call


class BonusPolicyTests(unittest.TestCase):
    def test_retry_request_cannot_be_replaced_with_promise_in_answer(self):
        tools = BonusTools(scenario='rate_limit_once')
        provider = FakeProvider([
            tool_call('first', 'get_vercel_status', '{}'),
            final('Đang retry nhưng chưa xác minh.'),
            tool_call('retry', 'get_vercel_status', '{}'),
            final('Theo snapshot, Vercel operational. https://www.vercel-status.com'),
        ])
        result = run_agent('Kiểm tra Vercel, retry rate limit có giới hạn', provider, tools, 4)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 2)
        self.assertTrue(any(t['event'] == 'validation_pending_bonus_actions'
                            for t in result['trace']))

    def test_incident_comparison_requires_details_from_status_evidence(self):
        tools = BonusTools()
        policy = BonusPolicy(tools.schemas, 'Đối chiếu incident mới nhất và phạm vi')
        status = policy.execute(tools, 'get_npm_status', {'component': 'package publishing'})
        action = policy.pending_actions()[0]
        self.assertEqual(action['name'], 'get_incident_details')
        self.assertEqual(action['arguments']['incident_id'], status['incidents'][0]['id'])
        policy.execute(tools, action['name'], action['arguments'])
        self.assertEqual(policy.pending_actions(), [])

    def test_persistent_rate_limit_stops_actual_api_calls(self):
        tools = BonusTools(scenario='rate_limit_always')
        policy = BonusPolicy(tools.schemas, 'Kiểm tra status')
        results = [policy.execute(tools, 'get_vercel_status', {}) for _ in range(4)]
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 3)
        self.assertFalse(results[2]['retriable'])
        self.assertEqual(results[3]['error'], 'RETRY_LIMIT')

    def test_long_retry_after_stops_without_wait_or_second_api_call(self):
        class LimitedTools:
            count = 0
            def execute(self, name, args):
                self.count += 1
                return {'ok': False, 'error': 'RATE_LIMITED',
                        'retry_after': '120', 'retriable': True}

        tools = LimitedTools()
        policy = BonusPolicy(BonusTools.schemas, 'Kiểm tra status')
        with patch('bonus_policy.time.sleep') as sleep:
            first = policy.execute(tools, 'get_vercel_status', {})
            second = policy.execute(tools, 'get_vercel_status', {})
        self.assertFalse(first['retriable'])
        self.assertEqual(second['error'], 'RETRY_BUDGET_EXCEEDED')
        self.assertEqual(tools.count, 1)
        sleep.assert_not_called()

    def test_http_date_retry_after_is_parsed(self):
        delay = BonusPolicy.retry_delay({'retry_after': 'Wed, 01 Jan 2100 00:00:00 GMT'})
        self.assertGreater(delay, 5)

    def test_noise_is_omitted_from_context_but_preserved_in_trace(self):
        tools = BonusTools(scenario='noisy')
        provider = FakeProvider([
            tool_call('a', 'get_vercel_status', '{}'), final('Theo snapshot.')])
        result = run_agent('Kiểm tra Vercel', provider, tools)
        observation = json.loads(provider.histories[1][-1]['content'])
        self.assertNotIn('distractors', observation)
        self.assertEqual(observation['omitted_distractors_count'], 160)
        evidence = next(t['result'] for t in result['trace'] if t['event'] == 'tool')
        self.assertEqual(len(evidence['distractors']), 160)

    def test_full_timeline_requires_next_page_and_uses_bonus_schema(self):
        tools = BonusTools()
        args = {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg', 'limit': 3}
        first = tools.get_incident_details(**args)
        next_args = {**args, 'offset': first['next_offset']}
        second = tools.get_incident_details(**next_args)
        last_args = {**args, 'offset': second['next_offset']}
        last = tools.get_incident_details(**last_args)
        self.assertIsNone(last['next_offset'])
        provider = FakeProvider([
            tool_call('first', 'get_incident_details', json.dumps(args)),
            final('Chưa xem hết. ' + first['url']),
            tool_call('next', 'get_incident_details', json.dumps(next_args)),
            final('Còn trang chưa đọc. ' + first['url']),
            tool_call('last', 'get_incident_details', json.dumps(last_args)),
            final('Theo timeline đã đọc. ' + first['url']),
        ])
        result = run_agent('Đọc toàn bộ timeline Vercel', provider, tools, 6)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(t['event'] == 'validation_unread_pages' for t in result['trace']))
        self.assertEqual([t['step'] for t in result['trace'] if t['event'] == 'tool'], [1, 3, 5])

    def test_unread_page_at_budget_limit_does_not_complete(self):
        tools = BonusTools()
        args = {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg', 'limit': 3}
        url = tools.get_incident_details(**args)['url']
        provider = FakeProvider([
            tool_call('first', 'get_incident_details', json.dumps(args)), final(url)])
        result = run_agent('Đọc timeline', provider, tools, 2)
        self.assertEqual(result['status'], 'max_steps')
