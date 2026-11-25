import json


def artifact(run, ledger=None):
    packet = {
        'schema': 'review-evidence/1',
        'manifest': run['report']['manifest'],
        'balance': run['report']['balance'],
        'cases': run['report']['cases'],
        'intake': run['report']['intake'],
        'review': {key:run[key] for key in ('status','revision','note','reviewed')},
    }
    if ledger is not None:
        packet['ledger'] = ledger
    return (json.dumps(packet, ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
