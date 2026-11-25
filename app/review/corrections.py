from datetime import datetime, timezone
from hashlib import sha256
from time import monotonic

from app.business import DomainIssue
from app.config import RULE_VERSION
from app.modules.pipeline import run
from app.review import ledger
from app.review.ledger import payable, verdict


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def submit(store, run_id, data, reference=None):
    """对已签发批次提交一次更正。

    - 只接受已签发批次；
    - 原金额和依据一律从签发时保存的报告读回，绝不改写；
    - 更正来源只能涉及原签发已算出的联单；
    - 以更正来源的摘要作为幂等键，同一份更正重试只返回既有补差；
      内容确有变化才算新的一次更正，按差额继续补。
    """
    start = monotonic()
    current = store.load(run_id)
    if current['status'] != 'APPROVED':
        raise DomainIssue('RUN_NOT_APPROVED')
    if reference is not None and (not isinstance(reference, str) or len(reference.strip()) > 200):
        raise DomainIssue('CORRECTION_FIELDS')
    report = run(data)
    original = payable(current['report'])
    corrected = payable(report)
    if set(corrected) != set(original):
        raise DomainIssue('CORRECTION_SCOPE')
    released, reason = verdict(report)
    fingerprint = sha256(data).hexdigest()
    token = fingerprint
    correction_id = sha256(f'{run_id}:{token}:{RULE_VERSION}'.encode()).hexdigest()
    report['manifest'] = dict(sha256=fingerprint, version=RULE_VERSION, created=now(),
                              duration_ms=round((monotonic()-start)*1000,3), bytes=len(data),
                              correction_of=run_id)
    meta = {
        'id': correction_id,
        'token': token,
        'reference': reference.strip() if isinstance(reference, str) and reference.strip() else None,
        'source_sha256': fingerprint,
        'source_bytes': len(data),
        'report': report,
        'original': original,
        'latest': corrected,
        'created': report['manifest']['created'],
    }

    def decide(paid):
        specs = ledger.plan(original, corrected, released, reason, paid)
        if not released:
            status = 'PENDING'
        elif any(spec['status'] == 'PENDING' for spec in specs):
            status = 'PENDING'
        elif specs:
            status = 'PAID'
        else:
            status = 'NO_CHANGE'
        if not released:
            why = reason
        elif status == 'PENDING':
            why = 'RECOVERY_NOT_ALLOWED'
        else:
            why = None
        return specs, status, why

    return store.record(run_id, token, meta, decide)
