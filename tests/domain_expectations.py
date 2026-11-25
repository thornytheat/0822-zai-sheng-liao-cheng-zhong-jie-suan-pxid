EXPECTED = {'0001': (1, 85500, 'READY'),
 '0002': (1, 875, 'READY'),
 '0003': (0, None, 'TICKET_MISMATCH'),
 '0004': (1, 31500, 'CONTAMINATION_LIMIT')}
EVIDENCE = {'0001': {'loads': {'31': {'net_g': 100000,
                           'dry_g': 90000,
                           'payable_g': 85500,
                           'reject_bp': 500}},
          'over_limit': []},
 '0002': {'loads': {'32': {'net_g': 1001,
                           'dry_g': 875,
                           'payable_g': 875,
                           'reject_bp': 0}},
          'over_limit': []}}
