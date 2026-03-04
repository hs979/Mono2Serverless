import json
import os
import sys
sys.path.append('/opt/python')

from internal_client import (
    create_response,
    handle_error
)


def lambda_handler(event, context):
    """
    Collect payment
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        if not body or 'chargeId' not in body:
            return create_response(400, {'error': 'chargeId is required'})
        
        # Collect payment
        result = collect_payment(body['chargeId'])
        
        return create_response(200, result)
        
    except Exception as e:
        return handle_error(e)


def collect_payment(charge_id: str) -> dict:
    """
    Collect payment from a pre-authorized charge
    """
    if not charge_id:
        raise ValueError("Invalid Charge ID")
    
    # Check if Stripe is configured
    stripe_secret_key = os.environ.get('STRIPE_SECRET_KEY')
    
    if stripe_secret_key:
        # Real Stripe implementation
        try:
            import stripe
            stripe.api_key = stripe_secret_key
            
            # Try to capture payment
            if charge_id.startswith('pi_'):
                # PaymentIntent
                payment_intent = stripe.PaymentIntent.capture(charge_id)
                return {
                    'receiptUrl': f"https://dashboard.stripe.com/payments/{payment_intent.id}",
                    'price': payment_intent.amount / 100  # Convert cents to dollars
                }
            else:
                # Charge or token
                charge = stripe.Charge.create(
                    amount=15000,  # $150.00 in cents
                    currency='usd',
                    source=charge_id,
                    description='Airline booking payment'
                )
                return {
                    'receiptUrl': charge.receipt_url or f"https://dashboard.stripe.com/payments/{charge.id}",
                    'price': charge.amount / 100
                }
                
        except Exception as e:
            raise ValueError(f"Payment failed: {str(e)}")
    else:
        # Simulation mode
        print(f"[SIMULATION] Collecting payment for charge: {charge_id}")
        
        return {
            'receiptUrl': f"https://payment.example.com/receipts/{charge_id}",
            'price': 150  # Simulated price
        }
