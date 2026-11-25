from app.business import decision


def policy(result):
    return decision(result,'CONTAMINATION_LIMIT' if result['flag'] else None)
