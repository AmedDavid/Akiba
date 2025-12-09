"""
Payment processing utilities for M-Pesa and Stripe
"""
import base64
import os
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from .models import Subscription, Payment
import stripe

# M-Pesa Daraja API Configuration (Sandbox)
MPESA_CONSUMER_KEY = getattr(settings, 'MPESA_CONSUMER_KEY', 'your_consumer_key_here')
MPESA_CONSUMER_SECRET = getattr(settings, 'MPESA_CONSUMER_SECRET', 'your_consumer_secret_here')
MPESA_SHORTCODE = getattr(settings, 'MPESA_SHORTCODE', '174379')  # Sandbox shortcode
MPESA_PASSKEY = getattr(settings, 'MPESA_PASSKEY', 'your_passkey_here')
MPESA_BASE_URL = getattr(settings, 'MPESA_BASE_URL', 'https://sandbox.safaricom.co.ke')

# Stripe Configuration
STRIPE_SECRET_KEY = getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_your_key_here')
STRIPE_PUBLISHABLE_KEY = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', 'pk_test_your_key_here')
STRIPE_WEBHOOK_SECRET = getattr(settings, 'STRIPE_WEBHOOK_SECRET', 'whsec_your_secret_here')

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Subscription pricing
# For testing, set to 1. For production, use 199
PRO_MONTHLY_PRICE = int(os.environ.get('PRO_MONTHLY_PRICE', '1'))  # Default to 1 for testing, change to 199 for production


def get_mpesa_access_token():
    """Get M-Pesa OAuth access token"""
    url = f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    
    # Check if credentials are set
    if MPESA_CONSUMER_KEY == 'your_consumer_key_here' or MPESA_CONSUMER_SECRET == 'your_consumer_secret_here':
        print("M-Pesa error: Consumer key or secret not configured. Please set MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET in .env file")
        return None
    
    # Encode consumer key and secret
    credentials = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        access_token = data.get('access_token')
        if not access_token:
            print(f"M-Pesa error: No access token in response: {data}")
        return access_token
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = response.json()
        except:
            error_detail = response.text
        print(f"M-Pesa access token error: {e}")
        print(f"Response status: {response.status_code}")
        print(f"Response body: {error_detail}")
        print(f"Response headers: {dict(response.headers)}")
        return None
    except Exception as e:
        print(f"M-Pesa access token error: {e}")
        import traceback
        traceback.print_exc()
        return None


def initiate_mpesa_stk_push(phone_number, amount, account_reference, callback_url):
    """
    Initiate M-Pesa STK Push payment
    Returns: (success, response_data)
    """
    access_token = get_mpesa_access_token()
    if not access_token:
        return False, {'error': 'Failed to get access token'}
    
    url = f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest"
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Generate password
    password_string = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(password_string.encode()).decode()
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Format phone number (remove + and ensure 254 format)
    phone = phone_number.replace('+', '').replace(' ', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif not phone.startswith('254'):
        phone = '254' + phone
    
    payload = {
        "BusinessShortCode": str(MPESA_SHORTCODE),
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": str(MPESA_SHORTCODE),
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": f"Akiba Pro Subscription"
    }
    
    try:
        print(f"Debug: STK Push payload: {payload}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"Debug: Response status: {response.status_code}")
        print(f"Debug: Response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"Debug: Response text: {response.text}")
            try:
                error_data = response.json()
                print(f"Debug: Response JSON: {error_data}")
            except:
                pass
        
        response.raise_for_status()
        data = response.json()
        
        print(f"Debug: STK Push response: {data}")
        
        if data.get('ResponseCode') == '0':
            return True, data
        else:
            error_msg = data.get('errorMessage', data.get('ResponseDescription', 'Unknown error'))
            print(f"M-Pesa STK Push error: {error_msg}")
            return False, {'error': error_msg, 'response': data}
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = response.json()
        except:
            error_detail = response.text
        print(f"M-Pesa STK Push error: {e}")
        print(f"Response status: {response.status_code}")
        print(f"Response body: {error_detail}")
        return False, {'error': str(e), 'response': error_detail}
    except Exception as e:
        print(f"M-Pesa STK Push error: {e}")
        import traceback
        traceback.print_exc()
        return False, {'error': str(e)}


def create_stripe_checkout_session(user, success_url, cancel_url):
    """
    Create Stripe checkout session for subscription
    Returns: (success, session_id or error)
    """
    try:
        # Create checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'kes',
                    'product_data': {
                        'name': 'Akiba Pro Subscription',
                        'description': 'Monthly Pro subscription for Akiba Smart Savings',
                    },
                    'unit_amount': PRO_MONTHLY_PRICE * 100,  # Convert to cents
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(user.id),
            metadata={
                'user_id': user.id,
                'username': user.username,
            }
        )
        
        return True, session.id
    except Exception as e:
        print(f"Stripe checkout error: {e}")
        return False, str(e)


def handle_mpesa_callback(callback_data):
    """
    Handle M-Pesa callback after payment
    Returns: (success, payment_object)
    """
    try:
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', '')
        checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID', '')
        metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
        
        # Extract transaction details
        transaction_id = None
        amount = None
        phone_number = None
        
        for item in metadata:
            if item.get('Name') == 'MpesaReceiptNumber':
                transaction_id = item.get('Value')
            elif item.get('Name') == 'Amount':
                amount = float(item.get('Value', 0))
            elif item.get('Name') == 'PhoneNumber':
                phone_number = item.get('Value')
        
        if result_code == 0:  # Success
            print(f"Debug: Looking for payment with checkout_request_id: {checkout_request_id}")
            
            # Find payment by checkout request ID
            # SQLite doesn't support contains lookup on JSONField, so we need to search differently
            payments = Payment.objects.filter(method='mpesa', status='pending')
            print(f"Debug: Found {payments.count()} pending M-Pesa payments")
            
            payment = None
            
            # Search through pending payments to find matching checkout_request_id
            for p in payments:
                print(f"Debug: Checking payment {p.id}: metadata={p.metadata}, transaction_id={p.transaction_id}")
                if p.metadata and p.metadata.get('checkout_request_id') == checkout_request_id:
                    payment = p
                    print(f"Debug: Found payment by checkout_request_id: {p.id}")
                    break
            
            # If not found by checkout_request_id, try to find by transaction_id
            if not payment:
                print(f"Debug: Trying to find by transaction_id: {checkout_request_id}")
                payment = Payment.objects.filter(
                    transaction_id=checkout_request_id,
                    method='mpesa',
                    status='pending'
                ).first()
                if payment:
                    print(f"Debug: Found payment by transaction_id: {payment.id}")
            
            # If still not found, try to find by phone number and recent timestamp (within last 5 minutes)
            if not payment and phone_number:
                print(f"Debug: Trying to find by phone number: {phone_number}")
                from datetime import timedelta
                recent_time = timezone.now() - timedelta(minutes=5)
                payments = Payment.objects.filter(
                    method='mpesa',
                    status='pending',
                    created_at__gte=recent_time
                )
                for p in payments:
                    if p.metadata and p.metadata.get('phone_number') == str(phone_number):
                        payment = p
                        print(f"Debug: Found payment by phone number and recent timestamp: {p.id}")
                        break
            
            if payment:
                print(f"Debug: Processing payment {payment.id} for user {payment.user.username}")
                payment.status = 'completed'
                payment.transaction_id = transaction_id or checkout_request_id
                payment.metadata.update({
                    'mpesa_receipt': transaction_id,
                    'phone_number': phone_number,
                    'amount_paid': amount,
                })
                payment.save()
                
                # Activate subscription
                subscription = payment.subscription or payment.user.subscription
                if subscription:
                    subscription.tier = 'pro'
                    subscription.status = 'active'
                    subscription.payment_method = 'mpesa'
                    subscription.expiry_date = timezone.now() + timedelta(days=30)
                    subscription.save()
                    print(f"Debug: Subscription activated for user {payment.user.username} - tier: {subscription.tier}, status: {subscription.status}")
                else:
                    print(f"Debug: Warning - No subscription found for user {payment.user.username}, creating one...")
                    subscription = Subscription.objects.create(
                        user=payment.user,
                        tier='pro',
                        status='active',
                        payment_method='mpesa',
                        expiry_date=timezone.now() + timedelta(days=30)
                    )
                    payment.subscription = subscription
                    payment.save()
                    print(f"Debug: Created and activated subscription for user {payment.user.username}")
                
                return True, payment
            else:
                print(f"Debug: ERROR - Payment not found for checkout_request_id: {checkout_request_id}")
                print(f"Debug: Available pending payments:")
                for p in Payment.objects.filter(method='mpesa', status='pending'):
                    print(f"  - Payment {p.id}: transaction_id={p.transaction_id}, metadata={p.metadata}")
        
        return False, None
    except Exception as e:
        print(f"M-Pesa callback error: {e}")
        return False, None


def handle_stripe_webhook(event):
    """
    Handle Stripe webhook events
    """
    try:
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user_id = session.get('client_reference_id')
            
            if user_id:
                from django.contrib.auth.models import User
                try:
                    user = User.objects.get(id=int(user_id))
                    
                    # Create or update payment
                    payment, created = Payment.objects.get_or_create(
                        transaction_id=session['id'],
                        defaults={
                            'user': user,
                            'amount': session['amount_total'] / 100,  # Convert from cents
                            'method': 'stripe',
                            'status': 'completed',
                            'metadata': {
                                'stripe_session_id': session['id'],
                                'customer_email': session.get('customer_details', {}).get('email', ''),
                            }
                        }
                    )
                    
                    # Activate subscription
                    subscription = user.subscription
                    subscription.tier = 'pro'
                    subscription.status = 'active'
                    subscription.payment_method = 'stripe'
                    subscription.expiry_date = timezone.now() + timedelta(days=30)
                    subscription.save()
                    
                    payment.subscription = subscription
                    payment.save()
                    
                    return True
                except User.DoesNotExist:
                    return False
        
        elif event['type'] == 'customer.subscription.deleted':
            # Handle subscription cancellation
            subscription_data = event['data']['object']
            # Find user by Stripe customer ID and cancel subscription
            # Implementation depends on storing Stripe customer ID
            
        return False
    except Exception as e:
        print(f"Stripe webhook error: {e}")
        return False

