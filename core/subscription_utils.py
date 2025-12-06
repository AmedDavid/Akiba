"""
Utility functions for subscription management and paywall gating
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import Subscription


def get_user_subscription(user):
    """Get or create subscription for user"""
    subscription, created = Subscription.objects.get_or_create(
        user=user,
        defaults={'tier': 'free', 'status': 'active'}
    )
    return subscription


def is_pro_user(user):
    """Check if user has active Pro subscription"""
    if not user.is_authenticated:
        return False
    try:
        subscription = user.subscription
        return subscription.is_pro()
    except Subscription.DoesNotExist:
        # Create free subscription if doesn't exist
        subscription = Subscription.objects.create(user=user, tier='free', status='active')
        return False


def pro_required(view_func):
    """Decorator to require Pro subscription for a view"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this feature.')
            return redirect('login')
        
        if not is_pro_user(request.user):
            messages.warning(request, 'This feature requires a Pro subscription. Upgrade to unlock!')
            return redirect('pricing')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def pro_required_json(view_func):
    """Decorator to require Pro subscription for JSON API views"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        if not is_pro_user(request.user):
            return JsonResponse({'error': 'Pro subscription required', 'upgrade_url': '/pricing/'}, status=403)
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def check_feature_access(user, feature_name):
    """
    Check if user has access to a specific feature
    Returns (has_access, message)
    """
    if not user.is_authenticated:
        return False, 'Please log in to access this feature.'
    
    subscription = get_user_subscription(user)
    
    # Feature-specific checks
    feature_limits = {
        'goals': {'free': 3, 'pro': None},  # None = unlimited
        'tribes_join': {'free': 2, 'pro': None},
        'statements_months': {'free': 3, 'pro': 12},
        'analytics_months': {'free': 3, 'pro': 12},
    }
    
    if feature_name in feature_limits:
        limit = feature_limits[feature_name]
        if subscription.tier == 'free' and limit['free'] is not None:
            # Check current count
            if feature_name == 'goals':
                from .models import Goal
                count = Goal.objects.filter(user=user, achieved=False).count()
                if count >= limit['free']:
                    return False, f'Free users can have up to {limit["free"]} active goals. Upgrade to Pro for unlimited goals!'
            elif feature_name == 'tribes_join':
                count = user.tribes.filter(is_private=False).count()
                if count >= limit['free']:
                    return False, f'Free users can join up to {limit["free"]} public tribes. Upgrade to Pro for unlimited tribes!'
    
    # Pro-only features
    pro_only_features = [
        'create_tribe', 'create_private_tribe', 'budget', 'recurring_plans',
        'challenge_create', 'export_reports', 'advanced_analytics', 'streak_multiplier',
        'streak_recovery', 'leak_buster_reports'
    ]
    
    if feature_name in pro_only_features:
        if not subscription.is_pro():
            return False, 'This feature requires a Pro subscription. Upgrade to unlock!'
    
    return True, None


def get_feature_limit(user, feature_name):
    """Get the limit for a feature for the current user"""
    subscription = get_user_subscription(user)
    
    limits = {
        'goals': {'free': 3, 'pro': None},
        'tribes_join': {'free': 2, 'pro': None},
        'statements_months': {'free': 3, 'pro': 12},
        'analytics_months': {'free': 3, 'pro': 12},
    }
    
    if feature_name in limits:
        tier_limit = limits[feature_name]
        if subscription.tier == 'pro' and subscription.is_pro():
            return tier_limit['pro']
        return tier_limit['free']
    
    return None

