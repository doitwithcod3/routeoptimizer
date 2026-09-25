from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from services.fuel_optimizer import MAX_RANGE_MILES, MPG, optimize_fuel_stops
from services.geometry_service import METRES_PER_MILE, find_stations_near_route
from services.location_service import LocationResolutionError, resolve_location
from services.routing_service import RoutingServiceError, get_route


@api_view(['POST'])
def route(request):
	start = request.data.get('start')
	finish = request.data.get('finish')
	if not isinstance(start, str) or not start.strip():
		return Response({'detail': 'start is required'}, status=status.HTTP_400_BAD_REQUEST)
	if not isinstance(finish, str) or not finish.strip():
		return Response({'detail': 'finish is required'}, status=status.HTTP_400_BAD_REQUEST)

	try:
		start_coordinates = resolve_location(start.strip())
		finish_coordinates = resolve_location(finish.strip())
	except LocationResolutionError as exc:
		return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

	cache_key = _route_cache_key(start_coordinates, finish_coordinates)
	cached_response = cache.get(cache_key)
	if cached_response is not None:
		return Response(cached_response)

	try:
		route_data = get_route(start_coordinates, finish_coordinates)
		route_coordinates = route_data['geometry']['coordinates']
		candidates = find_stations_near_route(route_coordinates)
		route_distance_miles = route_data['distance'] / METRES_PER_MILE
		optimization = optimize_fuel_stops(
			candidates,
			route_distance_miles,
		)
	except RoutingServiceError as exc:
		return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
	except ValueError as exc:
		return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

	response_data = {
		'start': {
			'address': start.strip(),
			'latitude': start_coordinates[0],
			'longitude': start_coordinates[1],
		},
		'finish': {
			'address': finish.strip(),
			'latitude': finish_coordinates[0],
			'longitude': finish_coordinates[1],
		},
		'route': {
			'distance miles': round(route_distance_miles, 1),
			'duration minutes': round(route_data['duration'] / 60),
			'geometry': route_data['geometry'],
		},
		'vehicle': {
			'max range miles': MAX_RANGE_MILES,
			'miles_per_gallon': MPG,
		},
		'fuel': {
			'total gallons': round(route_distance_miles / MPG, 2),
			'total_cost': float(optimization['total_fuel_cost']),
		},
		'fuel_stops': [
			_serialize_stop(stop, candidates)
			for stop in optimization['recommended_stops']
		],
	}
	cache.set(cache_key, response_data, timeout=3600)
	return Response(response_data)


def _route_cache_key(start, finish):
	coordinates = (*start, *finish)
	return 'route:v2:' + ':'.join(f'{coordinate:.6f}' for coordinate in coordinates)


def _serialize_stop(stop, candidates):
	station = stop['station']
	candidate = next(
		candidate for candidate in candidates
		if candidate['station'].id == station.id
	)
	return {
		'truckstop_id': station.opis_id,
		'name': station.name,
		'address': station.address,
		'city': station.city,
		'state': station.state,
		'retail_price': float(station.retail_price),
		'route_position_miles': round(stop['route_position_miles'], 1),
		'distance_from_route miles': round(
			candidate['distance_from_route_miles'], 1
		),
		'gallons_purchased': float(stop['gallons_purchased']),
		'cost': float(stop['cost']),
	}
