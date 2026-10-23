
from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id", "item_name", "unit_price",
            "quantity", "line_total",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(
        source="restaurant.name", read_only=True
    )
    rider_username = serializers.CharField(
        source="rider.user.username", read_only=True, default=None
    )
    restaurant_latitude = serializers.DecimalField(
        source="restaurant.latitude",
        max_digits=9,
        decimal_places=6,
        read_only=True,
        allow_null=True,
    )
    restaurant_longitude = serializers.DecimalField(
        source="restaurant.longitude",
        max_digits=9,
        decimal_places=6,
        read_only=True,
        allow_null=True,
    )
    rider_latitude = serializers.DecimalField(
        source="rider.latitude",
        max_digits=9,
        decimal_places=6,
        read_only=True,
        allow_null=True,
    )
    rider_longitude = serializers.DecimalField(
        source="rider.longitude",
        max_digits=9,
        decimal_places=6,
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Order
        # fields = [
        #     "id", "restaurant", "restaurant_name",
        #     "items", "status", "payment_method",
        #     "payment_status", "delivery_address",
        #     "subtotal", "delivery_fee", "total",
        #     "rider", "rider_username",
        #     "created_at", "updated_at",
        #     "confirmed_at", "delivered_at",
        # ]
        fields = "__all__"
        read_only_fields = fields
