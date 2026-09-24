from rest_framework import serializers

from .models import FuelStation


class FuelStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelStation
        fields = [
            'id',
            'opis_id',
            'name',
            'address',
            'city',
            'state',
            'rack_id',
            'retail_price',
            'latitude',
            'longitude',
        ]