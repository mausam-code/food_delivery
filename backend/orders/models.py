
from django.conf import settings
from django.db import models


class RiderProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rider_profile",
    )
    is_available = models.BooleanField(default=False, db_index=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    def __str__(self):
        return f"Rider: {self.user.username}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for restaurant"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready for pickup"
        PICKED_UP = "picked_up", "Picked up"
        DELIVERED = "delivered", "Delivered"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on delivery"
        MOCK = "mock", "Simulated online payment"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="food_orders",
    )
    restaurant = models.ForeignKey(
        "restaurants.Restaurant",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )

    delivery_address = models.CharField(max_length=500)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=100
    )
    total = models.DecimalField(max_digits=12, decimal_places=2)

    # The client supplies this key to safely retry checkout.
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "idempotency_key"],
                name="unique_customer_order_idempotency",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="order_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(delivery_fee__gte=0),
                name="order_delivery_fee_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="order_total_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["restaurant", "status", "created_at"],
                name="order_rest_status_created_idx",
            ),
            models.Index(
                fields=["rider", "status"],
                name="order_rider_status_idx",
            ),
        ]

    def __str__(self):
        return f"Order #{self.pk} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    menu_item = models.ForeignKey(
        "restaurants.MenuItem",
        on_delete=models.PROTECT,
        related_name="ordered_items",
    )

    # Snapshots preserve what the customer ordered at checkout.
    item_name = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="order_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_item_price_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.item_name}"
