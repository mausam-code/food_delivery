from django.db import models
from django.conf import settings


# Create your models here.
class Restaurant(models.Model):

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_restaurants",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )


    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(
                fields = ["is_active","name"],
                name = "restaurant_active_name_idx",
            ),
        ]

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="menu_items",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10,decimal_places=2,)
    is_available = models.BooleanField(default = True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="menu_item_price_nonnegative",
            ),            
        ]
        indexes = [
            models.Index(
                fields=["restaurant","is_available"],
                name="menu_restaurant_available_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.restaurant.name}"