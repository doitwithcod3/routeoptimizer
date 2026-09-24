import os
from typing import Any

import httpx

from routing.models import FuelStation


ORS_GEOCODE_URL = 'https://api.openrouteservice.org/geocode/search'


class LocationResolutionError(Exception):
    """Raised when a location cannot be resolved to coordinates."""


def resolve_location(location: str) -> tuple[float, float]:
    """Resolve an address from the imported fuel-station data."""
    station, canonical_address = _find_station_address(location)
    if station is None:
        raise LocationResolutionError(
            'Location must match an address from the imported fuel data'
        )

    if station.latitude != 0 or station.longitude != 0:
        return float(station.latitude), float(station.longitude)

    api_key = os.getenv('ORS_API_KEY')
    if not api_key:
        raise LocationResolutionError(
            'ORS_API_KEY is required to resolve non-coordinate locations'
        )

    try:
        response = httpx.get(
            ORS_GEOCODE_URL,
            params={'api_key': api_key, 'text': canonical_address, 'size': 1},
            timeout=10.0,
        )
    except httpx.TimeoutException as exc:
        raise LocationResolutionError('Location resolution timed out') from exc
    except httpx.RequestError as exc:
        raise LocationResolutionError('Location resolution request failed') from exc

    if response.status_code == 429:
        raise LocationResolutionError('Location resolution rate limit exceeded')
    if response.is_error:
        raise LocationResolutionError(
            f'Location resolution failed ({response.status_code}): '
            f'{_response_error(response)}'
        )

    try:
        longitude, latitude = response.json()['features'][0]['geometry']['coordinates']
        return float(latitude), float(longitude)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise LocationResolutionError(f'Location not found: {canonical_address}') from exc


def _find_station_address(location: str):
    normalized_location = _normalize_address(location)
    for station in FuelStation.objects.all():
        canonical_address = (
            f'{station.address}, {station.city}, {station.state}, USA'
        )
        accepted_forms = {
            _normalize_address(station.address),
            _normalize_address(canonical_address),
            _normalize_address(
                f'{station.address}, {station.city}, {station.state}'
            ),
        }
        if normalized_location in accepted_forms:
            return station, canonical_address
    return None, None


def _normalize_address(address: str) -> str:
    return ' '.join(address.strip().lower().split())


def _response_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get('error')
            if isinstance(error, dict):
                return str(error.get('message') or error.get('description') or error)
            if error:
                return str(error)
            if payload.get('message'):
                return str(payload['message'])
    except (ValueError, TypeError):
        pass
    return response.text[:300] or 'No error details returned'