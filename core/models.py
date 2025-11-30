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
