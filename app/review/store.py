import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue
from app.review.ledger import basis as basis_of
from app.review.ledger import payable, summarize

SCHEMA = '''CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', reviewed TEXT
);'''

LEDGER = '''
CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, token TEXT NOT NULL, reference TEXT,
    source_sha256 TEXT NOT NULL, source_bytes INTEGER NOT NULL, report TEXT NOT NULL,
    status TEXT NOT NULL, reason TEXT, created TEXT NOT NULL,
    UNIQUE(run_id, token)
);
CREATE TABLE IF NOT EXISTS supplements (
    id TEXT PRIMARY KEY, correction_id TEXT NOT NULL, run_id TEXT NOT NULL,
    item TEXT NOT NULL, group_code TEXT NOT NULL, ticket TEXT NOT NULL,
    original_g INTEGER NOT NULL, latest_g INTEGER NOT NULL, paid_before_g INTEGER NOT NULL,
    amount_g INTEGER NOT NULL, paid_after_g INTEGER NOT NULL, status TEXT NOT NULL,
    reason TEXT, created TEXT NOT NULL,
    UNIQUE(correction_id, item)
);
CREATE TABLE IF NOT EXISTS ticket_state (
    run_id TEXT NOT NULL, item TEXT NOT NULL, group_code TEXT NOT NULL, ticket TEXT NOT NULL,
    original_g INTEGER NOT NULL, latest_g INTEGER NOT NULL,
    PRIMARY KEY(run_id, item)
);
CREATE INDEX IF NOT EXISTS corrections_run ON corrections(run_id, created);
CREATE INDEX IF NOT EXISTS supplements_run ON supplements(run_id, item);
CREATE INDEX IF NOT EXISTS supplements_correction ON supplements(correction_id, item);
'''


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute(SCHEMA)
            db.executescript(LEDGER)
            yield db

    def register(self, run_id, report):
        with self.connect() as db:
            db.execute('INSERT INTO runs(id,report,created) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING',
                       (run_id,json.dumps(report,ensure_ascii=False),report['manifest']['created']))
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
        if row is None:
            raise DomainIssue('RUN_NOT_FOUND')
        result = dict(row)
        result['report'] = json.loads(result['report'])
        return result

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,created,status,revision,note FROM runs ORDER BY created DESC,id LIMIT 50')]

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute('UPDATE runs SET status=?,note=?,reviewed=?,revision=revision+1 WHERE id=? AND revision=?',
                                (status,note,now,run_id,revision))
            if cursor.rowcount != 1:
                raise DomainIssue('STALE_REVIEW')
        return self.load(run_id)

    # -- 更正补差 ---------------------------------------------------------

    def ledger(self, run_id):
        with self.connect() as db:
            return self._ledger(db, run_id)

    def corrections(self, run_id):
        with self.connect() as db:
            self._run_report(db, run_id)
            return [self._summary(row) for row in db.execute(
                'SELECT * FROM corrections WHERE run_id=? ORDER BY created,rowid',(run_id,))]

    def correction(self, run_id, correction_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM corrections WHERE run_id=? AND id=?',(run_id,correction_id)).fetchone()
            if row is None:
                raise DomainIssue('CORRECTION_NOT_FOUND')
            return self._assemble(db, row)

    def record(self, run_id, token, meta, decide):
        """在写锁内读取已付金额、生成补差并落库；同一 token 只产生一份更正。

        token 取更正来源的摘要，因此同一份更正重试直接返回既有结果。
        """
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM corrections WHERE run_id=? AND token=?',
                                  (run_id,token)).fetchone()
            if existing is not None:
                return self._assemble(db, existing)
            paid = {str(row['item']): int(row['amount'] or 0) for row in db.execute(
                "SELECT item, SUM(amount_g) AS amount FROM supplements "
                "WHERE run_id=? AND status='PAID' GROUP BY item",(run_id,))}
            specs, status, reason = decide(paid)
            db.execute('INSERT INTO corrections(id,run_id,token,reference,source_sha256,source_bytes,'
                       'report,status,reason,created) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (meta['id'],run_id,token,meta.get('reference'),meta['source_sha256'],
                        meta['source_bytes'],json.dumps(meta['report'],ensure_ascii=False),
                        status,reason,meta['created']))
            for item in meta['latest']:
                db.execute("UPDATE supplements SET status='SUPERSEDED' "
                           "WHERE run_id=? AND item=? AND status='PENDING'",(run_id,item))
            for spec in specs:
                db.execute('INSERT INTO supplements(id,correction_id,run_id,item,group_code,ticket,original_g,'
                           'latest_g,paid_before_g,amount_g,paid_after_g,status,reason,created) '
                           'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (f"{meta['id']}:{spec['key']}",meta['id'],run_id,spec['key'],spec['case'],
                            spec['ticket'],spec['original_g'],spec['latest_g'],spec['paid_before_g'],
                            spec['amount_g'],spec['paid_after_g'],spec['status'],spec['reason'],
                            meta['created']))
            for item, latest in meta['latest'].items():
                case, ticket = item.split(':', 1)
                db.execute('INSERT INTO ticket_state(run_id,item,group_code,ticket,original_g,latest_g) '
                           'VALUES (?,?,?,?,?,?) ON CONFLICT(run_id,item) DO UPDATE SET latest_g=excluded.latest_g',
                           (run_id,item,case,ticket,meta['original'].get(item,0),latest))
            row = db.execute('SELECT * FROM corrections WHERE id=?',(meta['id'],)).fetchone()
            return self._assemble(db, row)

    def _run_report(self, db, run_id):
        row = db.execute('SELECT report FROM runs WHERE id=?',(run_id,)).fetchone()
        if row is None:
            raise DomainIssue('RUN_NOT_FOUND')
        return json.loads(row['report'])

    @staticmethod
    def _summary(row):
        return {'id':row['id'],'run_id':row['run_id'],'reference':row['reference'],
                'created':row['created'],'status':row['status'],'reason':row['reason'],
                'source':{'sha256':row['source_sha256'],'bytes':row['source_bytes']}}

    def _assemble(self, db, row):
        report = json.loads(row['report'])
        corrected = payable(report)
        original_report = self._run_report(db, row['run_id'])
        original = payable(original_report)
        basis = basis_of(original_report)
        supplements = [dict(item) for item in db.execute(
            'SELECT * FROM supplements WHERE correction_id=? ORDER BY item,rowid',(row['id'],))]
        payload = self._summary(row)
        payload.update({
            'corrected': {item: amount for item, amount in sorted(corrected.items())},
            'original': {item: {'payable_g': amount, 'basis': basis.get(item)}
                         for item, amount in sorted(original.items())},
            'supplements': supplements,
        })
        return payload

    def _ledger(self, db, run_id):
        report = self._run_report(db, run_id)
        original = payable(report)
        basis = basis_of(report)
        latest = dict(original)
        latest.update({item['item']: int(item['latest_g']) for item in db.execute(
            'SELECT item,latest_g FROM ticket_state WHERE run_id=?',(run_id,))})
        supplements = [dict(row) for row in db.execute(
            'SELECT * FROM supplements WHERE run_id=? ORDER BY created,rowid',(run_id,))]
        corrections = [self._summary(row) for row in db.execute(
            'SELECT * FROM corrections WHERE run_id=? ORDER BY created,rowid',(run_id,))]
        return summarize(original, latest, supplements, basis, corrections)
