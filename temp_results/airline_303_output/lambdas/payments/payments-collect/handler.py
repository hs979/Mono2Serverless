"""
Lambda handler for POST /payments/collect
"""
import json
import os
import secrets
from shared_utils import format_response, get_body, log_error

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


def collect_payment(charge_id: str) -> dict:
    """
    Collect payment from a pre-authorized charge
    
    In production mode (when STRIPE_SECRET_KEY is set):
    - Captures a payment intent or charge using Stripe API
    
    In simulation mode (when STRIPE_SECRET_KEY is not set):
    - Simulates payment collection for testing
    
    Args:
        charge_id: Pre-authorization charge ID or payment intent ID
        
    Returns:
        Dictionary containing:
            - receiptUrl: Receipt URL
            - price: Amount collected (in cents for Stripe, or base unit)
            
    Raises:
        ValueError: If charge ID is invalid or payment fails
    """
    if not charge_id:
        raise ValueError("Invalid Charge ID")
    
    # Real Stripe implementation
    if _is_using_real_stripe():
        try:
            # Check if this is a PaymentIntent or a Charge ID
            if charge_id.startswith('pi_'):
                # This is a PaymentIntent - capture it
                payment_intent = stripe.PaymentIntent.capture(charge_id)
                
                return {
                    'receiptUrl': f"https://dashboard.stripe.com/payments/{payment_intent.id}",
                    'price': payment_intent.amount / 100,  # Convert cents to dollars
                    'chargeId': payment_intent.id,
                    'status': payment_intent.status,
                    'currency': payment_intent.currency
                }
                
            elif charge_id.startswith('ch_'):
                # This is a Charge ID - capture it
                charge = stripe.Charge.capture(charge_id)
                
                return {
                    'receiptUrl': charge.receipt_url or f"https://dashboard.stripe.com/payments/{charge.id}",
                    'price': charge.amount / 100,  # Convert cents to dollars
                    'chargeId': charge.id,
                    'status': charge.status,
                    'currency': charge.currency
                }
            else:
                # Assume it's a test token or other ID - try to create a charge
                # This is for backward compatibility with test scenarios
                charge = stripe.Charge.create(
                    amount=15000,  # $150.00 in cents
                    currency='usd',
                    source=charge_id,
                    description='Airline booking payment'
                )
                
                return {
                    'receiptUrl': charge.receipt_url or f"https://dashboard.stripe.com/payments/{charge.id}",
                    'price': charge.amount / 100,
                    'chargeId': charge.id,
                    'status': charge.status,
                    'currency': charge.currency
                }
                
        except stripe.error.CardError as e:
            # Card was declined
            raise ValueError(f"Card declined: {e.user_message}")
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters
            raise ValueError(f"Invalid payment request: {str(e)}")
        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe failed
            raise ValueError(f"Stripe authentication failed: {str(e)}")
        except stripe.error.APIConnectionError as e:
            # Network communication failed
            raise ValueError(f"Network error: {str(e)}")
        except stripe.error.StripeError as e:
            # Generic Stripe error
            raise ValueError(f"Payment error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected payment error: {str(e)}")
    
    # Simulation mode
    else:
        print(f"[SIMULATION] Collecting payment for charge: {charge_id}")
        
        # Simulate payment collection
        receipt_url = f"https://payment.example.com/receipts/{charge_id}"
        price = 150  # Simulated price
        
        return {
            'receiptUrl': receipt_url,
            'price': price,
            'chargeId': charge_id,
            'status': 'captured',
            'mode': 'simulation'
        }


def lambda_handler(event, context):
    """
    Handler for POST /payments/collect
    """
    try:
        # Parse request body
        data = get_body(event)
        
        if not data or 'chargeId' not in data:
            return format_response(400, {'error': 'chargeId is required'})
        
        # Collect payment
        result = collect_payment(data['chargeId'])
        
        return format_response(200, result)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
