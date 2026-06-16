from economy.supply.total import get_total_supply
from economy.reserve.reserve import get_total_reserve


def get_circulating():
    total = get_total_supply()
    reserve = get_total_reserve()

    return {
        "circulating": total,
        "reserve": reserve,
        "system_total": total + reserve
    }