from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Password reset
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='core/password_reset.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='core/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='core/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='core/password_reset_complete.html'), name='password_reset_complete'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('goals/', views.goals_list, name='goals'),
    path('goals/create/', views.goal_create, name='goal_create'),
    path('goals/<int:goal_id>/', views.goal_detail, name='goal_detail'),
    path('daily-saving/', views.daily_saving_log, name='daily_saving_log'),
    path('upload/', views.upload_statement, name='upload_statement'),
    path('insights/', views.insights, name='insights'),
    path('tribes/', views.tribes_list, name='tribes'),
    path('tribes/create/', views.tribe_create, name='tribe_create'),
    path('tribes/<int:tribe_id>/', views.tribe_detail, name='tribe_detail'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('achievements/', views.achievements_view, name='achievements'),
    path('challenges/', views.challenges_view, name='challenges'),
    path('challenges/<int:challenge_id>/', views.challenge_detail, name='challenge_detail'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('budget/', views.budget_view, name='budget'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('recurring-plans/', views.recurring_plans_view, name='recurring_plans'),
    path('calculator/', views.savings_calculator, name='calculator'),
    path('goal-templates/', views.goal_templates_view, name='goal_templates'),
    path('goal-templates/<int:template_id>/create/', views.create_goal_from_template, name='create_goal_from_template'),
]

