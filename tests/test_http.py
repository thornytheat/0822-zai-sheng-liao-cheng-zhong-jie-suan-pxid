import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('stage',['intake','prepare','calculate','policy','balance'])
def test_stage_has_http_entry_and_no_database_write(client,stage):
    response=client.post('/api/stages/'+stage,data={'sample':'dirty'})
    assert response.status_code==200 and response.json['intake']['rejected']==5
    assert client.get('/api/runs').json=={'items':[]}


def test_upload_uses_input_content(client,clean):
    a=client.post('/api/runs',data={'file':(io.BytesIO(clean),'input.csv')})
    b=client.post('/api/runs',data={'sample':'clean'})
    assert a.status_code==200 and a.json['id']==b.json['id']


def test_unknown_stage_and_sample(client):
    assert client.post('/api/stages/unknown',data={'sample':'clean'}).status_code==404
    assert client.post('/api/runs',data={'sample':'unknown'}).status_code==404


def test_bad_upload_leaves_history_empty(client):
    result=client.post('/api/runs',data={'file':(io.BytesIO(b'wrong,header\n'),'bad.csv')})
    assert result.status_code==422 and result.json['code']=='HEADER_MISMATCH'
    assert client.get('/api/runs').json['items']==[]


def test_correction_ledger_on_workbench(client):
    from corrections_data import rewrite
    run=client.post('/api/runs',data={'sample':'clean'}).json
    assert run['ledger']['tickets'][0]['status']=='UNCHANGED'
    client.patch(f"/api/runs/{run['id']}",json=dict(revision=0,status='APPROVED',note='首次签发完成'))
    fixed=rewrite((ROOT/'sample_data'/'ready.csv').read_bytes(),{('0001','reject','31'):0})
    client.post(f"/api/runs/{run['id']}/corrections",data={'file':(io.BytesIO(fixed),'fix.csv')})
    batch=client.get(f"/api/runs/{run['id']}").json
    ticket=next(row for row in batch['ledger']['tickets'] if row['ticket']=='31')
    assert (ticket['paid_g'],ticket['pending_g'],ticket['status'])==(4500,0,'PAID')
    assert batch['ledger']['settled'] is True
