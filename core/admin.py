from django.contrib import admin
from .models import (
    UserProfile, MpesaStatement, Goal, DailySaving, Tribe, TribePost,
    Achievement, UserAchievement, SavingsChallenge, ChallengeProgress, Notification,
    Budget, RecurringSavingsPlan, GoalTemplate, Subscription, Payment
)


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


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ['name', 'criteria_type', 'criteria_value', 'points', 'rarity']
    list_filter = ['rarity', 'criteria_type']
    search_fields = ['name', 'description']


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ['user', 'achievement', 'earned_at', 'notified']
    list_filter = ['earned_at', 'notified', 'achievement']
    search_fields = ['user__username', 'achievement__name']


@admin.register(SavingsChallenge)
class SavingsChallengeAdmin(admin.ModelAdmin):
    list_display = ['name', 'challenge_type', 'target_amount', 'start_date', 'end_date', 'is_active']
    list_filter = ['challenge_type', 'is_active', 'start_date']
    search_fields = ['name', 'description']


@admin.register(ChallengeProgress)
class ChallengeProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'challenge', 'amount_saved', 'completed', 'updated_at']
    list_filter = ['completed', 'updated_at']
    search_fields = ['user__username', 'challenge__name']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'month', 'total_budget', 'savings_target', 'created_at']
    list_filter = ['month', 'created_at']
    search_fields = ['user__username']


@admin.register(RecurringSavingsPlan)
class RecurringSavingsPlanAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'amount', 'frequency', 'is_active', 'start_date']
    list_filter = ['frequency', 'is_active', 'start_date']
    search_fields = ['user__username', 'name']


@admin.register(GoalTemplate)
class GoalTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'target_amount', 'suggested_deadline_months', 'is_featured']
    list_filter = ['category', 'is_featured', 'created_at']
    search_fields = ['name', 'description']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'status', 'payment_method', 'expiry_date', 'created_at']
    list_filter = ['tier', 'status', 'payment_method', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'method', 'status', 'transaction_id', 'created_at']
    list_filter = ['method', 'status', 'created_at']
    search_fields = ['user__username', 'transaction_id']
    readonly_fields = ['created_at', 'updated_at']
