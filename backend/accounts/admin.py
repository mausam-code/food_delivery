from django.contrib import admin

# Register your models here.

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "is_approved", "created_at")
    list_filter = ("role", "is_approved")
    search_fields = ("user__username", "user__email", "phone")
    list_editable = ("is_approved",)
