from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable


MAX_RANGE_MILES = 500
MPG = 10
MAX_TANK_GALLONS = 50
INITIAL_TANK_GALLONS = 50

_GALLON_QUANTUM = Decimal('0.001')
_MILES_PER_GALLON = Decimal(MPG)
_MAX_TANK = Decimal(MAX_TANK_GALLONS)


def optimize_fuel_stops(
    stations: Iterable[dict[str, Any]],
    route_distance_miles: float,
) -> dict[str, Any]:
    """Calculate greedy fuel purchases for a route.

    ``stations`` should contain the dictionaries returned by
    ``find_stations_near_route``. Stations are ordered by their 1D route
    position, and prices are read from each station's ``retail_price`` field.
    """
    if route_distance_miles < 0:
        raise ValueError('route_distance_miles must be non-negative')

    candidates = sorted(
        (_station_details(candidate) for candidate in stations),
        key=lambda candidate: candidate['position_miles'],
    )
    _validate_stations(candidates, route_distance_miles)

    fuel = Decimal(INITIAL_TANK_GALLONS)
    current_position = Decimal('0')
    total_cost = Decimal('0')
    recommended_stops = []

    for index, candidate in enumerate(candidates):
        position = candidate['position_miles']
        fuel -= (position - current_position) / _MILES_PER_GALLON
        current_position = position

        next_cheaper = _next_cheaper_reachable(candidates, index)
        if next_cheaper is not None:
            target_position = next_cheaper['position_miles']
            gallons_to_buy = max(
                Decimal('0'),
                (target_position - position) / _MILES_PER_GALLON - fuel,
            )
        else:
            gallons_to_buy = max(
                Decimal('0'),
                (Decimal(str(route_distance_miles)) - position)
                / _MILES_PER_GALLON
                - fuel,
            )

        gallons_to_buy = min(gallons_to_buy, _MAX_TANK - fuel)
        gallons_to_buy = gallons_to_buy.quantize(
            _GALLON_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        if gallons_to_buy <= 0:
            continue

        price = candidate['price']
        stop_cost = (gallons_to_buy * price).quantize(
            _GALLON_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        fuel += gallons_to_buy
        total_cost += stop_cost
        recommended_stops.append(
            {
                'station': candidate['station'],
                'position_miles': float(position),
                'gallons_purchased': gallons_to_buy,
                'price_per_gallon': price,
                'cost': stop_cost,
            }
        )

    return {
        'recommended_stops': recommended_stops,
        'total_fuel_cost': total_cost.quantize(
            _GALLON_QUANTUM,
            rounding=ROUND_HALF_UP,
        ),
    }


def _station_details(candidate: dict[str, Any]) -> dict[str, Any]:
    station = candidate['station']
    return {
        'station': station,
        'position_miles': Decimal(str(candidate['position_miles'])),
        'price': Decimal(str(station.retail_price)),
    }


def _next_cheaper_reachable(candidates, current_index):
    current = candidates[current_index]
    for candidate in candidates[current_index + 1:]:
        distance = candidate['position_miles'] - current['position_miles']
        if distance > MAX_RANGE_MILES:
            break
        if candidate['price'] < current['price']:
            return candidate
    return None


def _validate_stations(candidates, route_distance_miles):
    previous_position = Decimal('0')
    for candidate in candidates:
        position = candidate['position_miles']
        if position < 0 or position > Decimal(str(route_distance_miles)):
            raise ValueError('Station positions must fall within the route')
        if position < previous_position:
            raise ValueError('Station positions must be ordered along the route')
        if position - previous_position > MAX_RANGE_MILES:
            raise ValueError('A route segment exceeds the vehicle maximum range')
        previous_position = position

    if Decimal(str(route_distance_miles)) - previous_position > MAX_RANGE_MILES:
        raise ValueError('The final route segment exceeds the vehicle maximum range')