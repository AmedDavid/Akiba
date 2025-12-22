from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta, date
import PyPDF2
import re
import os
from decimal import Decimal

# Try to import QR code scanning libraries (optional)
# Note: pyzbar requires ZBar DLLs on Windows - if not available, QR scanning will be disabled
try:
    from pyzbar import pyzbar
    from pdf2image import convert_from_path
    QR_CODE_AVAILABLE = True
except (ImportError, FileNotFoundError, OSError) as e:
    # FileNotFoundError occurs on Windows when ZBar DLLs are missing
    # OSError can also occur when DLLs can't be loaded
    QR_CODE_AVAILABLE = False
    pyzbar = None
    convert_from_path = None

def convert_decimals_to_strings(obj):
    """Recursively convert Decimal and date values to strings for JSON serialization"""
    if isinstance(obj, Decimal):
        return str(obj)
    elif isinstance(obj, (datetime, date)):
        # Convert date/datetime to ISO format string
        if isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_decimals_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals_to_strings(item) for item in obj]
    else:
        return obj

from .models import (
    UserProfile, Goal, DailySaving, MpesaStatement, Tribe, TribePost,
    Achievement, UserAchievement, SavingsChallenge, ChallengeProgress, Notification,
    Budget, RecurringSavingsPlan, GoalTemplate, Subscription, Payment
)
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm,
    GoalForm, DailySavingForm, MpesaStatementForm, TribeForm, TribePostForm,
    BudgetForm, RecurringSavingsPlanForm
)
from .subscription_utils import is_pro_user, check_feature_access, get_feature_limit
from .payments import (
    initiate_mpesa_stk_push, create_stripe_checkout_session,
    handle_mpesa_callback, handle_stripe_webhook, PRO_MONTHLY_PRICE
)
import json


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
    
    # Check subscription status
    is_pro = is_pro_user(request.user)
    
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
        'is_pro': is_pro,
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
    # Check goal limit for free users
    has_access, error_msg = check_feature_access(request.user, 'goals')
    if not has_access:
        messages.warning(request, error_msg)
        return redirect('pricing')
    
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


def parse_mpesa_pdf(pdf_file, password=None):
    """Parse M-Pesa PDF statement and extract transactions"""
    transactions = []
    period_start = None
    period_end = None
    was_encrypted = False
    betting_keywords = ['bet', 'sportpesa', 'betway', 'betika', 'odds', 'gaming']
    airtime_keywords = ['airtime', 'top up', 'bundle purchase', 'customer bundle']
    fuliza_loan_keywords = ['overdraft of credit', 'over draw', 'od loan', 'fuliza loan', 'overdraft']  # Actual Fuliza credit usage
    fuliza_repayment_keywords = ['od loan repayment', 'fuliza repayment', 'loan repayment to 232323']  # Repaying Fuliza
    mshwari_deposit_keywords = ['m-shwari deposit', 'mshwari deposit', 'm-shwari']  # Saving to M-Shwari (check for deposit context)
    mshwari_withdraw_keywords = ['m-shwari withdraw', 'mshwari withdraw', 'm-shwari']  # Withdrawing from M-Shwari
    bar_keywords = ['bar', 'pub', 'club', 'restaurant', 'hotel']
    till_keywords = ['till', 'paybill', 'merchant payment']
    
    try:
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
        except Exception as e:
            # PyPDF2 might throw an exception for encrypted PDFs
            error_str = str(e).lower()
            if 'encrypted' in error_str or 'password' in error_str:
                if password:
                    # Try again with password
                    pdf_file.seek(0)
                    try:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        if pdf_reader.is_encrypted:
                            was_encrypted = True
                            if not pdf_reader.decrypt(password):
                                return {'error': 'PDF is encrypted and the provided password is incorrect.', 'encrypted': True, 'wrong_password': True}
                    except:
                        return {'error': 'PDF is encrypted and the provided password is incorrect.', 'encrypted': True, 'wrong_password': True}
                else:
                    return {'error': 'PDF is encrypted. Please provide the password.', 'encrypted': True}
            else:
                return {'error': f'Error reading PDF: {str(e)}'}
        
        if pdf_reader.is_encrypted:
            if password:
                try:
                    was_encrypted = True
                    if not pdf_reader.decrypt(password):
                        return {'error': 'PDF is encrypted and the provided password is incorrect.', 'encrypted': True, 'wrong_password': True}
                except Exception as e:
                    return {'error': f'PDF is encrypted and the provided password is incorrect: {str(e)}', 'encrypted': True, 'wrong_password': True}
            else:
                return {'error': 'PDF is encrypted. Please provide the password.', 'encrypted': True}

        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        # Try to extract data from QR code first (more accurate)
        qr_data = None
        # Skip QR scanning for encrypted PDFs to avoid poppler/password issues
        if QR_CODE_AVAILABLE and not was_encrypted:
            try:
                # For uploaded files, we need to save temporarily or use bytes
                # Try to get file path first
                pdf_path = None
                if hasattr(pdf_file, 'temporary_file_path'):
                    # File is already on disk
                    pdf_path = pdf_file.temporary_file_path()
                elif hasattr(pdf_file, 'name') and os.path.exists(pdf_file.name):
                    pdf_path = pdf_file.name
                else:
                    # Save to temporary file
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        pdf_file.seek(0)
                        tmp_file.write(pdf_file.read())
                        pdf_path = tmp_file.name
                
                if pdf_path and convert_from_path and pyzbar:
                    # Convert PDF to images and scan for QR codes
                    images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=200)
                    if images:
                        qr_results = pyzbar.decode(images[0])
                        if qr_results:
                            qr_data = qr_results[0].data.decode('utf-8')
                            # QR code data can contain transaction info - parse if needed
                    
                    # Clean up temporary file if we created it
                    if not (hasattr(pdf_file, 'temporary_file_path') or (hasattr(pdf_file, 'name') and os.path.exists(pdf_file.name))):
                        try:
                            os.unlink(pdf_path)
                        except:
                            pass
            except Exception as e:
                # QR code scanning failed, fall back to text parsing
                qr_data = None
        
        # Extract statement period from header (e.g., "10 Sep 2025 - 10 Dec 2025")
        # Look for date range patterns in the text
        period_patterns = [
            r'(\d{1,2}\s+\w+\s+\d{4})\s*-\s*(\d{1,2}\s+\w+\s+\d{4})',  # "10 Sep 2025 - 10 Dec 2025"
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*-\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',  # "10/09/2025 - 10/12/2025"
            r'statement period[:\s]+(\d{1,2}\s+\w+\s+\d{4})\s*-\s*(\d{1,2}\s+\w+\s+\d{4})',  # "Statement Period: 10 Sep 2025 - 10 Dec 2025"
        ]
        
        for pattern in period_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    from dateutil import parser as date_parser
                    period_start_str = match.group(1).strip()
                    period_end_str = match.group(2).strip()
                    period_start = date_parser.parse(period_start_str).date()
                    period_end = date_parser.parse(period_end_str).date()
                    break
                except:
                    continue
        
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
            'fuliza': Decimal('0.00'),  # Only actual Fuliza loans and repayments
            'bars': Decimal('0.00'),
            'till_withdrawals': Decimal('0.00'),
            'other': Decimal('0.00'),
            'incoming': Decimal('0.00'),
            'mshwari_savings': Decimal('0.00'),  # Track M-Shwari deposits (savings)
        }
        
        for trans in transactions:
            desc = trans.get('description', '')
            amount = trans.get('amount', Decimal('0.00'))
            abs_amount = abs(amount)
            
            # M-Shwari deposits (savings - not spending, but track separately)
            # Check for "deposit" keyword specifically to distinguish from withdrawals
            if any(kw in desc for kw in mshwari_deposit_keywords) and 'deposit' in desc:
                categorized['mshwari_savings'] += abs_amount
                # This is money being saved, not spent, so don't count as outgoing
                # The money was already counted as incoming when received
            # M-Shwari withdrawals (money coming back to M-Pesa - not spending)
            elif any(kw in desc for kw in mshwari_withdraw_keywords) and ('withdraw' in desc or 'withdrawal' in desc):
                # This is money being moved back to M-Pesa, count as incoming
                if amount > 0:
                    categorized['incoming'] += amount
            # Fuliza loan repayments (actual spending to pay back credit)
            elif any(kw in desc for kw in fuliza_repayment_keywords):
                categorized['fuliza'] += abs_amount
            # Fuliza loans (actual credit usage - spending)
            # Check for "overdraft of credit" or similar patterns
            elif any(kw in desc for kw in fuliza_loan_keywords):
                # Only count if it's an actual loan (not a repayment)
                if 'repayment' not in desc and ('overdraft of credit' in desc or 'over draw' in desc):
                    categorized['fuliza'] += abs_amount
            # Betting
            elif any(kw in desc for kw in betting_keywords):
                categorized['betting'] += abs_amount
            # Airtime/Bundles
            elif any(kw in desc for kw in airtime_keywords):
                categorized['airtime'] += abs_amount
            # Bars/Restaurants
            elif any(kw in desc for kw in bar_keywords):
                categorized['bars'] += abs_amount
            # Till/Paybill
            elif any(kw in desc for kw in till_keywords):
                categorized['till_withdrawals'] += abs_amount
            # Other transactions
            elif amount > 0:
                # Positive amounts are incoming (unless they're specific spending types)
                categorized['incoming'] += amount
            else:
                # Negative amounts are outgoing spending
                categorized['other'] += abs_amount
        
        return {
            'transactions': transactions,
            'categorized': categorized,
            'total_incoming': categorized['incoming'],
            'total_outgoing': categorized['betting'] + categorized['airtime'] + categorized['fuliza'] + categorized['bars'] + categorized['till_withdrawals'] + categorized['other'],
            'period_start': period_start,
            'period_end': period_end,
        }
    
    except Exception as e:
        return {'error': str(e)}


@login_required
def upload_statement(request):
    """Upload and parse M-Pesa statement (supports encrypted PDFs via fetch + modal)"""
    is_fetch = request.headers.get('X-Requested-With') == 'fetch'
    if request.method == 'POST':
        # Check if file is present
        if 'pdf_file' not in request.FILES:
            if is_fetch:
                return JsonResponse({'ok': False, 'message': 'No PDF file provided.'}, status=400)
            messages.error(request, 'No PDF file provided.')
            form = MpesaStatementForm()
            return render(request, 'core/upload_statement.html', {'form': form})
        
        form = MpesaStatementForm(request.POST, request.FILES)
        if form.is_valid():
            statement = form.save(commit=False)
            statement.user = request.user
            
            # Parse PDF
            pdf_file = request.FILES['pdf_file']
            pdf_password = request.POST.get('pdf_password') or None
            pdf_file.seek(0)  # Reset file pointer
            parsed = parse_mpesa_pdf(pdf_file, password=pdf_password)
            
            if 'error' in parsed:
                error_msg = parsed['error']
                is_encrypted = parsed.get('encrypted', False)
                wrong_password = parsed.get('wrong_password', False)
                
                if is_fetch:
                    if is_encrypted:
                        return JsonResponse({
                            'ok': False, 
                            'needs_password': True, 
                            'wrong_password': wrong_password,
                            'message': error_msg
                        }, status=400)
                    return JsonResponse({'ok': False, 'message': error_msg}, status=400)
                
                messages.error(request, f'Error parsing PDF: {error_msg}')
                return render(request, 'core/upload_statement.html', {'form': form})
            
            # Convert Decimal values to strings for JSON serialization
            parsed_json_safe = convert_decimals_to_strings(parsed)
            
            # Save parsed data
            statement.parsed_data = parsed_json_safe
            statement.total_incoming = parsed.get('total_incoming', Decimal('0.00'))
            statement.total_outgoing = parsed.get('total_outgoing', Decimal('0.00'))
            statement.betting_spent = parsed['categorized'].get('betting', Decimal('0.00'))
            statement.airtime_spent = parsed['categorized'].get('airtime', Decimal('0.00'))
            statement.fuliza_spent = parsed['categorized'].get('fuliza', Decimal('0.00'))
            statement.bars_spent = parsed['categorized'].get('bars', Decimal('0.00'))
            statement.till_withdrawals = parsed['categorized'].get('till_withdrawals', Decimal('0.00'))
            statement.other_spent = parsed['categorized'].get('other', Decimal('0.00'))
            
            # Save period dates if extracted
            if parsed.get('period_start'):
                statement.period_start = parsed['period_start']
            if parsed.get('period_end'):
                statement.period_end = parsed['period_end']
            
            # Calculate period_months if dates are available
            if statement.period_start and statement.period_end:
                from dateutil.relativedelta import relativedelta
                delta = relativedelta(statement.period_end, statement.period_start)
                statement.period_months = delta.months + (delta.years * 12) + (1 if delta.days > 0 else 0)
            
            statement.save()
            if is_fetch:
                return JsonResponse({'ok': True, 'redirect': reverse('insights')})
            messages.success(request, 'M-Pesa statement uploaded and analyzed successfully!')
            return redirect('insights')
        else:
            if is_fetch:
                # Return form errors for debugging
                errors = {}
                for field, field_errors in form.errors.items():
                    errors[field] = list(field_errors)
                error_message = 'Invalid form data. Please check the file and try again.'
                if errors:
                    error_message = f'Form validation failed: {", ".join([f"{k}: {v[0]}" for k, v in errors.items()])}'
                return JsonResponse({
                    'ok': False, 
                    'message': error_message,
                    'errors': errors
                }, status=400)
    else:
        form = MpesaStatementForm()
    
    return render(request, 'core/upload_statement.html', {'form': form})


@login_required
def delete_statement(request, statement_id):
    """Delete an M-Pesa statement"""
    statement = get_object_or_404(MpesaStatement, id=statement_id, user=request.user)
    
    if request.method == 'POST':
        # Delete the PDF file from storage before deleting the model instance
        if statement.pdf_file:
            try:
                statement.pdf_file.delete(save=False)
            except Exception as e:
                # Log error but continue with deletion
                print(f"Error deleting PDF file: {e}")
        
        # Delete the model instance (this will also trigger file deletion if not done above)
        statement.delete()
        messages.success(request, 'M-Pesa statement deleted successfully!')
        return redirect('insights')
    
    return redirect('insights')


@login_required
def insights(request):
    """Spending insights page"""
    statements = MpesaStatement.objects.filter(user=request.user).order_by('-uploaded_at')
    
    if statements.exists():
        latest = statements.first()
        net_amount = latest.total_incoming - latest.total_outgoing
        
        # Calculate percentages for each category
        total_spending = latest.total_outgoing
        if total_spending > 0:
            category_percentages = {
                'betting': (latest.betting_spent / total_spending * 100) if latest.betting_spent > 0 else 0,
                'airtime': (latest.airtime_spent / total_spending * 100) if latest.airtime_spent > 0 else 0,
                'fuliza': (latest.fuliza_spent / total_spending * 100) if latest.fuliza_spent > 0 else 0,
                'bars': (latest.bars_spent / total_spending * 100) if latest.bars_spent > 0 else 0,
                'till_withdrawals': (latest.till_withdrawals / total_spending * 100) if latest.till_withdrawals > 0 else 0,
                'other': (latest.other_spent / total_spending * 100) if latest.other_spent > 0 else 0,
            }
        else:
            category_percentages = {
                'betting': 0, 'airtime': 0, 'fuliza': 0, 'bars': 0, 'till_withdrawals': 0, 'other': 0
            }
        
        # Get top spending categories with formatted names
        category_names = {
            'betting': 'Betting',
            'airtime': 'Airtime',
            'fuliza': 'Fuliza',
            'bars': 'Bars & Restaurants',
            'till_withdrawals': 'Till Withdrawals',
            'other': 'Other',
        }
        categories = [
            (category_names['betting'], latest.betting_spent, category_percentages['betting']),
            (category_names['airtime'], latest.airtime_spent, category_percentages['airtime']),
            (category_names['fuliza'], latest.fuliza_spent, category_percentages['fuliza']),
            (category_names['bars'], latest.bars_spent, category_percentages['bars']),
            (category_names['till_withdrawals'], latest.till_withdrawals, category_percentages['till_withdrawals']),
            (category_names['other'], latest.other_spent, category_percentages['other']),
        ]
        top_categories = sorted([c for c in categories if c[1] > 0], key=lambda x: x[1], reverse=True)[:3]
        
        # Get recent transactions from parsed_data
        transactions = []
        if latest.parsed_data and 'transactions' in latest.parsed_data:
            transactions = latest.parsed_data['transactions'][:10]  # Last 10 transactions
        
        # Generate recommendations
        recommendations = []
        if latest.total_incoming > 0 and latest.betting_spent > latest.total_incoming * Decimal('0.3'):
            recommendations.append({
                'type': 'warning',
                'title': 'High Betting Spending',
                'message': f'You\'re spending {category_percentages["betting"]:.1f}% of your money on betting. Consider setting a monthly limit.'
            })
        if latest.fuliza_spent > 0:
            recommendations.append({
                'type': 'info',
                'title': 'Fuliza Usage Detected',
                'message': 'You\'re using M-Pesa Fuliza. Try to pay off credit quickly to avoid fees and save more.'
            })
        if net_amount < 0:
            recommendations.append({
                'type': 'error',
                'title': 'Negative Net Balance',
                'message': 'Your spending exceeds your income. Review your expenses and create a budget.'
            })
        elif net_amount > 0:
            recommendations.append({
                'type': 'success',
                'title': 'Positive Savings',
                'message': f'Great! You saved KSh {net_amount:.2f}. Consider adding this to a savings goal!'
            })
        
        context = {
            'statements': statements,
            'latest': latest,
            'net_amount': net_amount,
            'category_percentages': category_percentages,
            'top_categories': top_categories,
            'transactions': transactions,
            'recommendations': recommendations,
        }
    else:
        context = {
            'statements': [],
            'latest': None,
            'net_amount': Decimal('0.00'),
            'category_percentages': {},
            'top_categories': [],
            'transactions': [],
            'recommendations': [],
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
            # Check tribe join limit for free users
            if tribe.is_private:
                has_access, error_msg = check_feature_access(request.user, 'create_private_tribe')
                if not has_access:
                    messages.warning(request, error_msg)
                    return redirect('pricing')
            else:
                has_access, error_msg = check_feature_access(request.user, 'tribes_join')
                if not has_access:
                    messages.warning(request, error_msg)
                    return redirect('pricing')
            
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
    """Create new tribe - Pro only"""
    has_access, error_msg = check_feature_access(request.user, 'create_tribe')
    if not has_access:
        messages.warning(request, error_msg)
        return redirect('pricing')
    
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
    """Budget planning page - Pro only"""
    has_access, error_msg = check_feature_access(request.user, 'budget')
    if not has_access:
        messages.warning(request, error_msg)
        return redirect('pricing')
    
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
    # Limit free users to 3 months, Pro to 12 months
    is_pro = is_pro_user(request.user)
    months_limit = 12 if is_pro else 3
    
    today = timezone.now().date()
    
    # Get savings data for last N months (based on tier)
    months_data = []
    for i in range(months_limit - 1, -1, -1):
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
        'is_pro': is_pro,
        'months_limit': months_limit,
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


# ==================== PAYMENT & SUBSCRIPTION VIEWS ====================

@login_required
def pricing_view(request):
    """Pricing page"""
    subscription = request.user.subscription if hasattr(request.user, 'subscription') else None
    is_pro = is_pro_user(request.user) if subscription else False
    
    response = render(request, 'core/pricing.html', {
        'subscription': subscription,
        'is_pro': is_pro,
        'pro_price': PRO_MONTHLY_PRICE,
    })
    
    # Clear payment_pending cookie if user is now Pro
    if is_pro:
        response.delete_cookie('payment_pending')
    
    return response


@login_required
def upgrade_mpesa(request):
    """Initiate M-Pesa STK Push for subscription"""
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        
        if not phone_number:
            messages.error(request, 'Please provide your M-Pesa phone number.')
            return redirect('pricing')
        
        # Get or create subscription
        subscription, created = Subscription.objects.get_or_create(
            user=request.user,
            defaults={'tier': 'free', 'status': 'active'}
        )
        
        # Create pending payment
        from django.conf import settings
        # For sandbox, M-Pesa requires a publicly accessible callback URL
        # Options:
        # 1. Use ngrok: ngrok http 8000 (then use the ngrok URL)
        # 2. Use webhook.site for testing: https://webhook.site
        # 3. Deploy to a server with a public URL
        
        # Check if callback URL is set in environment, otherwise use localhost (won't work in sandbox)
        # Load from .env file via settings or environment variable
        from django.conf import settings
        callback_url = getattr(settings, 'MPESA_CALLBACK_URL', None) or os.environ.get('MPESA_CALLBACK_URL', None)
        if not callback_url:
            if settings.DEBUG:
                # For local development, you MUST use ngrok or webhook.site
                # This localhost URL won't work with M-Pesa sandbox
                callback_url = request.build_absolute_uri('/payments/mpesa/callback/')
                messages.warning(request, 'Warning: Using localhost callback URL. For sandbox testing, set MPESA_CALLBACK_URL in .env file to a public URL (e.g., ngrok URL).')
            else:
                callback_url = request.build_absolute_uri('/payments/mpesa/callback/')
        
        account_reference = f"AKIBA-{request.user.id}-{int(timezone.now().timestamp())}"
        
        payment = Payment.objects.create(
            user=request.user,
            amount=PRO_MONTHLY_PRICE,
            method='mpesa',
            status='pending',
            transaction_id=account_reference,
            subscription=subscription,
            metadata={
                'phone_number': phone_number,
                'checkout_request_id': account_reference,
            }
        )
        
        # Initiate STK Push
        success, response = initiate_mpesa_stk_push(
            phone_number=phone_number,
            amount=PRO_MONTHLY_PRICE,
            account_reference=account_reference,
            callback_url=callback_url
        )
        
        if success:
            checkout_request_id = response.get('CheckoutRequestID', '')
            # Update payment metadata with checkout_request_id for callback matching
            if not payment.metadata:
                payment.metadata = {}
            payment.metadata['checkout_request_id'] = checkout_request_id
            payment.transaction_id = checkout_request_id
            payment.save()
            messages.info(request, 'M-Pesa STK Push initiated! Please check your phone and enter your M-Pesa PIN to complete the payment. The page will refresh automatically once payment is confirmed.')
            response = redirect('pricing')
            # Add a flag to trigger auto-refresh after payment
            response.set_cookie('payment_pending', 'true', max_age=300)  # 5 minutes
            return response
        else:
            error_msg = response.get('errorMessage', 'Failed to initiate payment. Please try again.')
            messages.error(request, f'Payment error: {error_msg}')
            payment.delete()
            return redirect('pricing')
    
    return redirect('pricing')


@login_required
def upgrade_stripe(request):
    """Create Stripe checkout session"""
    success_url = request.build_absolute_uri('/payments/stripe/success/')
    cancel_url = request.build_absolute_uri('/pricing/')
    
    success, session_id = create_stripe_checkout_session(
        user=request.user,
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    if success:
        return redirect(f'https://checkout.stripe.com/pay/{session_id}')
    else:
        messages.error(request, f'Payment error: {session_id}')
        return redirect('pricing')


@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa callback after payment"""
    if request.method == 'POST':
        try:
            callback_data = json.loads(request.body)
            success, payment = handle_mpesa_callback(callback_data)
            
            if success and payment:
                # Send email confirmation
                from django.core.mail import send_mail
                send_mail(
                    subject='Akiba Pro Subscription Activated!',
                    message=f'Congratulations! Your Akiba Pro subscription has been activated. You now have access to all premium features.',
                    from_email=None,  # Will use DEFAULT_FROM_EMAIL from settings
                    recipient_list=[payment.user.email],
                    fail_silently=True,
                )
                
                return JsonResponse({'status': 'success', 'message': 'Payment processed successfully'})
        
        except Exception as e:
            print(f"M-Pesa callback error: {e}")
            import traceback
            traceback.print_exc()
    
    return JsonResponse({'status': 'error'}, status=400)


def stripe_webhook(request):
    """Handle Stripe webhook events"""
    if request.method == 'POST':
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        try:
            from .payments import STRIPE_WEBHOOK_SECRET
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            
            handle_stripe_webhook(event)
            return JsonResponse({'status': 'success'})
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except stripe.error.SignatureVerificationError as e:
            return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def stripe_success(request):
    """Handle successful Stripe payment"""
    session_id = request.GET.get('session_id')
    
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            payment = Payment.objects.filter(
                transaction_id=session_id
            ).first()
            
            if payment:
                # Send email confirmation
                from django.core.mail import send_mail
                send_mail(
                    subject='Akiba Pro Subscription Activated!',
                    message=f'Congratulations! Your Akiba Pro subscription has been activated. You now have access to all premium features.',
                    from_email=None,
                    recipient_list=[payment.user.email],
                    fail_silently=True,
                )
                
                messages.success(request, 'Payment successful! Your Pro subscription is now active.')
                return redirect('dashboard')
        except Exception as e:
            print(f"Stripe success error: {e}")
    
    messages.info(request, 'Payment processing. Your subscription will be activated shortly.')
    return redirect('dashboard')
