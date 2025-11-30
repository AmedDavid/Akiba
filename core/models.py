from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
import os


def avatar_upload_path(instance, filename):
    return f'avatars/{instance.user.id}/{filename}'


def statement_upload_path(instance, filename):
    return f'statements/{instance.user.id}/{filename}'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    total_saved = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_checkin = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def update_streak(self):
        """Update streak based on last check-in"""
        today = timezone.now().date()
        if self.last_checkin:
            days_diff = (today - self.last_checkin).days
            if days_diff == 1:
                self.current_streak += 1
            elif days_diff > 1:
                self.current_streak = 1
            else:
                return  # Already checked in today
        else:
            self.current_streak = 1
        
        self.last_checkin = today
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        self.save()

    class Meta:
        ordering = ['-total_saved']


class MpesaStatement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mpesa_statements')
    pdf_file = models.FileField(upload_to=statement_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    period_months = models.IntegerField(default=1)
    
    # Parsed data
    total_incoming = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_outgoing = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    betting_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    airtime_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    fuliza_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    bars_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    till_withdrawals = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    other_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    parsed_data = models.JSONField(default=dict, blank=True)  # Store raw transaction data

    def __str__(self):
        return f"{self.user.username} - {self.uploaded_at.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-uploaded_at']


class Goal(models.Model):
    CATEGORY_CHOICES = [
        ('plot', 'Plot/Land'),
        ('boda', 'Boda/Motorcycle'),
        ('wedding', 'Wedding'),
        ('house', 'House Construction'),
        ('business', 'Business'),
        ('education', 'Education'),
        ('vehicle', 'Vehicle'),
        ('emergency', 'Emergency Fund'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=200)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    deadline = models.DateField()
    achieved = models.BooleanField(default=False)
    achieved_at = models.DateTimeField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.title}"

    def progress_percentage(self):
        if self.target_amount == 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)

    def projected_finish_date(self):
        """Calculate projected finish date based on average daily savings"""
        if self.achieved:
            return self.achieved_at.date() if self.achieved_at else None
        
        remaining = self.target_amount - self.current_amount
        if remaining <= 0:
            return timezone.now().date()
        
        # Get average daily savings from DailySaving records
        savings = DailySaving.objects.filter(user=self.user, date__gte=self.created_at.date())
        if savings.exists():
            total_days = (timezone.now().date() - self.created_at.date()).days or 1
            avg_daily = self.current_amount / total_days
            if avg_daily > 0:
                days_remaining = (remaining / avg_daily)
                return timezone.now().date() + timezone.timedelta(days=int(days_remaining))
        
        return None

    class Meta:
        ordering = ['-created_at']


class DailySaving(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_savings')
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.date} - KSh {self.amount}"

    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']  # One saving per user per day


class Tribe(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    is_private = models.BooleanField(default=False)
    members = models.ManyToManyField(User, related_name='tribes')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tribes')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class TribePost(models.Model):
    tribe = models.ForeignKey(Tribe, on_delete=models.CASCADE, related_name='posts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tribe_posts')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} in {self.tribe.name}"

    class Meta:
        ordering = ['-created_at']


class Achievement(models.Model):
    """Achievement/Badge definitions"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon_name = models.CharField(max_length=50, help_text="Lucide icon name (e.g., 'trophy', 'star')")
    criteria_type = models.CharField(max_length=50, choices=[
        ('first_goal', 'Create First Goal'),
        ('goal_achieved', 'Achieve a Goal'),
        ('streak_7', '7 Day Streak'),
        ('streak_30', '30 Day Streak'),
        ('streak_100', '100 Day Streak'),
        ('total_saved_1000', 'Save KSh 1,000'),
        ('total_saved_10000', 'Save KSh 10,000'),
        ('total_saved_100000', 'Save KSh 100,000'),
        ('join_tribe', 'Join a Tribe'),
        ('create_tribe', 'Create a Tribe'),
        ('top_saver', 'Top 10 Saver'),
        ('upload_statement', 'Upload M-Pesa Statement'),
    ])
    criteria_value = models.IntegerField(default=1, help_text="Number required (e.g., 7 for 7-day streak)")
    points = models.IntegerField(default=10, help_text="Points awarded for this achievement")
    rarity = models.CharField(max_length=20, choices=[
        ('common', 'Common'),
        ('uncommon', 'Uncommon'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ], default='common')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['points', 'name']


class UserAchievement(models.Model):
    """User's earned achievements"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='user_achievements')
    earned_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.achievement.name}"

    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-earned_at']


class SavingsChallenge(models.Model):
    """Savings challenges users can participate in"""
    CHALLENGE_TYPES = [
        ('monthly', 'Monthly Challenge'),
        ('custom', 'Custom Challenge'),
        ('tribe', 'Tribe Challenge'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    challenge_type = models.CharField(max_length=20, choices=CHALLENGE_TYPES, default='monthly')
    target_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    tribe = models.ForeignKey(Tribe, on_delete=models.CASCADE, null=True, blank=True, related_name='challenges')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_challenges')
    participants = models.ManyToManyField(User, related_name='challenges', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def is_ongoing(self):
        today = timezone.now().date()
        return self.is_active and self.start_date <= today <= self.end_date

    class Meta:
        ordering = ['-created_at']


class ChallengeProgress(models.Model):
    """User's progress in a challenge"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge_progress')
    challenge = models.ForeignKey(SavingsChallenge, on_delete=models.CASCADE, related_name='progress')
    amount_saved = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.challenge.name}"

    def progress_percentage(self):
        if self.challenge.target_amount == 0:
            return 0
        return min(100, (self.amount_saved / self.challenge.target_amount) * 100)

    class Meta:
        unique_together = ['user', 'challenge']
        ordering = ['-amount_saved']


class Notification(models.Model):
    """User notifications"""
    NOTIFICATION_TYPES = [
        ('goal_deadline', 'Goal Deadline Approaching'),
        ('goal_achieved', 'Goal Achieved'),
        ('streak_milestone', 'Streak Milestone'),
        ('achievement_earned', 'Achievement Earned'),
        ('challenge_started', 'Challenge Started'),
        ('challenge_completed', 'Challenge Completed'),
        ('tribe_activity', 'Tribe Activity'),
        ('reminder', 'Reminder'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    related_achievement = models.ForeignKey(UserAchievement, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    related_challenge = models.ForeignKey(SavingsChallenge, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.title}"

    class Meta:
        ordering = ['-created_at']


class Budget(models.Model):
    """Monthly budget planning"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    month = models.DateField(help_text="First day of the month")
    total_budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    savings_target = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.month.strftime('%B %Y')}"

    def get_spent(self):
        """Calculate total spent this month from M-Pesa statements"""
        start_date = self.month
        if start_date.day != 1:
            start_date = start_date.replace(day=1)
        
        # Calculate end date (last day of month)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timezone.timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1, day=1) - timezone.timedelta(days=1)
        
        statements = MpesaStatement.objects.filter(
            user=self.user,
            uploaded_at__date__gte=start_date,
            uploaded_at__date__lte=end_date
        )
        return sum(s.total_outgoing for s in statements)

    def get_saved(self):
        """Calculate total saved this month"""
        start_date = self.month
        if start_date.day != 1:
            start_date = start_date.replace(day=1)
        
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timezone.timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1, day=1) - timezone.timedelta(days=1)
        
        savings = DailySaving.objects.filter(
            user=self.user,
            date__gte=start_date,
            date__lte=end_date
        )
        return sum(s.amount for s in savings)

    def remaining_budget(self):
        return self.total_budget - self.get_spent()

    def budget_percentage(self):
        if self.total_budget == 0:
            return 0
        return min(100, (self.get_spent() / self.total_budget) * 100)

    class Meta:
        unique_together = ['user', 'month']
        ordering = ['-month']


class RecurringSavingsPlan(models.Model):
    """Automatic recurring savings plans"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_plans')
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    linked_goal = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_plans')
    last_executed = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    def should_execute(self):
        """Check if plan should execute today"""
        if not self.is_active:
            return False
        
        today = timezone.now().date()
        
        if today < self.start_date:
            return False
        
        if self.end_date and today > self.end_date:
            return False
        
        if self.last_executed == today:
            return False
        
        if self.frequency == 'daily':
            return True
        elif self.frequency == 'weekly':
            if not self.last_executed:
                return True
            days_since = (today - self.last_executed).days
            return days_since >= 7
        elif self.frequency == 'monthly':
            if not self.last_executed:
                return True
            # Check if it's been at least a month
            return (today.year > self.last_executed.year) or \
                   (today.year == self.last_executed.year and today.month > self.last_executed.month)
        
        return False

    class Meta:
        ordering = ['-created_at']


class GoalTemplate(models.Model):
    """Pre-made goal templates"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    target_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    category = models.CharField(max_length=20, choices=Goal.CATEGORY_CHOICES, default='other')
    suggested_deadline_months = models.IntegerField(default=12, help_text="Suggested months to achieve goal")
    icon_name = models.CharField(max_length=50, default='target', help_text="Lucide icon name")
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-is_featured', 'name']
