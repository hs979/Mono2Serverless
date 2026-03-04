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
    Get payment details
    """
    try:
        # Extract charge_id from path parameters
        charge_id = event.get('pathParameters', {}).get('charge_id')
        
        if not charge_id:
            return create_response(400, {'error': 'charge_id is required in path'})
        
        # Get payment
        payment = get_payment(charge_id)
        
        return create_response(200, payment)
        
    except Exception as e:
        return handle_error(e)


def get_payment(charge_id: str) -> dict:
    """
    Get payment details
    """
    # Check if Stripe is configured
    stripe_secret_key = os.environ.get('STRIPE_SECRET_KEY')
    
    if stripe_secret_key:
        # Real Stripe implementation
        try:
            import stripe
            stripe.api_key = stripe_secret_key
            
            if charge_id.startswith('pi_'):
                payment_intent = stripe.PaymentIntent.retrieve(charge_id)
                return {
                    'chargeId': payment_intent.id,
                    'amount': payment_intent.amount,
                    'status': payment_intent.status,
                    'currency': payment_intent.currency
                }
            elif charge_id.startswith('ch_'):
                charge = stripe.Charge.retrieve(charge_id)
                return {
                    'chargeId': charge.id,
                    'amount': charge.amount,
                    'status': charge.status,
                    'currency': charge.currency,
                    'receiptUrl': charge.receipt_url
                }
            else:
                raise ValueError(f"Invalid charge ID format: {charge_id}")
                
        except Exception as e:
            raise ValueError(f"Failed to retrieve payment: {str(e)}")
    else:
        # Simulation mode
        # Return simulated payment data
        return {
            'chargeId': charge_id,
            'amount': 15000,
            'status': 'succeeded',
            'currency': 'usd',
            'mode': 'simulation'
        }
