from app.business import DomainIssue, prepared, single


def prepare(rows):
    statement = single(rows,'statement')['grams']
    tickets = {}
    for row in rows:
        if row['kind'] == 'statement':
            continue
        bundle = tickets.setdefault(row['ticket'],{})
        if row['kind'] in bundle:
            raise DomainIssue('DUPLICATE_WEIGHING')
        bundle[row['kind']] = row
    if not tickets:
        raise DomainIssue('WEIGHING_MISSING')
    for bundle in tickets.values():
        gross, tare = bundle.get('gross'), bundle.get('tare')
        if not gross or not tare or any(r['vehicle'] != gross['vehicle'] for r in bundle.values()):
            raise DomainIssue('TICKET_MISMATCH')
        if not 0 < tare['minute']-gross['minute'] <= 120 or tare['grams'] >= gross['grams']:
            raise DomainIssue('TARE_OUT_OF_RANGE')
        if any(not tare['minute'] <= r['minute'] <= tare['minute']+60 or r['basis_points'] > 10_000 for k,r in bundle.items() if k in {'moisture','reject'}):
            raise DomainIssue('INVALID_LAB_READING')
        if 'moisture' not in bundle:
            raise DomainIssue('MOISTURE_MISSING')
    return prepared(len(tickets),{'tickets':len(tickets),'statement_g':statement},(tickets,statement))
