"""
Achievement checking and awarding logic
"""
from django.utils import timezone
from .models import Achievement, UserAchievement, Notification, UserProfile, Goal, DailySaving, Tribe


def check_and_award_achievement(user, criteria_type, value=1):
    """Check if user qualifies for an achievement and award it"""
    achievements = Achievement.objects.filter(criteria_type=criteria_type, criteria_value__lte=value)
    
    for achievement in achievements:
        # Check if user already has this achievement
        if not UserAchievement.objects.filter(user=user, achievement=achievement).exists():
            # Award achievement
            user_achievement = UserAchievement.objects.create(
                user=user,
                achievement=achievement
            )
            
            # Create notification
            Notification.objects.create(
                user=user,
                notification_type='achievement_earned',
                title=f'Achievement Unlocked: {achievement.name}',
                message=achievement.description,
                related_achievement=user_achievement
            )
            
            return user_achievement
    return None


def check_all_achievements(user):
    """Check all achievements for a user"""
    profile = user.userprofile
    
    # Check first goal
    if Goal.objects.filter(user=user).exists():
        check_and_award_achievement(user, 'first_goal')
    
    # Check goal achieved
    achieved_count = Goal.objects.filter(user=user, achieved=True).count()
    if achieved_count > 0:
        check_and_award_achievement(user, 'goal_achieved', achieved_count)
    
    # Check streaks
    if profile.current_streak >= 7:
        check_and_award_achievement(user, 'streak_7', profile.current_streak)
    if profile.current_streak >= 30:
        check_and_award_achievement(user, 'streak_30', profile.current_streak)
    if profile.current_streak >= 100:
        check_and_award_achievement(user, 'streak_100', profile.current_streak)
    
    # Check total saved
    total = float(profile.total_saved)
    if total >= 100000:
        check_and_award_achievement(user, 'total_saved_100000', int(total))
    elif total >= 10000:
        check_and_award_achievement(user, 'total_saved_10000', int(total))
    elif total >= 1000:
        check_and_award_achievement(user, 'total_saved_1000', int(total))
    
    # Check tribe participation
    if Tribe.objects.filter(members=user).exists():
        check_and_award_achievement(user, 'join_tribe')
    
    if Tribe.objects.filter(created_by=user).exists():
        check_and_award_achievement(user, 'create_tribe')
    
    # Check M-Pesa upload
    from .models import MpesaStatement
    if MpesaStatement.objects.filter(user=user).exists():
        check_and_award_achievement(user, 'upload_statement')


def create_goal_deadline_notification(goal):
    """Create notification for goal deadline approaching"""
    today = timezone.now().date()
    days_remaining = (goal.deadline - today).days
    
    if 0 < days_remaining <= 7 and not goal.achieved:
        # Check if notification already exists
        if not Notification.objects.filter(
            user=goal.user,
            notification_type='goal_deadline',
            related_goal=goal,
            created_at__date=today
        ).exists():
            Notification.objects.create(
                user=goal.user,
                notification_type='goal_deadline',
                title=f'Goal Deadline Approaching: {goal.title}',
                message=f'Your goal "{goal.title}" deadline is in {days_remaining} day(s). You have saved KSh {goal.current_amount:.2f} of KSh {goal.target_amount:.2f}.',
                related_goal=goal
            )


def create_streak_milestone_notification(user, streak_days):
    """Create notification for streak milestones"""
    milestones = [7, 30, 50, 100, 200, 365]
    
    if streak_days in milestones:
        if not Notification.objects.filter(
            user=user,
            notification_type='streak_milestone',
            message__contains=f'{streak_days} days',
            created_at__date=timezone.now().date()
        ).exists():
            Notification.objects.create(
                user=user,
                notification_type='streak_milestone',
                title=f'🔥 {streak_days} Day Streak!',
                message=f'Congratulations! You\'ve maintained a {streak_days}-day savings streak. Keep it up!'
            )

