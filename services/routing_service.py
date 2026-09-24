import os
from typing import Any

import httpx


ORS_DIRECTIONS_URL = (
    'https://api.openrouteservice.org/v2/directions/driving-car/geojson'
)


class RoutingServiceError(Exception):
    """Base exception for OpenRouteService routing failures."""


class InvalidLocationError(RoutingServiceError):
    """Raised when OpenRouteService cannot route the requested locations."""


class RoutingTimeoutError(RoutingServiceError):
    """Raised when OpenRouteService does not respond before the timeout."""


class RoutingRateLimitError(RoutingServiceError):
    """Raised when the OpenRouteService API rate limit is exceeded."""


def get_route(
    start: tuple[float, float],
    finish: tuple[float, float],
) -> dict[str, Any]:
    """Return route data for start and finish coordinates.

    Coordinates are supplied as ``(latitude, longitude)`` pairs. The returned
    distance is in metres, duration is in seconds, and geometry is GeoJSON.
    """
    api_key = os.getenv('ORS_API_KEY')
    if not api_key:
        raise RoutingServiceError('ORS_API_KEY environment variable is not set')

    coordinates = [_to_ors_coordinate(start), _to_ors_coordinate(finish)]
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}

    try:
        response = httpx.post(
            ORS_DIRECTIONS_URL,
            headers=headers,
            json={'coordinates': coordinates},
            timeout=10.0,
        )
    except httpx.TimeoutException as exc:
        raise RoutingTimeoutError('OpenRouteService request timed out') from exc
    except httpx.RequestError as exc:
        raise RoutingServiceError('OpenRouteService request failed') from exc

    if response.status_code == 400:
        raise InvalidLocationError(_error_message(response, 'Invalid route locations'))
    if response.status_code == 429:
        raise RoutingRateLimitError('OpenRouteService rate limit exceeded')
    if response.is_error:
        raise RoutingServiceError(_error_message(response, 'OpenRouteService error'))

    try:
        feature = response.json()['features'][0]
        summary = feature['properties']['summary']
        geometry = feature['geometry']
        return {
            'distance': summary['distance'],
            'duration': summary['duration'],
            'geometry': geometry,
        }
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RoutingServiceError('OpenRouteService returned an invalid route response') from exc


def _to_ors_coordinate(coordinate: tuple[float, float]) -> list[float]:
    try:
        latitude, longitude = coordinate
        return [float(longitude), float(latitude)]
    except (TypeError, ValueError) as exc:
        raise InvalidLocationError(
            'Coordinates must be (latitude, longitude) pairs'
        ) from exc


def _error_message(response: httpx.Response, fallback: str) -> str:
    try:
        details = response.json().get('error', {}).get('message')
    except (ValueError, TypeError):
        details = None
    return details or fallback