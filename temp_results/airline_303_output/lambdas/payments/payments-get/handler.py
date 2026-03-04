"""
Lambda handler for GET /payments/{charge_id}
"""
import json
import os
import secrets
from shared_utils import format_response, get_path_parameter, log_error

# Try to import stripe
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    print("Warning: stripe library not installed. Payment service will run in simulation mode.")


# Stripe configuration
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
_stripe_configured = False

# Simulated payment storage (used in simulation mode)
_payments = {}
_refunds = {}


def _configure_stripe():
    """Configure Stripe API with secret key from environment"""
    global _stripe_configured
    
    if _stripe_configured:
        return
    
    if not STRIPE_AVAILABLE:
        print("Stripe library not available - running in simulation mode")
        return
    
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
        _stripe_configured = True
        print("Stripe payment gateway configured successfully")
    else:
        print("STRIPE_SECRET_KEY not found in environment - running in simulation mode")


def _is_using_real_stripe() -> bool:
    """Check if real Stripe integration is available and configured"""
    _configure_stripe()
    return STRIPE_AVAILABLE and _stripe_configured


def get_payment(charge_id: str) -> dict:
    """
    Get payment details
    
    Args:
        charge_id: Charge identifier
        
    Returns:
        Payment details
        
    Raises:
        ValueError: If payment not found
    """
    # Try to get from local cache first (simulation mode)
    payment = _payments.get(charge_id)
    if payment:
        return payment
    
    # If using real Stripe, try to retrieve from Stripe API
    if _is_using_real_stripe():
        try:
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
        except stripe.error.StripeError:
            pass
    
    raise ValueError(f"Payment {charge_id} not found")


def lambda_handler(event, context):
    """
    Handler for GET /payments/{charge_id}
    """
    try:
        # Extract path parameter
        charge_id = get_path_parameter(event, 'charge_id')
        
        # Get payment
        payment = get_payment(charge_id)
        
        return format_response(200, payment)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(404, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
