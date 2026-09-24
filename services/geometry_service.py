import math
from typing import Iterable

from django.db.models import QuerySet
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform

from routing.models import FuelStation


METRES_PER_MILE = 1609.344


def coordinates_to_linestring(
    route_coordinates: Iterable[tuple[float, float]],
) -> LineString:
    """Convert GeoJSON ``[longitude, latitude]`` coordinates to a LineString."""
    coordinates = [
        (float(longitude), float(latitude))
        for longitude, latitude in route_coordinates
    ]
    if not coordinates:
        raise ValueError('A route must contain at least one coordinate')
    if any(
        not (-180 <= longitude <= 180 and -90 <= latitude <= 90)
        for longitude, latitude in coordinates
    ):
        raise ValueError('Route coordinates must be valid longitude/latitude pairs')
    if len(coordinates) == 1:
        coordinates.append(coordinates[0])
    return LineString(coordinates)


def find_stations_near_route(
    route_coordinates: Iterable[tuple[float, float]],
    corridor_miles: float = 5.0,
    stations: QuerySet | Iterable[FuelStation] | None = None,
) -> list[dict[str, object]]:
    """Find stations within a route corridor and locate them along the route.

    ``route_coordinates`` must be GeoJSON ``[longitude, latitude]`` pairs.
    Each result contains the station, its distance along the route in miles,
    and its perpendicular distance from the route in miles.
    """
    if not math.isfinite(corridor_miles) or corridor_miles < 0:
        raise ValueError('corridor_miles must be a non-negative finite number')

    route = coordinates_to_linestring(route_coordinates)
    transformer = _route_transformer(route)
    projected_route = transform(transformer.transform, route)
    corridor_metres = corridor_miles * METRES_PER_MILE
    station_queryset = FuelStation.objects.all() if stations is None else stations

    nearby_stations = []
    for station in station_queryset:
        point = Point(float(station.longitude), float(station.latitude))
        projected_point = transform(transformer.transform, point)
        route_distance_metres = projected_route.distance(projected_point)
        if route_distance_metres <= corridor_metres:
            nearby_stations.append(
                {
                    'station': station,
                    'position_miles': projected_route.project(projected_point)
                    / METRES_PER_MILE,
                    'distance_from_route_miles': route_distance_metres
                    / METRES_PER_MILE,
                }
            )

    return sorted(nearby_stations, key=lambda candidate: candidate['position_miles'])


def _route_transformer(route: LineString) -> Transformer:
    """Create a metric WGS84-to-local-UTM transformer for the route."""
    longitude, latitude = route.centroid.coords[0]
    zone = min(60, max(1, math.floor((longitude + 180) / 6) + 1))
    epsg = (32600 if latitude >= 0 else 32700) + zone
    return Transformer.from_crs('EPSG:4326', f'EPSG:{epsg}', always_xy=True)