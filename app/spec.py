COLUMNS = ('ticket', 'vehicle', 'minute', 'grams', 'basis_points')
KINDS = ('gross', 'tare', 'moisture', 'reject', 'statement')
PROJECT = {'name': '再生料称重结算', 'actor': '回收站结算员', 'stages': [('intake', '样例采信'), ('prepare', '过磅联单'), ('calculate', '净干重核算'), ('policy', '结算复核'), ('balance', '运行对账')], 'chart': '联单重量', 'mark': '再'}
