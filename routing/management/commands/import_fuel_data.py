import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from routing.models import FuelStation


REQUIRED_COLUMNS = {
    'OPIS Truckstop ID',
    'Truckstop Name',
    'Address',
    'City',
    'State',
    'Rack ID',
    'Retail Price',
}


def normalize_address(address, city, state):
    return f'{address.strip()}, {city.strip()}, {state.strip()}, USA'.lower()


def mock_geocode(address):
    """Return placeholder coordinates until a real geocoding service is added."""
    return Decimal('0.000000'), Decimal('0.000000')


class Command(BaseCommand):
    help = 'Import fuel station data from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            nargs='?',
            default='resources/fuel_prices.csv',
            help='Path to the CSV file (default: resources/fuel_prices.csv).',
        )

    def handle(self, *args, **options):
        csv_path = Path(options['csv_file'])
        if not csv_path.is_absolute():
            csv_path = settings.BASE_DIR / csv_path

        if not csv_path.is_file():
            raise CommandError(f'CSV file not found: {csv_path}')

        geocoded_addresses = {}
        created_count = 0
        updated_count = 0

        with csv_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
            reader = csv.DictReader(csv_file)
            reader.fieldnames = [header.strip() for header in (reader.fieldnames or [])]
            headers = set(reader.fieldnames)
            missing_columns = REQUIRED_COLUMNS - headers
            if missing_columns:
                missing = ', '.join(sorted(missing_columns))
                raise CommandError(f'Missing required CSV columns: {missing}')

            for row_number, row in enumerate(reader, start=2):
                try:
                    opis_id = int(row['OPIS Truckstop ID'].strip())
                    name = row['Truckstop Name'].strip()
                    address = row['Address'].strip()
                    city = row['City'].strip()
                    state = row['State'].strip()
                    rack_id = row['Rack ID'].strip() or None
                    retail_price = self.parse_price(row['Retail Price'])
                except (AttributeError, InvalidOperation, TypeError, ValueError, KeyError) as exc:
                    raise CommandError(f'Invalid data on CSV row {row_number}: {exc}') from exc

                if not all((name, address, city, state)):
                    raise CommandError(f'Missing station data on CSV row {row_number}')

                normalized_address = normalize_address(address, city, state)
                if normalized_address not in geocoded_addresses:
                    geocoded_addresses[normalized_address] = mock_geocode(normalized_address)
                latitude, longitude = geocoded_addresses[normalized_address]

                station = FuelStation(
                    opis_id=opis_id,
                    name=name,
                    address=address,
                    city=city,
                    state=state,
                    rack_id=rack_id,
                    retail_price=retail_price,
                    latitude=latitude,
                    longitude=longitude,
                )
                try:
                    station.full_clean(validate_unique=False)
                except ValidationError as exc:
                    raise CommandError(f'Invalid station on CSV row {row_number}: {exc}') from exc

                _, created = FuelStation.objects.update_or_create(
                    opis_id=opis_id,
                    defaults={
                        'name': name,
                        'address': address,
                        'city': city,
                        'state': state,
                        'rack_id': rack_id,
                        'retail_price': retail_price,
                        'latitude': latitude,
                        'longitude': longitude,
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Imported {created_count + updated_count} rows: '
                f'{created_count} created, {updated_count} updated, '
                f'{len(geocoded_addresses)} unique addresses geocoded.'
            )
        )

    @staticmethod
    def parse_price(value):
        return Decimal(value.strip()).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)