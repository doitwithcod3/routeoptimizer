from django.db import models


class FuelStation(models.Model):
	opis_id = models.BigIntegerField(unique=True)
	name = models.CharField(max_length=255)
	address = models.CharField(max_length=255)
	city = models.CharField(max_length=100)
	state = models.CharField(max_length=50)
	rack_id = models.CharField(max_length=50, blank=True, null=True)
	retail_price = models.DecimalField(max_digits=6, decimal_places=3)
	latitude = models.DecimalField(max_digits=9, decimal_places=6)
	longitude = models.DecimalField(max_digits=9, decimal_places=6)

	def __str__(self):
		return self.name
