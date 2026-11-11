"""Kiểm tra lỗi provider và ngoại lệ tool không làm mất contract của loop."""
import json
import unittest

from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class RobustnessTests(unittest.TestCase):
    def test_provider_failure_returns_error_without_exception_text(self):
        class BrokenProvider:
            def complete(self, messages, schemas):
                raise RuntimeError('private-provider-data')

        result = run_agent('Kiểm tra trạng thái', BrokenProvider(), StatusTools())
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['trace'][-1]['event'], 'provider_error')
        self.assertNotIn('private-provider-data', json.dumps(result))

    def test_tool_exception_is_returned_and_other_call_still_runs(self):
        class PartialTools:
            def execute(self, name, args):
                if args['provider'] == 'cloudflare':
                    raise TimeoutError('private-tool-data')
                return {'provider': 'github', 'overall': {'indicator': 'none'}}

        first = tool_call('cf', 'get_status', '{"provider":"cloudflare"}')
        second = tool_call('gh', 'get_status', '{"provider":"github"}')
        first['calls'] += second['calls']
        first['message']['tool_calls'] += second['message']['tool_calls']
        provider = FakeProvider([first, final('Cloudflare chưa xác minh được.')])
        result = run_agent('Kiểm tra hai provider', provider, PartialTools())

        self.assertEqual(result['status'], 'completed')
        observations = [m for m in provider.histories[1] if m['role'] == 'tool']
        self.assertEqual([m['tool_call_id'] for m in observations], ['cf', 'gh'])
        self.assertEqual(json.loads(observations[0]['content'])['error'], 'TimeoutError')
        self.assertEqual(json.loads(observations[1]['content'])['provider'], 'github')
        self.assertNotIn('private-tool-data', json.dumps(result))
        self.assertEqual(provider.histories[1][-1]['role'], 'system')
        self.assertTrue(any(t['event'] == 'status_evidence_warning'
                            for t in result['trace']))

    def test_unread_related_incident_requires_another_tool_step(self):
        class LinkedTools:
            def execute(self, name, args):
                incident_id = args['incident_id']
                body = ('See https://www.githubstatus.com/incidents/second'
                        if incident_id == 'first' else 'Root cause: configuration error.')
                return {'ok': True, 'url': 'https://example.com/' + incident_id,
                        'updates': [{'body': body}]}

        provider = FakeProvider([
            tool_call('a', 'get_incident_details', '{"provider":"github","incident_id":"first"}'),
            final('Chưa đọc link. https://example.com/first'),
            tool_call('b', 'get_incident_details', '{"provider":"github","incident_id":"second"}'),
            final('Lỗi cấu hình. https://example.com/second'),
        ])
        result = run_agent('Tìm nguyên nhân theo liên kết', provider, LinkedTools(), 4)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([t['step'] for t in result['trace'] if t['event'] == 'tool'], [1, 3])
        self.assertTrue(any(t['event'] == 'validation_unread_incidents'
                            for t in result['trace']))

    def test_unread_link_at_budget_limit_does_not_complete(self):
        class LinkedTools:
            def execute(self, name, args):
                return {'ok': True, 'url': 'https://example.com/first',
                        'updates': [{'body': 'See https://www.githubstatus.com/incidents/second'}]}

        provider = FakeProvider([
            tool_call('a', 'get_incident_details', '{"provider":"github","incident_id":"first"}'),
            final('https://example.com/first'),
        ])
        result = run_agent('Tìm nguyên nhân', provider, LinkedTools(), 2)
        self.assertEqual(result['status'], 'max_steps')
