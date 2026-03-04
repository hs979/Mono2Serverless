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
    Refund payment
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        if not body or 'chargeId' not in body:
            return create_response(400, {'error': 'chargeId is required'})
        
        # Refund payment
        result = refund_payment(body['chargeId'])
        
        return create_response(200, result)
        
    except Exception as e:
        return handle_error(e)


def refund_payment(charge_id: str) -> dict:
    """
    Refund a payment from a given charge ID
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
            
            # Create refund
            refund = stripe.Refund.create(charge=charge_id)
            
            return {
                'refundId': refund.id
            }
                
        except Exception as e:
            raise ValueError(f"Refund failed: {str(e)}")
    else:
        # Simulation mode
        print(f"[SIMULATION] Refunding payment for charge: {charge_id}")
        
        import secrets
        refund_id = secrets.token_urlsafe(16)
        
        return {
            'refundId': refund_id
        }
