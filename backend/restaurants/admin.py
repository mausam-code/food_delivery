from django.contrib import admin
from .models import Restaurant, MenuItem


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 1


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "address", "is_active")
    search_fields = ("name", "address")
    list_filter = ("is_active",)
    inlines = [MenuItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "restaurant",
        "price",
        "is_available",
    )
    list_filter = ("is_available", "restaurant")
    search_fields = ("name", "restaurant__name")