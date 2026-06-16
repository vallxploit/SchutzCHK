from database.connection import execute


def get_total_supply():
    result = execute(
        "SELECT SUM(balance) FROM balances"
    )

    if not result.rows:
        return 0

    return result.rows[0][0] or 0