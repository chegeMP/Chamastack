import secrets
import string
from datetime import datetime, timedelta
import africastalking
from flask import current_app
import requests
import base64
import json
import re

def generate_join_code(length=8):
    """Generate a unique join code for chamas"""
    characters = string.ascii_uppercase + string.digits
    # Exclude confusing characters
    characters = characters.replace('0', '').replace('O', '').replace('I', '').replace('1')
    return ''.join(secrets.choice(characters) for _ in range(length))

def format_kenyan_phone(phone_number):
    """Format phone number to Kenyan standard (+254...)"""
    # Remove any spaces, dashes, or other characters
    phone = ''.join(filter(str.isdigit, phone_number))
    
    # Handle different formats
    if phone.startswith('254'):
        return f"+{phone}"
    elif phone.startswith('0'):
        return f"+254{phone[1:]}"
    elif len(phone) == 9:  # Missing country code and leading 0
        return f"+254{phone}"
    
    return phone_number  # Return as-is if format not recognized

class SMSService:
    """Handle SMS notifications using Africa's Talking"""
    
    def __init__(self):
        self.username = current_app.config.get('AFRICASTALKING_USERNAME')
        self.api_key = current_app.config.get('AFRICASTALKING_API_KEY')
        
        if self.username and self.api_key:
            africastalking.initialize(self.username, self.api_key)
            self.sms = africastalking.SMS
    
    def send_sms(self, phone_number, message):
        """Send SMS to a phone number"""
        try:
            if not self.username or not self.api_key:
                print(f"SMS not configured. Would send: {message} to {phone_number}")
                return True
            
            response = self.sms.send(message, [format_kenyan_phone(phone_number)])
            return response['SMSMessageData']['Recipients'][0]['status'] == 'Success'
        except Exception as e:
            print(f"SMS sending failed: {e}")
            return False
    
    def send_contribution_reminder(self, user, chama):
        """Send contribution reminder SMS"""
        message = f"Hi {user.name}, friendly reminder: Your {chama.contribution_frequency} contribution of KSh {chama.contribution_amount:,.0f} for {chama.name} is due. Reply STOP to opt out."
        return self.send_sms(user.phone_number, message)
    
    def send_contribution_confirmation(self, user, chama, amount):
        """Send contribution confirmation SMS"""
        message = f"Hi {user.name}, your contribution of KSh {amount:,.0f} to {chama.name} has been received and confirmed. Thank you!"
        return self.send_sms(user.phone_number, message)
    
    def send_join_notification(self, user, chama):
        """Send welcome SMS to new member"""
        message = f"Welcome to {chama.name}, {user.name}! Your contribution amount is KSh {chama.contribution_amount:,.0f} {chama.contribution_frequency}. Join code: {chama.join_code}"
        return self.send_sms(user.phone_number, message)

class MPesaService:
    """Handle M-Pesa payments integration"""
    
    def __init__(self):
        self.consumer_key = current_app.config.get('MPESA_CONSUMER_KEY')
        self.consumer_secret = current_app.config.get('MPESA_CONSUMER_SECRET')
        self.shortcode = current_app.config.get('MPESA_SHORTCODE')
        self.passkey = current_app.config.get('MPESA_PASSKEY')
        
        self.base_url = "https://sandbox.safaricom.co.ke"  # Use production URL in production
    
    def get_access_token(self):
        """Get OAuth access token from Safaricom"""
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            
            # Create basic auth header
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()['access_token']
            else:
                print(f"Failed to get access token: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None
    
    def initiate_stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK Push for payment"""
        access_token = self.get_access_token()
        if not access_token:
            return None
        
        try:
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password_string = f"{self.shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_string.encode()).decode('utf-8')
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": format_kenyan_phone(phone_number).replace('+', ''),
                "PartyB": self.shortcode,
                "PhoneNumber": format_kenyan_phone(phone_number).replace('+', ''),
                "CallBackURL": "https://your-domain.com/api/mpesa/callback",  # Update with your domain
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"STK Push failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error initiating STK push: {e}")
            return None

def calculate_next_contribution_date(chama, last_contribution_date=None):
    """Calculate when the next contribution is due"""
    if not last_contribution_date:
        last_contribution_date = datetime.now()
    
    if chama.contribution_frequency == 'weekly':
        return last_contribution_date + timedelta(weeks=1)
    elif chama.contribution_frequency == 'monthly':
        # Add one month (approximately 30 days)
        return last_contribution_date + timedelta(days=30)
    
    return last_contribution_date + timedelta(days=30)  # Default to monthly

def get_contribution_summary(chama, user=None, period='month'):
    """Get contribution summary for a chama or user"""
    # Import here to avoid circular imports
    try:
        from models import Contribution
    except ImportError:
        try:
            from .models import Contribution
        except ImportError:
            # If running as a script or different structure
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from models import Contribution
    
    from sqlalchemy import func, extract
    
    query = Contribution.query.filter_by(chama_id=chama.id, status='confirmed')
    
    if user:
        query = query.filter_by(user_id=user.id)
    
    # Filter by period
    now = datetime.now()
    if period == 'month':
        query = query.filter(
            extract('month', Contribution.contributed_at) == now.month,
            extract('year', Contribution.contributed_at) == now.year
        )
    elif period == 'year':
        query = query.filter(extract('year', Contribution.contributed_at) == now.year)
    
    total = query.with_entities(func.sum(Contribution.amount)).scalar() or 0
    count = query.count()
    
    return {
        'total_amount': total,
        'contribution_count': count,
        'average_contribution': total / count if count > 0 else 0
    }

def validate_kenyan_phone(phone_number):
    """Validate Kenyan phone number format"""
    # Remove any non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # Check various valid formats
    patterns = [
        r'^\+254[17]\d{8}$',  # +254701234567 or +254712345678
        r'^254[17]\d{8}$',    # 254701234567
        r'^0[17]\d{8}$',      # 0701234567
        r'^[17]\d{8}$'        # 701234567
    ]
    
    for pattern in patterns:
        if re.match(pattern, cleaned):
            return True
    
    return False