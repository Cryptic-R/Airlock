from concurrent.futures import ThreadPoolExecutor
import pytest
from common import service
from engine.seed import INBOX

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr('common.asi1.ASI1_API_KEY', '')
    service._sessions.clear()


def test_repeat_and_restart_skip_planner_and_payment(monkeypatch):
    service.run_messages('alice', [INBOX[0]])
    service._sessions.clear()
    def forbidden(*args):
        raise AssertionError('duplicate invoked planner')
    monkeypatch.setattr('engine.llm.LLMPlanner.plan', forbidden)
    result = service.run_messages('alice', [INBOX[0]])
    assert len(result['skipped']) == 1
    assert result['paid_count'] == 1
    assert result['audit_ok']


def test_concurrent_duplicate_is_applied_once():
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.run_messages('alice', [INBOX[0]]), range(2)))
    assert sum(len(r['handled']) for r in results) == 1
    assert service.run_messages('alice', [INBOX[0]])['paid_count'] == 1


def test_state_isolated_by_user():
    assert service.run_messages('alice', [INBOX[0]])['paid_count'] == 1
    assert len(service.run_messages('bob', [INBOX[0]])['handled']) == 1


def test_approvals_survive_restart_and_execute_once():
    result = service.run_messages('alice', [INBOX[3]])
    signature = result['decisions'][0]['signature']
    service._sessions.clear()
    assert service.approve('alice', signature)
    service._sessions.clear()
    with pytest.raises(KeyError):
        service.approve('alice', signature)
    assert service.run_messages('alice', [INBOX[3]])['paid_count'] == 1


def test_changed_id_blocks_and_attachments_fail_closed():
    service.run_messages('alice', [INBOX[0]])
    altered = dict(INBOX[0], body='Amount due $200.00')
    assert service.run_messages('alice', [altered])['blocked']
    attached = dict(INBOX[1], attachments=[{'name': 'invoice.pdf', 'scan': 'clean'}])
    result = service.run_messages('alice', [attached])
    assert result['blocked'] and result['paid_count'] == 1


def test_stains_survive_restart():
    service.run_messages('alice', [{'id':'plant','subject':'Acme Power remittance', 'body':'Note: remittance route RM-7781'}])
    service._sessions.clear()
    result = service.run_messages('alice', [INBOX[0]])
    assert result['paid_count'] == 0 and result['decisions']
