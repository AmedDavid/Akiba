from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, Goal, DailySaving, Notification, Subscription
from .achievements import check_and_award_achievement, check_all_achievements, create_goal_deadline_notification, create_streak_milestone_notification


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        # Create free subscription by default
        Subscription.objects.get_or_create(
            user=instance,
            defaults={'tier': 'free', 'status': 'active'}
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()


@receiver(post_save, sender=Goal)
def check_goal_achievements(sender, instance, created, **kwargs):
    """Check achievements when goal is created or updated"""
    if created:
        # First goal achievement
        check_and_award_achievement(instance.user, 'first_goal')
    elif instance.achieved and not instance.achieved_at:
        # Goal just achieved
        from django.utils import timezone
        instance.achieved_at = timezone.now()
        instance.save()
        
        # Award achievement
        check_and_award_achievement(instance.user, 'goal_achieved')
        
        # Create notification
        Notification.objects.create(
            user=instance.user,
            notification_type='goal_achieved',
            title=f'🎉 Goal Achieved: {instance.title}',
            message=f'Congratulations! You\'ve successfully achieved your goal of saving KSh {instance.target_amount:.2f}!',
            related_goal=instance
        )
    
    # Check for deadline approaching
    create_goal_deadline_notification(instance)


@receiver(post_save, sender=DailySaving)
def check_savings_achievements(sender, instance, created, **kwargs):
    """Check achievements when daily saving is created"""
    if created:
        # Update total saved and check achievements
        profile = instance.user.userprofile
        from django.db.models import Sum
        total = DailySaving.objects.filter(user=instance.user).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        profile.total_saved = total
        profile.save()
        
        # Check total saved achievements
        total_float = float(total)
        if total_float >= 100000:
            check_and_award_achievement(instance.user, 'total_saved_100000', int(total_float))
        elif total_float >= 10000:
            check_and_award_achievement(instance.user, 'total_saved_10000', int(total_float))
        elif total_float >= 1000:
            check_and_award_achievement(instance.user, 'total_saved_1000', int(total_float))


@receiver(post_save, sender=UserProfile)
def check_streak_achievements(sender, instance, **kwargs):
    """Check streak achievements when profile is updated"""
    if instance.current_streak > 0:
        # Check streak milestones
        create_streak_milestone_notification(instance.user, instance.current_streak)
        
        # Check streak achievements
        if instance.current_streak >= 100:
            check_and_award_achievement(instance.user, 'streak_100', instance.current_streak)
        elif instance.current_streak >= 30:
            check_and_award_achievement(instance.user, 'streak_30', instance.current_streak)
        elif instance.current_streak >= 7:
            check_and_award_achievement(instance.user, 'streak_7', instance.current_streak)

