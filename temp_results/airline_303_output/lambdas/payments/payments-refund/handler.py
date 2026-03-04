"""
Lambda handler for POST /payments/refund
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


def refund_payment(charge_id: str) -> dict:
    """
    Refund a payment from a given charge ID
    
    In production mode (when STRIPE_SECRET_KEY is set):
    - Creates a refund using Stripe API
    
    In simulation mode (when STRIPE_SECRET_KEY is not set):
    - Simulates refund for testing
    
    Args:
        charge_id: Pre-authorization charge ID or payment intent ID
        
    Returns:
        Dictionary containing refund ID
        
    Raises:
        ValueError: If charge ID is invalid or refund fails
    """
    if not charge_id:
        raise ValueError("Invalid Charge ID")
    
    # Real Stripe implementation
    if _is_using_real_stripe():
        try:
            # Check if this is a PaymentIntent or a Charge ID
            if charge_id.startswith('pi_'):
                # Get the PaymentIntent to find the charge
                payment_intent = stripe.PaymentIntent.retrieve(charge_id)
                
                # Get the latest charge from the payment intent
                if payment_intent.latest_charge:
                    charge_id_to_refund = payment_intent.latest_charge
                else:
                    raise ValueError(f"No charge found for payment intent: {charge_id}")
            else:
                charge_id_to_refund = charge_id
            
            # Create the refund
            refund = stripe.Refund.create(charge=charge_id_to_refund)
            
            return {
                'refundId': refund.id,
                'chargeId': charge_id_to_refund,
                'amount': refund.amount,
                'status': refund.status,
                'currency': refund.currency
            }
            
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters or charge not found
            raise ValueError(f"Invalid refund request: {str(e)}")
        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe failed
            raise ValueError(f"Stripe authentication failed: {str(e)}")
        except stripe.error.APIConnectionError as e:
            # Network communication failed
            raise ValueError(f"Network error: {str(e)}")
        except stripe.error.StripeError as e:
            # Generic Stripe error
            raise ValueError(f"Refund error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected refund error: {str(e)}")
    
    # Simulation mode
    else:
        print(f"[SIMULATION] Refunding payment for charge: {charge_id}")
        
        # Simulate refund processing
        refund_id = secrets.token_urlsafe(16)
        
        return {
            'refundId': refund_id,
            'chargeId': charge_id,
            'status': 'refunded',
            'mode': 'simulation'
        }


def lambda_handler(event, context):
    """
    Handler for POST /payments/refund
    """
    try:
        # Parse request body
        data = get_body(event)
        
        if not data or 'chargeId' not in data:
            return format_response(400, {'error': 'chargeId is required'})
        
        # Refund payment
        result = refund_payment(data['chargeId'])
        
        return format_response(200, result)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
