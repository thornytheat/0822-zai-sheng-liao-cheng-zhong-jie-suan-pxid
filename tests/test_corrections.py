import io

import pytest

from app.business import DomainIssue
from app.review.corrections import submit
from app.review.service import execute, review
from corrections_data import only_groups, rewrite


@pytest.fixture
def issued(store, clean):
    run = execute(store, clean)
    review(store, run['id'], dict(revision=0, status='APPROVED', note='首次签发完成'))
    return run['id']


def paid(result):
    return {row['item']: row['amount_g'] for row in result['supplements']}


def test_correction_requires_issued_batch(store, clean):
    run = execute(store, clean)
    with pytest.raises(DomainIssue, match='RUN_NOT_APPROVED'):
        submit(store, run['id'], rewrite(clean, {('0001', 'reject', '31'): 0}), '首次更正')
    review(store, run['id'], dict(revision=0, status='HELD', note='暂缓待核对'))
    with pytest.raises(DomainIssue, match='RUN_NOT_APPROVED'):
        submit(store, run['id'], rewrite(clean, {('0001', 'reject', '31'): 0}), '首次更正')


def test_correction_reads_back_original_amounts(store, clean, issued):
    touched = rewrite(clean, {('0001', 'reject', '31'): 0})
    submit(store, issued, touched, '杂质复检')
    original = store.correction(issued, store.corrections(issued)[0]['id'])['original']
    assert original['0001:31']['payable_g'] == 85500
    assert original['0001:31']['basis'] == {'case': '0001', 'ticket': '31', 'net_g': 100000,
                                            'dry_g': 90000, 'payable_g': 85500, 'reject_bp': 500}
    assert store.load(issued)['report']['cases'][0]['measure']['value'] == 85500


def test_first_correction_pays_only_the_difference(store, clean, issued):
    result = submit(store, issued, rewrite(clean, {('0001', 'reject', '31'): 0}), '杂质复检')
    assert result['status'] == 'PAID'
    assert paid(result) == {'0001:31': 4500}


def test_two_corrections_accumulate_to_latest_gap(store, clean, issued):
    first = submit(store, issued, rewrite(clean, {('0001', 'reject', '31'): 0}), '第一次更正')
    second = submit(store, issued, rewrite(clean, {('0001', 'reject', '31'): 0,
                                                   ('0001', 'moisture', '31'): 500}), '第二次更正')
    assert paid(first) == {'0001:31': 4500}
    assert paid(second) == {'0001:31': 5000}
    assert second['supplements'][0]['paid_before_g'] == 4500
    assert second['supplements'][0]['paid_after_g'] == 9500

    ledger = store.ledger(issued)
    assert ledger['paid_g'] == 9500
    assert ledger['gap_g'] == 9500
    assert ledger['latest_g'] - ledger['original_g'] == ledger['paid_g']
    assert ledger['settled'] and not ledger['pending_g']


def test_retry_does_not_duplicate(store, clean, issued):
    touched = rewrite(clean, {('0001', 'reject', '31'): 0})
    first = submit(store, issued, touched, '第一次更正')
    again = submit(store, issued, touched, '第一次更正')
    assert again['id'] == first['id']
    assert len(store.corrections(issued)) == 1
    assert store.ledger(issued)['paid_g'] == 4500


def test_contamination_after_correction_holds_supplement(store, clean, issued):
    result = submit(store, issued, rewrite(clean, {('0001', 'reject', '31'): 3000}), '杂质复检')
    assert result['status'] == 'PENDING' and result['reason'] == 'CONTAMINATION_LIMIT'
    assert result['supplements'][0]['status'] == 'PENDING'
    ledger = store.ledger(issued)
    assert ledger['paid_g'] == 0 and ledger['pending_g'] == 0
    assert not ledger['settled']
    assert store.load(issued)['report']['cases'][0]['measure']['value'] == 85500


def test_recovery_is_left_pending(store, clean, issued):
    submit(store, issued, rewrite(clean, {('0001', 'reject', '31'): 0}), '第一次更正')
    lower = rewrite(clean, {('0001', 'reject', '31'): 1000})
    result = submit(store, issued, lower, '回调杂质')
    entry = result['supplements'][0]
    assert entry['status'] == 'PENDING' and entry['reason'] == 'RECOVERY_NOT_ALLOWED'
    # 最新应付 81000，原签发 85500，已补 4500；要凑齐差额需追回 9000。
    assert entry['latest_g'] == 81000 and entry['amount_g'] == -9000
    ledger = store.ledger(issued)
    assert ledger['paid_g'] == 4500 and ledger['recovery_g'] == 9000
    assert ledger['gap_g'] == -4500
    assert not ledger['settled']


def test_unbalanced_correction_pays_nothing(store, clean, issued):
    broken = rewrite(clean, {('0001', 'reject', '31'): 0}) + b'BROKEN,row\n'
    result = submit(store, issued, broken, '带坏行更正')
    assert result['status'] == 'PENDING'
    assert all(row['status'] == 'PENDING' for row in result['supplements'])
    assert store.ledger(issued)['paid_g'] == 0


def test_correction_cannot_change_scope(store, clean, issued):
    with pytest.raises(DomainIssue, match='CORRECTION_SCOPE'):
        submit(store, issued, only_groups(clean, {'0001'}), '漏掉一组')


def test_pending_supplement_is_superseded_by_later_fix(store, clean, issued):
    submit(store, issued, rewrite(clean, {('0001', 'reject', '31'): 3000}), '杂质超限')
    pending = store.ledger(issued)['tickets']
    assert pending[0]['status'] == 'PENDING'
    fixed = submit(store, issued, rewrite(clean, {('0001', 'reject', '31'): 0}), '撤销超限')
    assert fixed['status'] == 'PAID'
    ledger = store.ledger(issued)
    assert ledger['settled'] and ledger['paid_g'] == 4500
    assert ledger['pending_g'] == 0


def test_restoring_original_after_payment_holds_recovery(store, clean, issued):
    touched = rewrite(clean, {('0001', 'reject', '31'): 0})
    submit(store, issued, touched, '第一次更正')
    restored = submit(store, issued, clean, '来源复原')
    assert restored['status'] == 'PENDING'
    assert restored['supplements'][0]['reason'] == 'RECOVERY_NOT_ALLOWED'
    assert store.ledger(issued)['paid_g'] == 4500


def test_correction_unknown_run_is_404(client, clean):
    response = client.post('/api/runs/unknown/corrections',
                           data={'file': (io.BytesIO(clean), 'fix.csv')})
    assert response.status_code == 404


def test_http_correction_flow(client, clean):
    run = client.post('/api/runs', data={'sample': 'clean'}).json
    assert client.post(f"/api/runs/{run['id']}/corrections",
                       data={'file': (io.BytesIO(rewrite(clean, {('0001', 'reject', '31'): 0})),
                                      'fix.csv')}).status_code == 409
    client.patch(f"/api/runs/{run['id']}",
                 json=dict(revision=0, status='APPROVED', note='首次签发完成'))
    response = client.post(f"/api/runs/{run['id']}/corrections",
                           data={'file': (io.BytesIO(rewrite(clean, {('0001', 'reject', '31'): 0})),
                                          'fix.csv'),
                                 'reference': '化验单 A-17'})
    assert response.status_code == 200
    assert response.json['status'] == 'PAID'
    assert response.json['reference'] == '化验单 A-17'
    ledger = client.get(f"/api/runs/{run['id']}/ledger").json
    assert ledger['paid_g'] == 4500 and ledger['settled']
    evidence = client.get(f"/api/runs/{run['id']}/evidence").json
    assert evidence['ledger']['paid_g'] == 4500
