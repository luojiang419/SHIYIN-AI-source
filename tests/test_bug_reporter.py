import json

from canvas_core.bug_reporter import BugReporter


def test_user_heartbeat_is_throttled_and_includes_cached_machine(tmp_path):
    reporter = BugReporter(tmp_path, source='http://127.0.0.1:1')
    reporter._hardware = {'cpu': [{'Name': 'Test CPU'}]}
    reporter.mark_user_active('user_abc')
    reporter.mark_user_active('user_abc')
    reports = [json.loads(path.read_text('utf-8')) for path in reporter.pending.glob('*.json')]
    user_reports = [report for report in reports if report.get('userId') == 'user_abc']
    assert len(user_reports) == 1
    assert user_reports[0]['machine']['cpu'][0]['Name'] == 'Test CPU'
