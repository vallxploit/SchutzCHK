from database.connection import execute


def get_history(user_id: int, limit: int = 20):
    result = execute(
        """
        SELECT *
        FROM ledger
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        [user_id, limit]
    )

    return [
        {
            "type": row[1],
            "amount": row[2],
            "before": row[3],
            "after": row[4],
            "desc": row[5],
            "time": row[6]
        }
        for row in result.rows
    ]