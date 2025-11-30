from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, timedelta
import PyPDF2
import re
from decimal import Decimal

from .models import (
    UserProfile, Goal, DailySaving, MpesaStatement, Tribe, TribePost,
    Achievement, UserAchievement, SavingsChallenge, ChallengeProgress, Notification,
    Budget, RecurringSavingsPlan, GoalTemplate
)
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm,
    GoalForm, DailySavingForm, MpesaStatementForm, TribeForm, TribePostForm,
    BudgetForm, RecurringSavingsPlanForm
)


def landing(request):
    """Landing page for non-authenticated users"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/landing.html')


def register_view(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Update phone in profile
            if form.cleaned_data.get('phone'):
                user.userprofile.phone = form.cleaned_data['phone']
                user.userprofile.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to Akiba!')
            return redirect('dashboard')
        else:
            # Form has errors - they'll be displayed in template
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'core/register.html', {'form': form})


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'core/login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')


@login_required
def dashboard(request):
    """Main dashboard"""
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist (safety check)
        profile = UserProfile.objects.create(user=request.user)
    
    today = timezone.now().date()
    
    # Get active goals
    active_goals = Goal.objects.filter(user=request.user, achieved=False).order_by('-created_at')[:5]
    
    # Get recent savings
    recent_savings = DailySaving.objects.filter(user=request.user).order_by('-date')[:5]
    
    # Get total saved from all daily savings
    total_saved = DailySaving.objects.filter(user=request.user).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Update profile total_saved
    profile.total_saved = total_saved
    profile.save()
    
    # Check if user has checked in today
    checked_in_today = DailySaving.objects.filter(user=request.user, date=today).exists()
    
    # Get recent M-Pesa insights
    recent_statement = MpesaStatement.objects.filter(user=request.user).first()
    
    # Get recent achievements
    recent_achievements = UserAchievement.objects.filter(user=request.user).order_by('-earned_at')[:5]
    total_achievements = UserAchievement.objects.filter(user=request.user).count()
    
    # Get active challenges
    active_challenges = SavingsChallenge.objects.filter(
        is_active=True,
        start_date__lte=today,
        end_date__gte=today
    ).filter(
        Q(participants=request.user) | Q(challenge_type='monthly')
    ).distinct()[:3]
    
    # Get unread notifications
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')[:5]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    # Check all achievements
    from .achievements import check_all_achievements
    check_all_achievements(request.user)
    
    context = {
        'profile': profile,
        'active_goals': active_goals,
        'recent_savings': recent_savings,
        'total_saved': total_saved,
        'checked_in_today': checked_in_today,
        'recent_statement': recent_statement,
        'recent_achievements': recent_achievements,
        'total_achievements': total_achievements,
        'active_challenges': active_challenges,
        'unread_notifications': unread_notifications,
        'unread_count': unread_count,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def profile_view(request):
    """User profile page"""
    profile = request.user.userprofile
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'core/profile.html', {'form': form, 'profile': profile})


@login_required
def goals_list(request):
    """List all goals"""
    goals = Goal.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/goals_list.html', {'goals': goals})


@login_required
def goal_detail(request, goal_id):
    """Goal detail page"""
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    
    if request.method == 'POST':
        if 'check_in' in request.POST:
            # Daily check-in
            today = timezone.now().date()
            saving, created = DailySaving.objects.get_or_create(
                user=request.user,
                date=today,
                defaults={'amount': Decimal('0.00')}
            )
            if created:
                request.user.userprofile.update_streak()
                messages.success(request, 'Check-in successful! Keep the streak going!')
            else:
                messages.info(request, 'You have already checked in today.')
            return redirect('goal_detail', goal_id=goal_id)
        
        elif 'add_amount' in request.POST:
            amount = Decimal(request.POST.get('amount', 0))
            if amount > 0:
                goal.current_amount += amount
                goal.save()
                
                # Also create/update daily saving
                today = timezone.now().date()
                saving, created = DailySaving.objects.get_or_create(
                    user=request.user,
                    date=today,
                    defaults={'amount': amount}
                )
                if not created:
                    saving.amount += amount
                    saving.save()
                
                # Update profile total_saved (recalculate from all daily savings)
                total_saved = DailySaving.objects.filter(user=request.user).aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0.00')
                request.user.userprofile.total_saved = total_saved
                request.user.userprofile.update_streak()
                request.user.userprofile.save()
                
                # Update challenge progress
                today = timezone.now().date()
                active_challenges = SavingsChallenge.objects.filter(
                    is_active=True,
                    start_date__lte=today,
                    end_date__gte=today,
                    participants=request.user
                )
                for challenge in active_challenges:
                    progress, _ = ChallengeProgress.objects.get_or_create(
                        user=request.user,
                        challenge=challenge
                    )
                    # Add amount to challenge progress
                    progress.amount_saved += amount
                    if progress.amount_saved >= challenge.target_amount and not progress.completed:
                        progress.completed = True
                        progress.completed_at = timezone.now()
                        Notification.objects.create(
                            user=request.user,
                            notification_type='challenge_completed',
                            title=f'Challenge Completed: {challenge.name}',
                            message=f'Congratulations! You\'ve completed the "{challenge.name}" challenge!',
                            related_challenge=challenge
                        )
                    progress.save()
                
                # Check if goal achieved
                if goal.current_amount >= goal.target_amount and not goal.achieved:
                    goal.achieved = True
                    goal.achieved_at = timezone.now()
                    goal.save()
                    messages.success(request, f'🎉 Goal "{goal.title}" achieved! Congratulations!')
                else:
                    messages.success(request, f'Added KSh {amount} to goal "{goal.title}"')
                
                return redirect('goal_detail', goal_id=goal_id)
        
        elif 'mark_achieved' in request.POST:
            goal.achieved = True
            goal.achieved_at = timezone.now()
            goal.save()
            messages.success(request, f'Goal "{goal.title}" marked as achieved!')
            return redirect('goal_detail', goal_id=goal_id)
    
    remaining = goal.target_amount - goal.current_amount
    projected_date = goal.projected_finish_date()
    return render(request, 'core/goal_detail.html', {
        'goal': goal,
        'remaining': max(Decimal('0.00'), remaining),
        'projected_date': projected_date
    })


@login_required
def goal_create(request):
    """Create new goal"""
    if request.method == 'POST':
        form = GoalForm(request.POST)
        if form.is_valid():
            # Validate deadline is in the future
            deadline = form.cleaned_data['deadline']
            if deadline <= timezone.now().date():
                form.add_error('deadline', 'Deadline must be in the future.')
                return render(request, 'core/goal_create.html', {
                    'form': form,
                    'today': timezone.now().date()
                })
            
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.title}" created successfully!')
            return redirect('goal_detail', goal_id=goal.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = GoalForm()
    
    return render(request, 'core/goal_create.html', {
        'form': form,
        'today': timezone.now().date()
    })


@login_required
def daily_saving_log(request):
    """Daily saving log and check-in"""
    if request.method == 'POST':
        form = DailySavingForm(request.POST)
        if form.is_valid():
            saving = form.save(commit=False)
            saving.user = request.user
            saving.date = timezone.now().date()
            
            # Check if already saved today
            existing = DailySaving.objects.filter(user=request.user, date=saving.date).first()
            if existing:
                existing.amount += saving.amount
                existing.note = saving.note or existing.note
                existing.save()
                saving = existing
            else:
                saving.save()
            
            # Update profile total_saved (recalculate from all daily savings)
            profile = request.user.userprofile
            total_saved = DailySaving.objects.filter(user=request.user).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            profile.total_saved = total_saved
            profile.update_streak()
            profile.save()
            
            messages.success(request, f'Saved KSh {saving.amount} today! Streak: {profile.current_streak} days')
            return redirect('daily_saving_log')
    else:
        form = DailySavingForm()
    
    # Get all savings
    savings = DailySaving.objects.filter(user=request.user).order_by('-date')
    profile = request.user.userprofile
    
    return render(request, 'core/daily_saving_log.html', {
        'form': form,
        'savings': savings,
        'profile': profile,
    })


def parse_mpesa_pdf(pdf_file):
    """Parse M-Pesa PDF statement and extract transactions"""
    transactions = []
    betting_keywords = ['bet', 'sportpesa', 'betway', 'betika', 'odds', 'gaming']
    airtime_keywords = ['airtime', 'top up']
    fuliza_keywords = ['fuliza', 'm-shwari']
    bar_keywords = ['bar', 'pub', 'club', 'restaurant', 'hotel']
    till_keywords = ['till', 'paybill']
    
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        # Extract transactions using regex
        # M-Pesa statements typically have date, description, amount patterns
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        amount_pattern = r'([\d,]+\.\d{2})'
        
        lines = text.split('\n')
        current_transaction = {}
        
        for line in lines:
            # Look for dates
            date_match = re.search(date_pattern, line)
            if date_match:
                if current_transaction:
                    transactions.append(current_transaction)
                current_transaction = {'date': date_match.group(1)}
            
            # Look for amounts
            amount_matches = re.findall(amount_pattern, line.replace(',', ''))
            if amount_matches and current_transaction:
                try:
                    amount = Decimal(amount_matches[-1])
                    if 'amount' not in current_transaction:
                        current_transaction['amount'] = amount
                except:
                    pass
            
            # Look for descriptions
            if current_transaction and 'description' not in current_transaction:
                desc = line.strip()
                if desc and not re.match(r'^[\d,]+\.\d{2}$', desc):
                    current_transaction['description'] = desc.lower()
        
        if current_transaction:
            transactions.append(current_transaction)
        
        # Categorize transactions
        categorized = {
            'betting': Decimal('0.00'),
            'airtime': Decimal('0.00'),
            'fuliza': Decimal('0.00'),
            'bars': Decimal('0.00'),
            'till_withdrawals': Decimal('0.00'),
            'other': Decimal('0.00'),
            'incoming': Decimal('0.00'),
        }
        
        for trans in transactions:
            desc = trans.get('description', '')
            amount = trans.get('amount', Decimal('0.00'))
            
            if any(kw in desc for kw in betting_keywords):
                categorized['betting'] += abs(amount)
            elif any(kw in desc for kw in airtime_keywords):
                categorized['airtime'] += abs(amount)
            elif any(kw in desc for kw in fuliza_keywords):
                categorized['fuliza'] += abs(amount)
            elif any(kw in desc for kw in bar_keywords):
                categorized['bars'] += abs(amount)
            elif any(kw in desc for kw in till_keywords):
                categorized['till_withdrawals'] += abs(amount)
            elif amount > 0:
                categorized['incoming'] += amount
            else:
                categorized['other'] += abs(amount)
        
        return {
            'transactions': transactions,
            'categorized': categorized,
            'total_incoming': categorized['incoming'],
            'total_outgoing': categorized['betting'] + categorized['airtime'] + categorized['fuliza'] + categorized['bars'] + categorized['till_withdrawals'] + categorized['other'],
        }
    
    except Exception as e:
        return {'error': str(e)}


@login_required
def upload_statement(request):
    """Upload and parse M-Pesa statement"""
    if request.method == 'POST':
        form = MpesaStatementForm(request.POST, request.FILES)
        if form.is_valid():
            statement = form.save(commit=False)
            statement.user = request.user
            
            # Parse PDF
            pdf_file = request.FILES['pdf_file']
            pdf_file.seek(0)  # Reset file pointer
            parsed = parse_mpesa_pdf(pdf_file)
            
            if 'error' in parsed:
                messages.error(request, f'Error parsing PDF: {parsed["error"]}')
                return render(request, 'core/upload_statement.html', {'form': form})
            
            # Save parsed data
            statement.parsed_data = parsed
            statement.total_incoming = parsed.get('total_incoming', Decimal('0.00'))
            statement.total_outgoing = parsed.get('total_outgoing', Decimal('0.00'))
            statement.betting_spent = parsed['categorized'].get('betting', Decimal('0.00'))
            statement.airtime_spent = parsed['categorized'].get('airtime', Decimal('0.00'))
            statement.fuliza_spent = parsed['categorized'].get('fuliza', Decimal('0.00'))
            statement.bars_spent = parsed['categorized'].get('bars', Decimal('0.00'))
            statement.till_withdrawals = parsed['categorized'].get('till_withdrawals', Decimal('0.00'))
            statement.other_spent = parsed['categorized'].get('other', Decimal('0.00'))
            
            statement.save()
            messages.success(request, 'M-Pesa statement uploaded and analyzed successfully!')
            return redirect('insights')
    else:
        form = MpesaStatementForm()
    
    return render(request, 'core/upload_statement.html', {'form': form})


@login_required
def insights(request):
    """Spending insights page"""
    statements = MpesaStatement.objects.filter(user=request.user).order_by('-uploaded_at')
    
    if statements.exists():
        latest = statements.first()
        net_amount = latest.total_incoming - latest.total_outgoing
        context = {
            'statements': statements,
            'latest': latest,
            'net_amount': net_amount,
        }
    else:
        context = {
            'statements': [],
            'latest': None,
            'net_amount': Decimal('0.00'),
        }
    
    return render(request, 'core/insights.html', context)


@login_required
def tribes_list(request):
    """List all tribes"""
    tribes = Tribe.objects.filter(is_private=False).annotate(
        member_count=Count('members')
    ).order_by('-created_at')
    
    user_tribes = request.user.tribes.all()
    
    return render(request, 'core/tribes_list.html', {
        'tribes': tribes,
        'user_tribes': user_tribes,
    })


@login_required
def tribe_detail(request, tribe_id):
    """Tribe detail page with posts"""
    tribe = get_object_or_404(Tribe, id=tribe_id)
    is_member = request.user in tribe.members.all()
    
    if request.method == 'POST':
        if 'join' in request.POST:
            tribe.members.add(request.user)
            messages.success(request, f'Joined {tribe.name}!')
            return redirect('tribe_detail', tribe_id=tribe_id)
        
        elif 'leave' in request.POST:
            tribe.members.remove(request.user)
            messages.info(request, f'Left {tribe.name}')
            return redirect('tribes')
        
        elif 'post' in request.POST:
            form = TribePostForm(request.POST)
            if form.is_valid() and is_member:
                post = form.save(commit=False)
                post.tribe = tribe
                post.user = request.user
                post.save()
                messages.success(request, 'Post shared!')
                return redirect('tribe_detail', tribe_id=tribe_id)
    
    posts = TribePost.objects.filter(tribe=tribe).order_by('-created_at')[:20]
    members = tribe.members.all()
    
    # Get leaderboard for tribe members
    member_profiles = UserProfile.objects.filter(user__in=members).order_by('-total_saved')[:10]
    
    post_form = TribePostForm() if is_member else None
    
    return render(request, 'core/tribe_detail.html', {
        'tribe': tribe,
        'is_member': is_member,
        'posts': posts,
        'members': members,
        'member_profiles': member_profiles,
        'post_form': post_form,
    })


@login_required
def tribe_create(request):
    """Create new tribe"""
    if request.method == 'POST':
        form = TribeForm(request.POST)
        if form.is_valid():
            tribe = form.save(commit=False)
            tribe.created_by = request.user
            tribe.save()
            tribe.members.add(request.user)
            messages.success(request, f'Tribe "{tribe.name}" created!')
            return redirect('tribe_detail', tribe_id=tribe.id)
    else:
        form = TribeForm()
    
    return render(request, 'core/tribe_create.html', {'form': form})


@login_required
def leaderboard(request):
    """National and tribe leaderboards"""
    # National leaderboard
    national_top = UserProfile.objects.all().order_by('-total_saved')[:20]
    
    # Streak leaders
    streak_leaders = UserProfile.objects.filter(current_streak__gt=0).order_by('-current_streak')[:20]
    
    # Goal achievers (fastest)
    fastest_achievers = Goal.objects.filter(achieved=True).order_by('achieved_at')[:20]
    
    # User's tribes
    user_tribes = request.user.tribes.all()
    tribe_leaderboards = {}
    for tribe in user_tribes:
        tribe_leaderboards[tribe] = UserProfile.objects.filter(
            user__in=tribe.members.all()
        ).order_by('-total_saved')[:10]
    
    return render(request, 'core/leaderboard.html', {
        'national_top': national_top,
        'streak_leaders': streak_leaders,
        'fastest_achievers': fastest_achievers,
        'tribe_leaderboards': tribe_leaderboards,
    })


@login_required
def achievements_view(request):
    """User achievements page"""
    user_achievements = UserAchievement.objects.filter(user=request.user).order_by('-earned_at')
    all_achievements = Achievement.objects.all().order_by('points', 'name')
    
    # Get earned achievement IDs
    earned_ids = set(user_achievements.values_list('achievement_id', flat=True))
    
    # Separate earned and unearned
    earned = [ua.achievement for ua in user_achievements]
    unearned = [a for a in all_achievements if a.id not in earned_ids]
    
    # Calculate stats
    total_points = sum(ua.achievement.points for ua in user_achievements)
    completion_rate = (len(earned) / len(all_achievements) * 100) if all_achievements.exists() else 0
    
    return render(request, 'core/achievements.html', {
        'earned_achievements': earned,
        'unearned_achievements': unearned,
        'total_points': total_points,
        'completion_rate': completion_rate,
        'total_count': len(earned),
    })


@login_required
def challenges_view(request):
    """Savings challenges page"""
    today = timezone.now().date()
    
    # Get all active challenges
    active_challenges = SavingsChallenge.objects.filter(
        is_active=True,
        start_date__lte=today,
        end_date__gte=today
    ).order_by('-created_at')
    
    # Get user's challenge progress
    user_progress = ChallengeProgress.objects.filter(user=request.user).select_related('challenge')
    
    # Get completed challenges
    completed_challenges = SavingsChallenge.objects.filter(
        is_active=True,
        end_date__lt=today
    ).order_by('-end_date')[:10]
    
    return render(request, 'core/challenges.html', {
        'active_challenges': active_challenges,
        'user_progress': user_progress,
        'completed_challenges': completed_challenges,
    })


@login_required
def challenge_detail(request, challenge_id):
    """Challenge detail page"""
    challenge = get_object_or_404(SavingsChallenge, id=challenge_id)
    progress, created = ChallengeProgress.objects.get_or_create(
        user=request.user,
        challenge=challenge
    )
    
    # Get all participants and their progress
    participants = challenge.participants.all()
    all_progress = ChallengeProgress.objects.filter(challenge=challenge).order_by('-amount_saved')
    
    is_participant = request.user in participants
    
    if request.method == 'POST' and 'join' in request.POST:
        if not is_participant:
            challenge.participants.add(request.user)
            progress, _ = ChallengeProgress.objects.get_or_create(
                user=request.user,
                challenge=challenge
            )
            messages.success(request, f'Joined challenge: {challenge.name}')
            return redirect('challenge_detail', challenge_id=challenge_id)
    
    return render(request, 'core/challenge_detail.html', {
        'challenge': challenge,
        'progress': progress,
        'is_participant': is_participant,
        'all_progress': all_progress,
    })


@login_required
def notifications_view(request):
    """User notifications page"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Mark all as read
    if request.method == 'POST' and 'mark_all_read' in request.POST:
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, 'All notifications marked as read')
        return redirect('notifications')
    
    return render(request, 'core/notifications.html', {
        'notifications': notifications,
    })


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications')


@login_required
def budget_view(request):
    """Budget planning page"""
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    # Get or create current month budget
    budget, created = Budget.objects.get_or_create(
        user=request.user,
        month=current_month,
        defaults={'total_budget': Decimal('0.00'), 'savings_target': Decimal('0.00')}
    )
    
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, 'Budget updated successfully!')
            return redirect('budget')
    else:
        form = BudgetForm(instance=budget)
    
    # Get all budgets
    budgets = Budget.objects.filter(user=request.user).order_by('-month')[:12]
    
    return render(request, 'core/budget.html', {
        'budget': budget,
        'form': form,
        'budgets': budgets,
        'current_month': current_month,
    })


@login_required
def analytics_view(request):
    """Savings analytics and reports"""
    today = timezone.now().date()
    
    # Get savings data for last 12 months
    months_data = []
    for i in range(11, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=30*i)).replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        
        savings = DailySaving.objects.filter(
            user=request.user,
            date__gte=month_start,
            date__lte=month_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        months_data.append({
            'month': month_start.strftime('%b %Y'),
            'amount': float(savings),
        })
    
    # Calculate trends
    if len(months_data) >= 2:
        recent_avg = sum(m['amount'] for m in months_data[-3:]) / 3
        previous_avg = sum(m['amount'] for m in months_data[-6:-3]) / 3 if len(months_data) >= 6 else months_data[0]['amount']
        trend = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
    else:
        trend = 0
    
    # Get total saved
    total_saved = DailySaving.objects.filter(user=request.user).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Get savings velocity (average per day)
    first_saving = DailySaving.objects.filter(user=request.user).order_by('date').first()
    if first_saving:
        days_active = (today - first_saving.date).days or 1
        velocity = float(total_saved) / days_active
    else:
        velocity = 0
    
    # Get goal progress
    active_goals = Goal.objects.filter(user=request.user, achieved=False)
    total_goal_target = sum(g.target_amount for g in active_goals)
    total_goal_current = sum(g.current_amount for g in active_goals)
    
    return render(request, 'core/analytics.html', {
        'months_data': months_data,
        'trend': trend,
        'total_saved': total_saved,
        'velocity': velocity,
        'total_goal_target': total_goal_target,
        'total_goal_current': total_goal_current,
    })


@login_required
def recurring_plans_view(request):
    """Recurring savings plans page"""
    plans = RecurringSavingsPlan.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        if 'create' in request.POST:
            form = RecurringSavingsPlanForm(request.POST, user=request.user)
            if form.is_valid():
                plan = form.save(commit=False)
                plan.user = request.user
                plan.save()
                messages.success(request, f'Recurring plan "{plan.name}" created!')
                return redirect('recurring_plans')
        elif 'toggle' in request.POST:
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(RecurringSavingsPlan, id=plan_id, user=request.user)
            plan.is_active = not plan.is_active
            plan.save()
            messages.success(request, f'Plan {"activated" if plan.is_active else "deactivated"}!')
            return redirect('recurring_plans')
        elif 'delete' in request.POST:
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(RecurringSavingsPlan, id=plan_id, user=request.user)
            plan.delete()
            messages.success(request, 'Plan deleted!')
            return redirect('recurring_plans')
    else:
        form = RecurringSavingsPlanForm(user=request.user)
    
    return render(request, 'core/recurring_plans.html', {
        'plans': plans,
        'form': form,
    })


@login_required
def savings_calculator(request):
    """Savings calculator tool"""
    result = None
    monthly_savings = None
    
    if request.method == 'POST':
        target_amount = Decimal(request.POST.get('target_amount', 0))
        current_amount = Decimal(request.POST.get('current_amount', 0))
        monthly_savings = Decimal(request.POST.get('monthly_savings', 0))
        deadline = request.POST.get('deadline')
        
        if target_amount > 0 and monthly_savings > 0:
            remaining = target_amount - current_amount
            if remaining > 0:
                months_needed = (remaining / monthly_savings)
                result = {
                    'months': months_needed,
                    'days': months_needed * 30,
                    'weekly_savings': monthly_savings / 4,
                    'daily_savings': monthly_savings / 30,
                }
    
    return render(request, 'core/calculator.html', {
        'result': result,
        'monthly_savings': monthly_savings
    })


@login_required
def goal_templates_view(request):
    """Goal templates page"""
    templates = GoalTemplate.objects.all().order_by('-is_featured', 'name')
    featured = templates.filter(is_featured=True)
    regular = templates.filter(is_featured=False)
    
    return render(request, 'core/goal_templates.html', {
        'featured_templates': featured,
        'regular_templates': regular,
    })


@login_required
def create_goal_from_template(request, template_id):
    """Create a goal from a template"""
    template = get_object_or_404(GoalTemplate, id=template_id)
    
    if request.method == 'POST':
        # Calculate deadline based on suggested months
        from datetime import datetime
        deadline = timezone.now().date() + timedelta(days=template.suggested_deadline_months * 30)
        
        goal = Goal.objects.create(
            user=request.user,
            title=template.name,
            target_amount=template.target_amount,
            deadline=deadline,
            category=template.category
        )
        
        messages.success(request, f'Goal "{goal.title}" created from template!')
        return redirect('goal_detail', goal_id=goal.id)
    
    return render(request, 'core/create_from_template.html', {
        'template': template,
        'suggested_deadline': timezone.now().date() + timedelta(days=template.suggested_deadline_months * 30),
    })
