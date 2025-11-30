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

from .models import UserProfile, Goal, DailySaving, MpesaStatement, Tribe, TribePost
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm,
    GoalForm, DailySavingForm, MpesaStatementForm, TribeForm, TribePostForm
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
    profile = request.user.userprofile
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
    
    context = {
        'profile': profile,
        'active_goals': active_goals,
        'recent_savings': recent_savings,
        'total_saved': total_saved,
        'checked_in_today': checked_in_today,
        'recent_statement': recent_statement,
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
                
                # Update profile
                request.user.userprofile.total_saved += amount
                request.user.userprofile.update_streak()
                request.user.userprofile.save()
                
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
    
    return render(request, 'core/goal_detail.html', {'goal': goal})


@login_required
def goal_create(request):
    """Create new goal"""
    if request.method == 'POST':
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.title}" created successfully!')
            return redirect('goal_detail', goal_id=goal.id)
    else:
        form = GoalForm()
    
    return render(request, 'core/goal_create.html', {'form': form})


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
            
            # Update profile
            profile = request.user.userprofile
            profile.total_saved += saving.amount
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
        context = {
            'statements': statements,
            'latest': latest,
        }
    else:
        context = {
            'statements': [],
            'latest': None,
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
