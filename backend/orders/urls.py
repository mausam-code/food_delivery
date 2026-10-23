
from django.urls import path

from .views import (
    PlaceOrderView,
    MyOrdersView,
    RestaurantOrdersView,
    RestaurantOrderActionView,
    RiderAvailabilityView,
    RiderOrdersView,
    RiderOrderActionView,
    AdminMonitoringView,
)

urlpatterns = [
    path("", PlaceOrderView.as_view(), name="place-order"),
    path("mine/", MyOrdersView.as_view(), name="my-orders"),

    path(
        "restaurant/",
        RestaurantOrdersView.as_view(),
        name="restaurant-orders",
    ),
    path(
        "restaurant/<int:order_id>/status/",
        RestaurantOrderActionView.as_view(),
        name="restaurant-order-status",
    ),

    path(
        "rider/availability/",
        RiderAvailabilityView.as_view(),
        name="rider-availability",
    ),
    path("rider/", RiderOrdersView.as_view(), name="rider-orders"),
    path(
        "rider/<int:order_id>/status/",
        RiderOrderActionView.as_view(),
        name="rider-order-status",
    ),

    path("admin-monitoring/", AdminMonitoringView.as_view(), name="admin-monitoring"),
]
