from rest_framework import generics
from .models import Restaurant, MenuItem
from .serializers import (
    RestaurantSerializer,
    RestaurantDetailSerializer,
    MenuItemSerializer,
)

from django.core.cache import cache
from rest_framework.response import Response

from .cache_utils import get_cache_generation


class CachedListMixin:
    cache_namespace = None
    cache_timeout = 60

    def list(self, request, *args, **kwargs):
        generation = get_cache_generation(self.cache_namespace)

        cache_key = (
            f"foodflow:{self.cache_namespace}:"
            f"v{generation}:{request.get_full_path()}"
        )

        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(
                cache_key, 
                response.data, 
                timeout = self.cache_timeout,
            )

        return response


class RestaurantListView(CachedListMixin, generics.ListAPIView):

    cache_namespace = "restaurants"
    serializer_class = RestaurantSerializer

    def get_queryset(self):
        return Restaurant.objects.filter(is_active=True)


class RestaurantDetailView(generics.RetrieveAPIView):
    serializer_class = RestaurantDetailSerializer

    def get_queryset(self):
        return (
            Restaurant.objects
            .filter(is_active=True)
            .prefetch_related("menu_items")
        )


class MenuItemListView(CachedListMixin, generics.ListAPIView):

    cache_namespace = "menu-items"
    serializer_class = MenuItemSerializer

    def get_queryset(self):
        queryset = MenuItem.objects.filter(
            restaurant__is_active=True,
            is_available=True,
        )

        restaurant_id = self.request.query_params.get(
            "restaurant_id"
        )

        if restaurant_id:
            queryset = queryset.filter(
                restaurant_id=restaurant_id
            )

        return queryset