from django.contrib import admin
from .models import UserProfile, MpesaStatement, Goal, DailySaving, Tribe, TribePost


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'total_saved', 'current_streak', 'longest_streak', 'last_checkin']
    list_filter = ['created_at']
    search_fields = ['user__username', 'user__email', 'phone']


@admin.register(MpesaStatement)
class MpesaStatementAdmin(admin.ModelAdmin):
    list_display = ['user', 'uploaded_at', 'period_months', 'total_incoming', 'total_outgoing']
    list_filter = ['uploaded_at']
    search_fields = ['user__username']


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'target_amount', 'current_amount', 'deadline', 'achieved', 'category']
    list_filter = ['achieved', 'category', 'created_at']
    search_fields = ['user__username', 'title']


@admin.register(DailySaving)
class DailySavingAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'amount', 'note']
    list_filter = ['date', 'created_at']
    search_fields = ['user__username']


@admin.register(Tribe)
class TribeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_private', 'created_by', 'created_at']
    list_filter = ['is_private', 'created_at']
    search_fields = ['name', 'description']


@admin.register(TribePost)
class TribePostAdmin(admin.ModelAdmin):
    list_display = ['tribe', 'user', 'created_at']
    list_filter = ['created_at', 'tribe']
    search_fields = ['user__username', 'content']
