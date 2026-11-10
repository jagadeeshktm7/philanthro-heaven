from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

# Register CustomUser with UserAdmin so it appears nicely in admin panel
admin.site.register(CustomUser, UserAdmin)
