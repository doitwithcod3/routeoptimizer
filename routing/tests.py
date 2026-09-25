from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from rest_framework.test import APITestCase


class RouteResponseTests(APITestCase):
	@patch('routing.views.cache.set')
	@patch('routing.views.cache.get', return_value=None)
	@patch('routing.views.optimize_fuel_stops')
	@patch('routing.views.find_stations_near_route')
	@patch('routing.views.get_route')
	@patch('routing.views.resolve_location')
	def test_returns_nested_route_and_fuel_response(
		self,
		resolve_location,
		get_route,
		find_stations,
		optimize,
		cache_get,
		cache_set,
	):
		resolve_location.side_effect = [(40.7128, -74.006), (41.8781, -87.6298)]
		geometry = {'type': 'LineString', 'coordinates': [[-74.006, 40.7128]]}
		get_route.return_value = {
			'distance': 790.4 * 1609.344,
			'duration': 745 * 60,
			'geometry': geometry,
		}
		station = SimpleNamespace(
			id=1,
			opis_id=12345,
			name='Example Truckstop',
			address='123 Example Road',
			city='Example City',
			state='IL',
			retail_price=Decimal('3.190'),
		)
		candidates = [{
			'station': station,
			'route_position_miles': 320.4,
			'distance_from_route_miles': 1.2,
		}]
		find_stations.return_value = candidates
		optimize.return_value = {
			'total_fuel_cost': Decimal('65.400'),
			'recommended_stops': [{
				'station': station,
				'route_position_miles': 320.4,
				'gallons_purchased': Decimal('20.5'),
				'cost': Decimal('65.400'),
			}],
		}

		response = self.client.post(
			'/api/v1/route/',
			{'start': 'New York, NY', 'finish': 'Chicago, IL'},
			format='json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data, {
			'start': {
				'address': 'New York, NY',
				'latitude': 40.7128,
				'longitude': -74.006,
			},
			'finish': {
				'address': 'Chicago, IL',
				'latitude': 41.8781,
				'longitude': -87.6298,
			},
			'route': {
				'distance miles': 790.4,
				'duration minutes': 745,
				'geometry': geometry,
			},
			'vehicle': {'max range miles': 500, 'miles_per_gallon': 10},
			'fuel': {'total gallons': 79.04, 'total_cost': 65.4},
			'fuel_stops': [{
				'truckstop_id': 12345,
				'name': 'Example Truckstop',
				'address': '123 Example Road',
				'city': 'Example City',
				'state': 'IL',
				'retail_price': 3.19,
				'route_position_miles': 320.4,
				'distance_from_route miles': 1.2,
				'gallons_purchased': 20.5,
				'cost': 65.4,
			}],
		})
