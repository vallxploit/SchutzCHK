from database.connection import execute


def search_ledger(user_id: int = None, tx_type: str = None):

    query = "SELECT * FROM ledger WHERE 1=1"
    params = []

    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    if tx_type:
        query += " AND type = ?"
        params.append(tx_type)

    query += " ORDER BY timestamp DESC"

    result = execute(query, params)

    return [
        {
            "user": row[0],
            "type": row[1],
            "amount": row[2],
            "before": row[3],
            "after": row[4],
            "desc": row[5],
            "time": row[6]
        }
        for row in result.rows
    ]