from django.contrib import admin
from .models import NGOProfile, HelpRequest, Match

@admin.register(NGOProfile)
class NGOProfileAdmin(admin.ModelAdmin):
    list_display = ('ngo_name', 'user', 'city', 'is_verified', 'rating')
    list_filter = ('is_verified', 'city')
    search_fields = ('ngo_name', 'registration_number', 'user__username')
    list_editable = ('is_verified',)

@admin.register(HelpRequest)
class HelpRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'beneficiary', 'category', 'city', 'urgency', 'priority_label', 'is_duplicate', 'is_suspicious', 'status', 'created_at')
    list_filter = ('status', 'urgency', 'priority_label', 'is_duplicate', 'is_suspicious', 'category', 'city')
    search_fields = ('title', 'description', 'beneficiary__username')

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('request', 'ngo', 'score', 'rank')
    list_filter = ('rank',)
    search_fields = ('request__title', 'ngo__ngo_name')
