from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache_utils import invalidate_cache
from .models import Restaurant, MenuItem


@receiver([post_save, post_delete], sender=Restaurant)
def restaurant_changed(sender, **kwargs):
    invalidate_cache("restaurants")
    invalidate_cache("menu-items")


@receiver([post_save, post_delete], sender=MenuItem)
def menu_item_changed(sender, **kwargs):
    invalidate_cache("menu-items")