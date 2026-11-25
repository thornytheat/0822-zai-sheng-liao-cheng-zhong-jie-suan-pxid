from app.business import measured


def compute(data):
    tickets, statement = data
    loads = {}
    high_reject = []
    for ticket,bundle in sorted(tickets.items()):
        net = bundle['gross']['grams'] - bundle['tare']['grams']
        water = bundle['moisture']['basis_points']
        rejected = bundle.get('reject',{}).get('basis_points',0)
        payable = net*(10_000-water)*(10_000-rejected)//100_000_000
        loads[str(ticket)] = {'net_g':net,'dry_g':net*(10_000-water)//10_000,'payable_g':payable,'reject_bp':rejected}
        if rejected > 2000:
            high_reject.append(ticket)
    return measured(sum(row['payable_g'] for row in loads.values()),statement,'克',{'loads':loads,'over_limit':high_reject},bool(high_reject))
