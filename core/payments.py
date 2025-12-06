"""
Payment processing utilities for M-Pesa and Stripe
"""
import base64
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
PRO_MONTHLY_PRICE = 199  # KSh 199/month


def get_mpesa_access_token():
    """Get M-Pesa OAuth access token"""
    url = f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    
    # Encode consumer key and secret
    credentials = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get('access_token')
    except Exception as e:
        print(f"M-Pesa access token error: {e}")
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
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": f"Akiba Pro Subscription - {account_reference}"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data.get('ResponseCode') == '0':
            return True, data
        else:
            return False, data
    except Exception as e:
        print(f"M-Pesa STK Push error: {e}")
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
            # Find payment by checkout request ID
            payment = Payment.objects.filter(
                metadata__contains={'checkout_request_id': checkout_request_id}
            ).first()
            
            if payment:
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
                subscription.tier = 'pro'
                subscription.status = 'active'
                subscription.payment_method = 'mpesa'
                subscription.expiry_date = timezone.now() + timedelta(days=30)
                subscription.save()
                
                return True, payment
        
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

