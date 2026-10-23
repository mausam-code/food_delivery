
from django.contrib import admin
from .models import Order, OrderItem, RiderProfile


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "menu_item", "item_name", "unit_price",
        "quantity", "line_total",
    )
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "customer", "restaurant", "status",
        "payment_status", "total", "rider", "created_at",
    )
    list_filter = ("status", "payment_status", "created_at")
    search_fields = (
        "customer__username",
        "restaurant__name",
        "delivery_address",
    )
    readonly_fields = (
        "customer", "restaurant", "rider",
        "subtotal", "delivery_fee", "total",
        "idempotency_key", "request_hash",
        "created_at", "updated_at", "confirmed_at", "delivered_at",
    )
    inlines = [OrderItemInline]
    list_select_related = ("customer", "restaurant", "rider")


@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_available", "latitude", "longitude")
    list_filter = ("is_available",)
    search_fields = ("user__username",)
