from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
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
]

