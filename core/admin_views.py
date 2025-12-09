"""
Custom Admin Dashboard Views
Uses Django's authentication and permission system (is_staff, is_superuser)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
import csv
import json
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    UserProfile, Goal, DailySaving, MpesaStatement, Tribe, TribePost,
    Achievement, UserAchievement, SavingsChallenge, ChallengeProgress, Notification,
    Budget, RecurringSavingsPlan, GoalTemplate, Subscription, Payment
)
from .forms import CustomAuthenticationForm


def staff_required(view_func):
    """Decorator to require staff status"""
    from functools import wraps
    from django.contrib.auth.decorators import login_required
    from django.contrib.auth.views import redirect_to_login
    from django.http import HttpResponseForbidden
    
    @wraps(view_func)
    @login_required(login_url='/admin/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden(
                '<h1>403 Forbidden</h1><p>You do not have permission to access this page. Staff access required.</p><p><a href="/dashboard/">Return to Dashboard</a></p>'
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def admin_login(request):
    """Custom admin login page"""
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'You do not have permission to access the admin dashboard. Staff access required.')
            return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            from django.contrib.auth import login
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                messages.success(request, f'Welcome to Admin Dashboard, {user.username}!')
                next_url = request.GET.get('next', '/admin/')
                return redirect(next_url)
            else:
                messages.error(request, 'You do not have permission to access the admin dashboard.')
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'custom_admin/login.html', {'form': form})


@staff_required
def admin_dashboard(request):
    """Main admin dashboard with statistics"""
    # Double check - should be handled by decorator but just in case
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    # Calculate statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    pro_users = Subscription.objects.filter(tier='pro', status='active').count()
    new_users_today = User.objects.filter(date_joined__date=timezone.now().date()).count()
    new_users_this_week = User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=7)).count()
    
    # Goals statistics
    total_goals = Goal.objects.count()
    active_goals = Goal.objects.filter(achieved=False).count()
    achieved_goals = Goal.objects.filter(achieved=True).count()
    total_target_amount = Goal.objects.aggregate(Sum('target_amount'))['target_amount__sum'] or 0
    total_current_amount = Goal.objects.aggregate(Sum('current_amount'))['current_amount__sum'] or 0
    
    # Savings statistics
    total_savings = DailySaving.objects.aggregate(Sum('amount'))['amount__sum'] or 0
    total_saved_profiles = UserProfile.objects.aggregate(Sum('total_saved'))['total_saved__sum'] or 0
    savings_today = DailySaving.objects.filter(date=timezone.now().date()).aggregate(Sum('amount'))['amount__sum'] or 0
    savings_this_week = DailySaving.objects.filter(date__gte=timezone.now().date() - timedelta(days=7)).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Payment statistics
    total_payments = Payment.objects.count()
    completed_payments = Payment.objects.filter(status='completed').count()
    pending_payments = Payment.objects.filter(status='pending').count()
    total_revenue = Payment.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    revenue_today = Payment.objects.filter(status='completed', created_at__date=timezone.now().date()).aggregate(Sum('amount'))['amount__sum'] or 0
    revenue_this_month = Payment.objects.filter(
        status='completed',
        created_at__month=timezone.now().month,
        created_at__year=timezone.now().year
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Subscription statistics
    free_subscriptions = Subscription.objects.filter(tier='free').count()
    pro_subscriptions = Subscription.objects.filter(tier='pro', status='active').count()
    expired_subscriptions = Subscription.objects.filter(status='expired').count()
    
    # Tribes statistics
    total_tribes = Tribe.objects.count()
    private_tribes = Tribe.objects.filter(is_private=True).count()
    public_tribes = Tribe.objects.filter(is_private=False).count()
    total_tribe_posts = TribePost.objects.count()
    
    # Statements statistics
    total_statements = MpesaStatement.objects.count()
    statements_this_month = MpesaStatement.objects.filter(
        uploaded_at__month=timezone.now().month,
        uploaded_at__year=timezone.now().year
    ).count()
    
    # Recent activity
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_payments = Payment.objects.filter(status='completed').order_by('-created_at')[:5]
    recent_goals = Goal.objects.order_by('-created_at')[:5]
    
    # User growth data (last 30 days)
    user_growth_data = []
    for i in range(30, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        count = User.objects.filter(date_joined__date__lte=date).count()
        user_growth_data.append({'date': date.strftime('%Y-%m-%d'), 'count': count})
    
    # Revenue trend (last 7 days)
    revenue_trend = []
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        daily_revenue = Payment.objects.filter(
            status='completed',
            created_at__date=date
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        revenue_trend.append({'date': date.strftime('%m/%d'), 'amount': float(daily_revenue)})
    
    # Savings trend (last 7 days)
    savings_trend = []
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        daily_savings = DailySaving.objects.filter(date=date).aggregate(Sum('amount'))['amount__sum'] or 0
        savings_trend.append({'date': date.strftime('%m/%d'), 'amount': float(daily_savings)})
    
    # Payment method breakdown
    mpesa_payments = Payment.objects.filter(method='mpesa', status='completed').count()
    stripe_payments = Payment.objects.filter(method='stripe', status='completed').count()
    mpesa_revenue = Payment.objects.filter(method='mpesa', status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    stripe_revenue = Payment.objects.filter(method='stripe', status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Top savers
    top_savers = UserProfile.objects.order_by('-total_saved')[:5]
    
    # Top tribes by members
    top_tribes = Tribe.objects.annotate(member_count=Count('members')).order_by('-member_count')[:5]
    
    # Active challenges
    active_challenges = SavingsChallenge.objects.filter(is_active=True).count()
    completed_challenges = SavingsChallenge.objects.filter(is_active=False).count()
    
    # Achievements statistics
    total_achievements = Achievement.objects.count()
    total_user_achievements = UserAchievement.objects.count()
    unique_users_with_achievements = UserAchievement.objects.values('user').distinct().count()
    
    # Notifications statistics
    total_notifications = Notification.objects.count()
    unread_notifications = Notification.objects.filter(is_read=False).count()
    
    # Goals by category
    goals_by_category = {}
    for category_code, category_name in Goal.CATEGORY_CHOICES:
        count = Goal.objects.filter(category=category_code).count()
        if count > 0:
            goals_by_category[category_name] = count
    
    # Failed payments
    failed_payments = Payment.objects.filter(status='failed').count()
    
    # Average goal progress
    avg_goal_progress = 0
    if total_goals > 0:
        avg_goal_progress = (total_current_amount / total_target_amount * 100) if total_target_amount > 0 else 0
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'pro_users': pro_users,
        'new_users_today': new_users_today,
        'new_users_this_week': new_users_this_week,
        'total_goals': total_goals,
        'active_goals': active_goals,
        'achieved_goals': achieved_goals,
        'total_target_amount': total_target_amount,
        'total_current_amount': total_current_amount,
        'avg_goal_progress': avg_goal_progress,
        'total_savings': total_savings,
        'total_saved_profiles': total_saved_profiles,
        'savings_today': savings_today,
        'savings_this_week': savings_this_week,
        'total_payments': total_payments,
        'completed_payments': completed_payments,
        'pending_payments': pending_payments,
        'failed_payments': failed_payments,
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'revenue_this_month': revenue_this_month,
        'free_subscriptions': free_subscriptions,
        'pro_subscriptions': pro_subscriptions,
        'expired_subscriptions': expired_subscriptions,
        'total_tribes': total_tribes,
        'private_tribes': private_tribes,
        'public_tribes': public_tribes,
        'total_tribe_posts': total_tribe_posts,
        'total_statements': total_statements,
        'statements_this_month': statements_this_month,
        'recent_users': recent_users,
        'recent_payments': recent_payments,
        'recent_goals': recent_goals,
        'user_growth_data': json.dumps(user_growth_data),
        'revenue_trend': json.dumps(revenue_trend),
        'savings_trend': json.dumps(savings_trend),
        'mpesa_payments': mpesa_payments,
        'stripe_payments': stripe_payments,
        'mpesa_revenue': mpesa_revenue,
        'stripe_revenue': stripe_revenue,
        'top_savers': top_savers,
        'top_tribes': top_tribes,
        'active_challenges': active_challenges,
        'completed_challenges': completed_challenges,
        'total_achievements': total_achievements,
        'total_user_achievements': total_user_achievements,
        'unique_users_with_achievements': unique_users_with_achievements,
        'total_notifications': total_notifications,
        'unread_notifications': unread_notifications,
        'goals_by_category': goals_by_category,
    }
    
    return render(request, 'custom_admin/dashboard.html', context)


@staff_required
def admin_users(request):
    """Manage users"""
    search_query = request.GET.get('search', '')
    filter_type = request.GET.get('filter', 'all')
    
    users = User.objects.all()
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if filter_type == 'active':
        users = users.filter(is_active=True)
    elif filter_type == 'inactive':
        users = users.filter(is_active=False)
    elif filter_type == 'staff':
        users = users.filter(is_staff=True)
    elif filter_type == 'pro':
        pro_user_ids = Subscription.objects.filter(tier='pro', status='active').values_list('user_id', flat=True)
        users = users.filter(id__in=pro_user_ids)
    
    users = users.order_by('-date_joined')
    
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_type': filter_type,
    }
    
    return render(request, 'custom_admin/users.html', context)


@staff_required
def admin_user_detail(request, user_id):
    """View user details"""
    user = get_object_or_404(User, id=user_id)
    profile = getattr(user, 'userprofile', None)
    subscription = getattr(user, 'subscription', None)
    goals = Goal.objects.filter(user=user)
    payments = Payment.objects.filter(user=user)
    savings = DailySaving.objects.filter(user=user).order_by('-date')[:10]
    statements = MpesaStatement.objects.filter(user=user).order_by('-uploaded_at')[:5]
    achievements = UserAchievement.objects.filter(user=user)
    
    context = {
        'user': user,
        'profile': profile,
        'subscription': subscription,
        'goals': goals,
        'payments': payments,
        'savings': savings,
        'statements': statements,
        'achievements': achievements,
    }
    
    return render(request, 'custom_admin/user_detail.html', context)


@staff_required
def admin_user_toggle_active(request, user_id):
    """Toggle user active status"""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        user.is_active = not user.is_active
        user.save()
        messages.success(request, f'User {user.username} is now {"active" if user.is_active else "inactive"}.')
    return redirect('admin_user_detail', user_id=user_id)


@staff_required
def admin_goals(request):
    """Manage goals"""
    search_query = request.GET.get('search', '')
    filter_type = request.GET.get('filter', 'all')
    
    goals = Goal.objects.all()
    
    if search_query:
        goals = goals.filter(
            Q(title__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    
    if filter_type == 'active':
        goals = goals.filter(achieved=False)
    elif filter_type == 'achieved':
        goals = goals.filter(achieved=True)
    elif filter_type == 'overdue':
        goals = goals.filter(achieved=False, deadline__lt=timezone.now().date())
    
    goals = goals.order_by('-created_at')
    
    paginator = Paginator(goals, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_type': filter_type,
        'today': timezone.now().date(),
    }
    
    return render(request, 'custom_admin/goals.html', context)


@staff_required
def admin_payments(request):
    """Manage payments"""
    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('status', 'all')
    filter_method = request.GET.get('method', 'all')
    
    payments = Payment.objects.all()
    
    if search_query:
        payments = payments.filter(
            Q(user__username__icontains=search_query) |
            Q(transaction_id__icontains=search_query)
        )
    
    if filter_status != 'all':
        payments = payments.filter(status=filter_status)
    
    if filter_method != 'all':
        payments = payments.filter(method=filter_method)
    
    payments = payments.order_by('-created_at')
    
    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_status': filter_status,
        'filter_method': filter_method,
    }
    
    return render(request, 'custom_admin/payments.html', context)


@staff_required
def admin_subscriptions(request):
    """Manage subscriptions"""
    search_query = request.GET.get('search', '')
    filter_tier = request.GET.get('tier', 'all')
    filter_status = request.GET.get('status', 'all')
    
    subscriptions = Subscription.objects.all()
    
    if search_query:
        subscriptions = subscriptions.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    if filter_tier != 'all':
        subscriptions = subscriptions.filter(tier=filter_tier)
    
    if filter_status != 'all':
        subscriptions = subscriptions.filter(status=filter_status)
    
    subscriptions = subscriptions.order_by('-created_at')
    
    paginator = Paginator(subscriptions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_tier': filter_tier,
        'filter_status': filter_status,
        'today': timezone.now().date(),
    }
    
    return render(request, 'custom_admin/subscriptions.html', context)


@staff_required
def admin_tribes(request):
    """Manage tribes"""
    search_query = request.GET.get('search', '')
    filter_type = request.GET.get('type', 'all')
    
    tribes = Tribe.objects.all()
    
    if search_query:
        tribes = tribes.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if filter_type == 'private':
        tribes = tribes.filter(is_private=True)
    elif filter_type == 'public':
        tribes = tribes.filter(is_private=False)
    
    tribes = tribes.annotate(member_count=Count('members')).order_by('-created_at')
    
    paginator = Paginator(tribes, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_type': filter_type,
    }
    
    return render(request, 'custom_admin/tribes.html', context)


@staff_required
def admin_statements(request):
    """Manage M-Pesa statements"""
    search_query = request.GET.get('search', '')
    
    statements = MpesaStatement.objects.all()
    
    if search_query:
        statements = statements.filter(
            Q(user__username__icontains=search_query)
        )
    
    statements = statements.order_by('-uploaded_at')
    
    paginator = Paginator(statements, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'custom_admin/statements.html', context)


@staff_required
def admin_export_data(request):
    """Export admin data to CSV"""
    export_type = request.GET.get('type', 'users')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="akiba_{export_type}_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    if export_type == 'users':
        writer.writerow(['Username', 'Email', 'Date Joined', 'Is Active', 'Is Staff', 'Total Saved', 'Current Streak'])
        for user in User.objects.all():
            profile = getattr(user, 'userprofile', None)
            writer.writerow([
                user.username,
                user.email,
                user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                user.is_active,
                user.is_staff,
                profile.total_saved if profile else 0,
                profile.current_streak if profile else 0,
            ])
    
    elif export_type == 'payments':
        writer.writerow(['User', 'Amount', 'Method', 'Status', 'Transaction ID', 'Created At'])
        for payment in Payment.objects.all().order_by('-created_at'):
            writer.writerow([
                payment.user.username,
                payment.amount,
                payment.method,
                payment.status,
                payment.transaction_id,
                payment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])
    
    elif export_type == 'goals':
        writer.writerow(['User', 'Title', 'Category', 'Target Amount', 'Current Amount', 'Progress %', 'Achieved', 'Created At'])
        for goal in Goal.objects.all().order_by('-created_at'):
            progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
            writer.writerow([
                goal.user.username,
                goal.title,
                goal.get_category_display(),
                goal.target_amount,
                goal.current_amount,
                f"{progress:.2f}%",
                goal.achieved,
                goal.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])
    
    elif export_type == 'subscriptions':
        writer.writerow(['User', 'Tier', 'Status', 'Payment Method', 'Expiry Date', 'Created At'])
        for subscription in Subscription.objects.all().order_by('-created_at'):
            writer.writerow([
                subscription.user.username,
                subscription.tier,
                subscription.status,
                subscription.payment_method or 'N/A',
                subscription.expiry_date.strftime('%Y-%m-%d') if subscription.expiry_date else 'N/A',
                subscription.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])
    
    return response

