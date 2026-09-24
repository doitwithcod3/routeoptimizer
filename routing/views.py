from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from services.fuel_optimizer import optimize_fuel_stops
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
		optimization = optimize_fuel_stops(
			candidates,
			route_data['distance'] / METRES_PER_MILE,
		)
	except RoutingServiceError as exc:
		return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
	except ValueError as exc:
		return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

	response_data = {
		'geometry': route_data['geometry'],
		'total_fuel_cost': float(optimization['total_fuel_cost']),
		'fuel_stops': [_serialize_stop(stop) for stop in optimization['recommended_stops']],
	}
	cache.set(cache_key, response_data, timeout=3600)
	return Response(response_data)


def _route_cache_key(start, finish):
	coordinates = (*start, *finish)
	return 'route:v1:' + ':'.join(f'{coordinate:.6f}' for coordinate in coordinates)


def _serialize_stop(stop):
	station = stop['station']
	return {
		'station': {
			'id': station.id,
			'opis_id': station.opis_id,
			'name': station.name,
			'address': station.address,
			'city': station.city,
			'state': station.state,
			'rack_id': station.rack_id,
			'retail_price': float(station.retail_price),
		},
		'position_miles': stop['position_miles'],
		'gallons_purchased': float(stop['gallons_purchased']),
		'price_per_gallon': float(stop['price_per_gallon']),
		'cost': float(stop['cost']),
	}
