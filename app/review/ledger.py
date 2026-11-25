"""更正补差的纯计算部分。

签发批次确定了每张联单的应付金额。后续每次更正只改变该联单的最新应付，
但已经补出去的金额不能追回，因此每一笔新补差都是：

    本次补差 = 最新应付 - 原签发应付 - 已补合计

逐次累加后，已补合计恰好等于最新应付与原签发应付之差。若更正后批次
不合格，或最新应付低于已付金额（需要追回），差额停在待处理，不动原签发。

联单以「业务分组:票号」为键，避免不同分组复用票号时互相覆盖。
"""


def key(case, ticket):
    return f"{case}:{ticket}"


def loads(report):
    """逐联单产出 (键, 业务分组, 票号, 计算证据)。"""
    for case in report.get('cases') or []:
        measure = case.get('measure') or {}
        evidence = measure.get('evidence') or {}
        for ticket, load in sorted((evidence.get('loads') or {}).items()):
            yield key(case['case'], ticket), case['case'], str(ticket), load


def payable(report):
    """按联单取应付克数，未算出金额的分组不进入台账。"""
    return {item[0]: int(item[3]['payable_g']) for item in loads(report)}


def basis(report):
    """原签发依据：逐联单的重量与化验结论，按签发时保存的报告原样读取。"""
    return {
        item[0]: {
            'case': item[1],
            'ticket': item[2],
            'net_g': int(item[3]['net_g']),
            'dry_g': int(item[3]['dry_g']),
            'payable_g': int(item[3]['payable_g']),
            'reject_bp': int(item[3]['reject_bp']),
        }
        for item in loads(report)
    }


def verdict(report):
    """更正后整批是否仍可补差。

    杂质率超限优先于其他对账问题；缺少过磅、联单不符等使整批算不齐的
    情况也停在待处理。原签发时写下的参考金额不参与判断，因为更正的
    正是金额本身。
    """
    cases = report.get('cases') or []
    for case in cases:
        evidence = (case.get('measure') or {}).get('evidence') or {}
        if case.get('status') == 'CONTAMINATION_LIMIT' or evidence.get('over_limit'):
            return False, 'CONTAMINATION_LIMIT'
    balance = report.get('balance') or {}
    if not balance.get('balanced', False) or balance.get('isolated', 0):
        return False, 'UNBALANCED'
    broken = sorted({case['status'] for case in cases
                     if case.get('status') not in ('READY', 'MISMATCH')})
    if broken:
        return False, broken[0]
    return True, None


def plan(original, corrected, released, reason, paid_before):
    """逐联单算出本次补差。

    `corrected` 只包含本次来源里出现的联单，未出现的联单视为未更正。
    `paid_before` 是已经付出且不可追回的金额，按同一键累计。
    """
    specs = []
    for item in sorted(corrected, key=lambda name: tuple(name.split(':', 1))):
        case, ticket = item.split(':', 1)
        source = int(original.get(item, 0))
        latest = int(corrected[item])
        paid = int(paid_before.get(item, 0))
        due = latest - source - paid
        if due == 0:
            continue
        if not released:
            status, why = 'PENDING', reason
        elif due < 0:
            status, why = 'PENDING', 'RECOVERY_NOT_ALLOWED'
        else:
            status, why = 'PAID', None
        specs.append({
            'key': item,
            'case': case,
            'ticket': ticket,
            'original_g': source,
            'latest_g': latest,
            'paid_before_g': paid,
            'amount_g': due,
            'paid_after_g': paid + (due if status == 'PAID' else 0),
            'status': status,
            'reason': why,
        })
    return specs


def summarize(original, latest, supplements, basis_map=None, corrections=()):
    """工作台台账：原签发、已补、待处理和需追回逐联单汇总。"""
    basis_map = basis_map or {}
    tickets = {}

    def entry_for(item, original_g, latest_g, row=None):
        if item not in tickets:
            details = basis_map.get(item) or (row.get('basis') if row else None) or {}
            group, ticket = item.split(':', 1)
            tickets[item] = {
                'key': item,
                'case': details.get('case') or (row['group_code'] if row else group),
                'ticket': details.get('ticket') or (row['ticket'] if row else ticket),
                'original_g': int(original_g),
                'latest_g': int(latest_g),
                'paid_g': 0,
                'pending_g': 0,
                'recovery_g': 0,
                'reasons': [],
                'basis': details or None,
            }
        return tickets[item]

    for item, amount in original.items():
        entry_for(item, amount, latest.get(item, amount))
    for row in supplements:
        item = row.get('item') or key(row['group_code'], row['ticket'])
        entry = entry_for(item, row['original_g'], row['latest_g'], row)
        amount = int(row['amount_g'])
        if row['status'] == 'PAID':
            entry['paid_g'] += amount
        elif row['status'] == 'PENDING':
            if amount >= 0:
                entry['pending_g'] += amount
            else:
                entry['recovery_g'] += -amount
            if row.get('reason') and row['reason'] not in entry['reasons']:
                entry['reasons'].append(row['reason'])
    for item, entry in tickets.items():
        entry['latest_g'] = int(latest.get(item, entry['latest_g']))
        entry['gap_g'] = entry['latest_g'] - entry['original_g']
        if entry['pending_g'] or entry['recovery_g']:
            entry['status'] = 'PENDING'
        elif entry['paid_g']:
            entry['status'] = 'PAID'
        else:
            entry['status'] = 'UNCHANGED'
    ordered = sorted(tickets.values(), key=lambda item: (item['case'], item['ticket']))
    original_g = sum(item['original_g'] for item in ordered)
    latest_g = sum(item['latest_g'] for item in ordered)
    paid_g = sum(item['paid_g'] for item in ordered)
    pending_g = sum(item['pending_g'] for item in ordered)
    recovery_g = sum(item['recovery_g'] for item in ordered)
    return {
        'original_g': original_g,
        'latest_g': latest_g,
        'paid_g': paid_g,
        'pending_g': pending_g,
        'recovery_g': recovery_g,
        'gap_g': latest_g - original_g,
        'settled': not pending_g and not recovery_g and paid_g == latest_g - original_g,
        'tickets': ordered,
        'corrections': list(corrections),
    }
