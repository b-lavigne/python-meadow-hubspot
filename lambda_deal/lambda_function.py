"""
Lambda function to handle deal-related webhook events.
Updates ONE deal per patient that moves through pipeline stages based on patient journey.

Key Model: Each patient has ONE deal that transitions through stages:
- intake_in_progress → intake_abandoned/checkout_abandoned → active_subscription

All events find the existing deal and update its stage/properties.
No new deals are created (deal is created during patient.registered in lambda_contact).
"""

import json
import os
import sys
import logging
from typing import Dict, Any

# Add shared directory to path (works both locally and in Lambda)
# Try multiple paths to work with different execution contexts
for path in [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'shared'),  # Relative to this file
    os.path.join(os.getcwd(), 'shared'),  # From project root (IntelliJ)
    '/var/task/shared'  # Lambda environment
]:
    if path not in sys.path:
        sys.path.insert(0, path)

import hubspot


# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event, context):
    """
    Main Lambda handler for deal events.
    Routes events to appropriate handler functions.

    All events update ONE deal per patient that moves through pipeline stages.
    """
    try:
        # Parse event body if coming from API Gateway
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event

        event_type = body.get("event", {}).get("type")
        idempotency_key = body.get("event", {}).get("idempotency_key")

        logger.info(f"Processing event: {event_type}", extra={
            "event_type": event_type,
            "idempotency_key": idempotency_key
        })

        # Route to appropriate handler
        if event_type == "intake.started":
            result = handle_intake_started(body)
        elif event_type == "intake.abandoned":
            result = handle_intake_abandoned(body)
        elif event_type == "checkout.abandoned":
            result = handle_checkout_abandoned(body)
        elif event_type == "order.created":
            result = handle_order_created(body)
        elif event_type == "payment.succeeded":
            result = handle_payment_succeeded(body)
        elif event_type == "subscription.restarted":
            result = handle_subscription_restarted(body)
        elif event_type == "subscription.refill_pushed":
            result = handle_refill_pushed(body)
        elif event_type == "subscription.canceled":
            result = handle_subscription_canceled(body)
        else:
            logger.warning(f"Unknown event type: {event_type}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown event type: {event_type}"})
            }

        logger.info(f"Successfully processed event: {event_type}")
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except Exception as e:
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def handle_intake_started(body: Dict) -> Dict:
    """
    Handle intake.started event.
    Finds the existing deal by patient_external_id and updates to "intake_in_progress" stage.
    """
    patient_data = body.get("patient", {})
    patient_external_id = patient_data.get("external_id")

    if not patient_external_id:
        raise Exception("Patient external_id is required")

    # Find the deal by patient_external_id
    deal = hubspot.search_deal_by_patient_id(patient_external_id)
    if not deal:
        raise Exception(f"Deal not found for patient: {patient_external_id}")

    # Update deal stage
    properties = {
        "dealstage": "intakeinprogress"
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal to intake_in_progress: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Deal moved to intake_in_progress stage"
    }


def handle_intake_abandoned(body: Dict) -> Dict:
    """
    Handle intake.abandoned event.
    Finds the existing deal by patient_external_id and updates to "intakeincomplete" stage.
    """
    patient_data = body.get("patient", {})
    patient_external_id = patient_data.get("external_id")

    if not patient_external_id:
        raise Exception("Patient external_id is required")

    # Find the deal by patient_external_id
    deal = hubspot.search_deal_by_patient_id(patient_external_id)
    if not deal:
        raise Exception(f"Deal not found for patient: {patient_external_id}")

    # Update deal stage
    properties = {
        "dealstage": "intakeincomplete"
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal to intakeincomplete: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Deal moved to intakeincomplete stage"
    }


def handle_checkout_abandoned(body: Dict) -> Dict:
    """
    Handle checkout.abandoned event.
    Finds the existing deal by patient_external_id and updates to "checkoutincomplete" stage.
    """
    patient_data = body.get("patient", {})
    patient_external_id = patient_data.get("external_id")

    if not patient_external_id:
        raise Exception("Patient external_id is required")

    # Find the deal by patient_external_id
    deal = hubspot.search_deal_by_patient_id(patient_external_id)
    if not deal:
        raise Exception(f"Deal not found for patient: {patient_external_id}")

    # Update deal stage
    properties = {
        "dealstage": "checkoutincomplete"
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal to checkoutincomplete: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Deal moved to checkoutincomplete stage"
    }


def handle_order_created(body: Dict) -> Dict:
    """
    Handle order.created event.
    Finds the existing deal by patient_external_id and updates to "active_subscription" stage.
    Sets subscription_external_id and mrr from the order.
    """
    patient_data = body.get("patient", {})
    patient_external_id = patient_data.get("external_id")
    orders = body.get("orders", [])

    if not patient_external_id:
        raise Exception("Patient external_id is required")

    # Find the deal by patient_external_id
    deal = hubspot.search_deal_by_patient_id(patient_external_id)
    if not deal:
        raise Exception(f"Deal not found for patient: {patient_external_id}")

    # Update deal stage and properties
    properties = {
        "dealstage": "activesubscriber"
    }

    if orders:
        order = orders[0]
        amount = order.get("price_in_cents", 0) / 100  # Convert cents to dollars
        properties["subscription_external_id"] = order.get("external_id")
        properties["mrr"] = str(amount)
        properties["product_name"] = order.get("product_name")
        properties["amount"] = str(amount)

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal to activesubscriber: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Deal moved to active_subscription stage"
    }


def handle_payment_succeeded(body: Dict) -> Dict:
    """
    Handle payment.succeeded event.
    Finds deal by subscription_external_id and updates last_payment_date and mrr.
    """
    subscription = body.get("subscription", {})
    payment = body.get("payment", {})
    subscription_external_id = subscription.get("external_id")

    if not subscription_external_id:
        logger.warning("Payment succeeded but no subscription_external_id found")
        return {"message": "Payment succeeded - no subscription ID to find deal"}

    # Find the deal by subscription_external_id
    deal = hubspot.search_deal_by_external_id(subscription_external_id)
    if not deal:
        logger.warning(f"Deal not found for subscription: {subscription_external_id}")
        return {"message": "Payment succeeded - no deal found"}

    # Update payment info
    amount = payment.get("amount_in_cents", 0) / 100
    properties = {
        "last_payment_date": body.get("event", {}).get("timestamp"),
        "mrr": str(amount)
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal payment info: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Payment info updated"
    }


def handle_subscription_restarted(body: Dict) -> Dict:
    """
    Handle subscription.restarted event.
    Finds deal by subscription_external_id and moves to "active_subscription" stage.
    """
    subscription = body.get("subscription", {})
    subscription_external_id = subscription.get("external_id")

    if not subscription_external_id:
        raise Exception("Subscription external_id is required")

    # Find the deal by subscription_external_id
    deal = hubspot.search_deal_by_external_id(subscription_external_id)
    if not deal:
        raise Exception(f"Deal not found for subscription: {subscription_external_id}")

    # Update deal stage
    properties = {
        "dealstage": "activesubscriber"
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal to activesubscriber: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Deal moved to activesubscriber stage"
    }


def handle_refill_pushed(body: Dict) -> Dict:
    """
    Handle subscription.refill_pushed event.
    Finds deal by subscription_external_id and updates next_refill_date.
    """
    subscription = body.get("subscription", {})
    subscription_external_id = subscription.get("external_id")

    if not subscription_external_id:
        raise Exception("Subscription external_id is required")

    # Find the deal by subscription_external_id
    deal = hubspot.search_deal_by_external_id(subscription_external_id)
    if not deal:
        raise Exception(f"Deal not found for subscription: {subscription_external_id}")

    # Update next refill date
    properties = {
        "next_refill_date": subscription.get("next_refill_at")
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal refill date: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Refill date updated"
    }


def handle_subscription_canceled(body: Dict) -> Dict:
    """
    Handle subscription.canceled event.
    Finds deal by subscription_external_id and moves to "closedlost" stage.
    """
    subscription = body.get("subscription", {})
    subscription_external_id = subscription.get("external_id")

    if not subscription_external_id:
        raise Exception("Subscription external_id is required")

    # Find the deal by subscription_external_id
    deal = hubspot.search_deal_by_external_id(subscription_external_id)
    if not deal:
        raise Exception(f"Deal not found for subscription: {subscription_external_id}")

    # Move deal to subscriptionended
    properties = {
        "dealstage": "subscriptionended"
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal to subscriptionended: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Deal moved to subscriptionended stage"
    }


if __name__ == "__main__":
    import json

    # Load test event from JSON file
    with open("../docs/json_objects/event_order_created.json", "r") as f:
        test_event = json.load(f)

    print("Testing lambda_deal with order created event...")
    print(f"Event type: {test_event.get('event', {}).get('type')}")
    print("-" * 80)

    result = lambda_handler(test_event, None)

    print("-" * 80)
    print("Result:")
    print(json.dumps(result, indent=2))
