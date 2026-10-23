
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from math import radians, sin, cos, asin, sqrt

from django.db import transaction, IntegrityError
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from accounts.models import UserProfile
from restaurants.models import Restaurant, MenuItem
from .models import Order, OrderItem, RiderProfile
from .serializers import OrderSerializer


DELIVERY_FEE = Decimal("100.00")


def profile_role(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.role


def haversine_km(lat1, lon1, lat2, lon2):
    """Approximate straight-line distance between two coordinates."""
    lat1, lon1, lat2, lon2 = map(
        lambda value: radians(float(value)),
        (lat1, lon1, lat2, lon2),
    )
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(min(1, a)))


def assign_nearest_rider(order):
    """
    Call inside transaction.atomic().
    Locks available rider rows while selecting one.
    """
    restaurant = order.restaurant

    if restaurant.latitude is None or restaurant.longitude is None:
        return None

    candidates = list(
        RiderProfile.objects.select_for_update()
        .filter(
            is_available=True,
            latitude__isnull=False,
            longitude__isnull=False,
            user__profile__role=UserProfile.Role.RIDER,
            user__profile__is_approved=True,
        )
    )

    if not candidates:
        return None

    rider = min(
        candidates,
        key=lambda item: haversine_km(
            restaurant.latitude,
            restaurant.longitude,
            item.latitude,
            item.longitude,
        ),
    )

    rider.is_available = False
    rider.save(update_fields=["is_available"])
    order.rider = rider
    order.save(update_fields=["rider", "updated_at"])
    return rider


class PlaceOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if profile_role(request.user) != UserProfile.Role.CUSTOMER:
            return Response(
                {"detail": "Only customer accounts can place orders."},
                status=status.HTTP_403_FORBIDDEN,
            )

        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128:
            return Response(
                {"detail": "Provide an Idempotency-Key header (max 128 characters)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            restaurant_id = int(request.data.get("restaurant_id"))
            address = str(request.data.get("delivery_address", "")).strip()
            raw_items = request.data.get("items")
            if not address or len(address) > 500:
                raise ValueError("Enter a delivery address up to 500 characters.")
            if not isinstance(raw_items, list) or not raw_items:
                raise ValueError("items must be a non-empty list.")

            quantities = {}
            for item in raw_items:
                item_id = int(item["menu_item_id"])
                quantity = int(item["quantity"])
                if quantity < 1 or quantity > 100:
                    raise ValueError("Each quantity must be between 1 and 100.")
                quantities[item_id] = quantities.get(item_id, 0) + quantity
                if quantities[item_id] > 100:
                    raise ValueError("Combined quantity per item cannot exceed 100.")

            if len(quantities) > 50:
                raise ValueError("An order can contain at most 50 distinct menu items.")

            normalized_items = [
                {"menu_item_id": item_id, "quantity": qty}
                for item_id, qty in sorted(quantities.items())
            ]
            canonical_request = {
                "restaurant_id": restaurant_id,
                "delivery_address": address,
                "items": normalized_items,
            }
            request_hash = hashlib.sha256(
                json.dumps(canonical_request, sort_keys=True).encode()
            ).hexdigest()

        except (ValueError, TypeError, KeyError):
            return Response(
                {"detail": "Invalid restaurant, address, items, or quantities."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = Order.objects.filter(
            customer=request.user, idempotency_key=key
        ).first()
        if existing:
            if existing.request_hash != request_hash:
                return Response(
                    {"detail": "This Idempotency-Key was already used for a different order."},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(OrderSerializer(existing).data, status=status.HTTP_200_OK)

        try:
            with transaction.atomic():
                restaurant = Restaurant.objects.select_for_update().get(
                    pk=restaurant_id, is_active=True
                )

                menu_items = list(
                    MenuItem.objects.select_for_update()
                    .filter(
                        id__in=quantities.keys(),
                        restaurant=restaurant,
                        is_available=True,
                    )
                    .order_by("id")
                )

                if len(menu_items) != len(quantities):
                    return Response(
                        {"detail": "One or more menu items are unavailable or belong to another restaurant."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                subtotal = sum(
                    (item.price * quantities[item.id] for item in menu_items),
                    Decimal("0.00"),
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total = subtotal + DELIVERY_FEE

                order = Order.objects.create(
                    customer=request.user,
                    restaurant=restaurant,
                    delivery_address=address,
                    subtotal=subtotal,
                    delivery_fee=DELIVERY_FEE,
                    total=total,
                    idempotency_key=key,
                    request_hash=request_hash,
                )

                OrderItem.objects.bulk_create([
                    OrderItem(
                        order=order,
                        menu_item=item,
                        item_name=item.name,
                        unit_price=item.price,
                        quantity=quantities[item.id],
                        line_total=item.price * quantities[item.id],
                    )
                    for item in menu_items
                ])

        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found or inactive."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            # Another concurrent request may have won the same idempotency key.
            existing = Order.objects.filter(
                customer=request.user, idempotency_key=key
            ).first()
            if existing:
                if existing.request_hash != request_hash:
                    return Response(
                        {"detail": "Idempotency-Key reused with a different order."},
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response(OrderSerializer(existing).data, status=status.HTTP_200_OK)
            raise

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class MyOrdersView(ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .select_related("restaurant", "rider__user")
            .prefetch_related("items")
        )


class RestaurantOrdersView(ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if profile_role(self.request.user) != UserProfile.Role.RESTAURANT:
            return Order.objects.none()

        return (
            Order.objects.filter(restaurant__manager=self.request.user)
            .select_related("restaurant", "customer", "rider__user")
            .prefetch_related("items")
        )


class RestaurantOrderActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, order_id):
        if profile_role(request.user) != UserProfile.Role.RESTAURANT:
            return Response({"detail": "Restaurant manager access required."},
                            status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status")
        allowed = {
            Order.Status.PENDING: {
                Order.Status.CONFIRMED, Order.Status.REJECTED,
            },
            Order.Status.CONFIRMED: {Order.Status.PREPARING},
            Order.Status.PREPARING: {Order.Status.READY},
        }

        with transaction.atomic():
            try:
                order = (
                    Order.objects.select_for_update()
                    .select_related("restaurant")
                    .get(
                        pk=order_id,
                        restaurant__manager=request.user,
                    )
                )
            except Order.DoesNotExist:
                return Response({"detail": "Order not found."},
                                status=status.HTTP_404_NOT_FOUND)

            if new_status not in allowed.get(order.status, set()):
                return Response(
                    {"detail": f"Cannot change order from {order.status} to {new_status}."},
                    status=status.HTTP_409_CONFLICT,
                )

            order.status = new_status

            if new_status == Order.Status.CONFIRMED:
                order.confirmed_at = timezone.now()

            order.save(update_fields=["status", "confirmed_at", "updated_at"])

            if new_status == Order.Status.READY:
                assign_nearest_rider(order)

        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class RiderAvailabilityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        if profile_role(request.user) != UserProfile.Role.RIDER:
            return Response({"detail": "Rider account required."},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            latitude = Decimal(str(request.data["latitude"]))
            longitude = Decimal(str(request.data["longitude"]))
            available = request.data.get("is_available", True)

            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError()
            if not isinstance(available, bool):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            return Response(
                {"detail": "Provide valid latitude, longitude and boolean is_available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rider, _ = RiderProfile.objects.get_or_create(user=request.user)
        if available and rider.orders.filter(
            status__in=[Order.Status.READY, Order.Status.PICKED_UP]
        ).exists():
            return Response(
                {"detail": "You cannot become available while an active delivery is assigned."},
                status=status.HTTP_409_CONFLICT,
            )

        rider.latitude = latitude
        rider.longitude = longitude
        rider.is_available = available
        rider.save()
        return Response({"message": "Rider location and availability updated."})


class RiderOrdersView(ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if profile_role(self.request.user) != UserProfile.Role.RIDER:
            return Order.objects.none()

        return (
            Order.objects.filter(rider__user=self.request.user)
            .select_related("restaurant", "customer", "rider__user")
            .prefetch_related("items")
        )


class RiderOrderActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, order_id):
        if profile_role(request.user) != UserProfile.Role.RIDER:
            return Response({"detail": "Rider account required."},
                            status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status")
        allowed = {
            Order.Status.READY: Order.Status.PICKED_UP,
            Order.Status.PICKED_UP: Order.Status.DELIVERED,
        }

        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(
                    pk=order_id, rider__user=request.user
                )
            except Order.DoesNotExist:
                return Response({"detail": "Assigned order not found."},
                                status=status.HTTP_404_NOT_FOUND)

            if allowed.get(order.status) != new_status:
                return Response(
                    {"detail": f"Cannot change order from {order.status} to {new_status}."},
                    status=status.HTTP_409_CONFLICT,
                )

            order.status = new_status
            fields = ["status", "updated_at"]

            if new_status == Order.Status.DELIVERED:
                order.delivered_at = timezone.now()
                fields.append("delivered_at")

            order.save(update_fields=fields)

            if new_status == Order.Status.DELIVERED:
                rider = RiderProfile.objects.select_for_update().get(
                    pk=order.rider_id
                )
                rider.is_available = True
                rider.save(update_fields=["is_available"])

        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class AdminMonitoringView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        active_statuses = [
            Order.Status.PENDING,
            Order.Status.CONFIRMED,
            Order.Status.PREPARING,
            Order.Status.READY,
            Order.Status.PICKED_UP,
        ]

        counts = {
            "total_orders": Order.objects.count(),
            "active_orders": Order.objects.filter(status__in=active_statuses).count(),
            "delivered_orders": Order.objects.filter(status=Order.Status.DELIVERED).count(),
            "rejected_orders": Order.objects.filter(status=Order.Status.REJECTED).count(),
            "available_riders": RiderProfile.objects.filter(
                is_available=True
            ).count(),
            "total_restaurants": Restaurant.objects.count(),
        }

        revenue = Order.objects.filter(
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.PAID,
        ).aggregate(amount=Sum("total"))["amount"] or Decimal("0.00")

        counts["paid_delivered_revenue"] = str(revenue)
        return Response(counts)
