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

# HubSpot Pipeline Configuration
PIPELINE_ID = "869949826"  # Patient Journey Pipeline
STAGE_IDS = {
    "familyregistered": "1302219584",
    "intakeinprogress": "1302219585",
    "intakeincomplete": "1302219586",
    "checkoutincomplete": "1302219587",
    "activesubscriber": "1302219588",
    "subscriptionended": "1302219589"
}


def lambda_handler(event, context):
    """
    Main Lambda handler for deal events.
    Triggered by SQS messages from lambda_router.

    All events update ONE deal per patient that moves through pipeline stages.

    SQS event format:
    {
        "Records": [
            {
                "body": "{...deal event payload...}",
                "messageAttributes": {...}
            }
        ]
    }
    """
    try:
        # Parse SQS records
        if "Records" in event:
            # SQS batch processing
            results = []
            for record in event["Records"]:
                body = json.loads(record["body"])
                result = process_event(body)
                results.append(result)

            return {
                "statusCode": 200,
                "body": json.dumps({"processed": len(results), "results": results})
            }
        else:
            # Direct invocation (testing)
            result = process_event(event)
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


def process_event(body: Dict) -> Dict:
    """
    Process a single deal event.
    """
    event_type = body.get("event", {}).get("type")
    idempotency_key = body.get("event", {}).get("idempotency_key")

    logger.info(f"Processing event: {event_type}", extra={
        "event_type": event_type,
        "idempotency_key": idempotency_key
    })

    # Route to appropriate handler
    if event_type == "checkout.abandoned":
        result = handle_checkout_abandoned(body)
    elif event_type == "order.created":
        result = handle_order_created(body)
    elif event_type == "payment.succeeded":
        result = handle_payment_succeeded(body)
    elif event_type == "subscription.canceled":
        result = handle_subscription_canceled(body)
    else:
        logger.warning(f"Unknown event type: {event_type}")
        raise ValueError(f"Unknown event type: {event_type}")

    logger.info(f"Successfully processed event: {event_type}")
    return result


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
        "dealstage": STAGE_IDS["checkoutincomplete"]
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

    # Find or create the deal for this patient
    deal = hubspot.search_deal_by_patient_id(patient_external_id)

    if not deal:
        # Create deal if it doesn't exist (first order)
        contact_data = body.get("contact", {})
        dealname = f"{patient_data.get('first_name')} {patient_data.get('last_name')} — Patient Journey"
        deal_properties = {
            "dealstage": STAGE_IDS["activesubscriber"],
            "pipeline": PIPELINE_ID,
            "patient_external_id": patient_external_id
        }

        if orders:
            order = orders[0]
            amount = order.get("price_in_cents", 0) / 100
            deal_properties["subscription_external_id"] = order.get("external_id")
            deal_properties["mrr"] = str(amount)
            deal_properties["product_name"] = order.get("product_name")
            deal_properties["amount"] = str(amount)

        deal = hubspot.create_deal(dealname, deal_properties)
        deal_id = deal["id"]
        logger.info(f"Created new deal: {deal_id}")

        # Associate deal with guardian, patient, and company
        guardian_external_id = contact_data.get("external_id")
        print(f"Searching for guardian with external_id: {guardian_external_id}")
        guardian = hubspot.search_contact_by_external_id(guardian_external_id)

        print(f"Searching for patient with external_id: {patient_external_id}")
        patient = hubspot.search_contact_by_external_id(patient_external_id)

        print(f"Searching for company with family_external_id: {guardian_external_id}")
        company = hubspot.search_company_by_external_id(guardian_external_id)

        if guardian:
            print(f"✓ Found guardian: {guardian['id']}")
            try:
                hubspot.associate_deal_to_contact(deal_id, guardian["id"])
                print(f"✓ Associated deal with guardian {guardian['id']}")
            except Exception as e:
                print(f"✗ Failed to associate deal with guardian: {str(e)}")

        else:
            print(f"✗ Guardian not found for external_id: {guardian_external_id}")

        if patient:
            print(f"✓ Found patient: {patient['id']}")
            try:
                hubspot.associate_deal_to_contact(deal_id, patient["id"])
                print(f"✓ Associated deal with patient {patient['id']}")
            except Exception as e:
                print(f"✗ Failed to associate deal with patient: {str(e)}")
        else:
            print(f"✗ Patient not found for external_id: {patient_external_id}")

        if company:
            print(f"✓ Found company: {company['id']}")
            try:
                hubspot.associate_company_to_deal(company["id"], deal_id)
                print(f"✓ Associated deal with company {company['id']}")
            except Exception as e:
                print(f"✗ Failed to associate deal with company: {str(e)}")
        else:
            print(f"✗ Company not found for family_external_id: {guardian_external_id}")
    else:
        # Update existing deal
        deal_id = deal["id"]
        properties = {
            "dealstage": STAGE_IDS["activesubscriber"]
        }

        if orders:
            order = orders[0]
            amount = order.get("price_in_cents", 0) / 100
            properties["subscription_external_id"] = order.get("external_id")
            properties["mrr"] = str(amount)
            properties["product_name"] = order.get("product_name")
            properties["amount"] = str(amount)

        hubspot.update_deal(deal_id, properties)
        logger.info(f"Updated deal to activesubscriber: {deal_id}")

    return {
        "deal_id": deal_id,
        "message": "Deal created/updated to activesubscriber stage"
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
        "dealstage": STAGE_IDS["subscriptionended"]
    }

    hubspot.update_deal(deal["id"], properties)
    logger.info(f"Updated deal to subscriptionended: {deal['id']}")

    return {
        "deal_id": deal["id"],
        "message": "Deal moved to subscriptionended stage"
    }


if __name__ == "__main__":
    import json
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
    from test_data_helper import get_or_generate_test_data, build_order_created_event

    # Get or generate consistent test data (same IDs as lambda_registration)
    data = get_or_generate_test_data()
    test_event = build_order_created_event(data)

    print("Testing lambda_deal with order created event...")
    print(f"Guardian: {data['first_name']} {data['last_name']} ({data['email']})")
    print(f"Patient: {data['child_name']} {data['last_name']}")
    print(f"Guardian ID: {data['guardian_id']}")
    print(f"Patient ID: {data['patient_id']}")
    print(f"Product: {test_event['orders'][0]['product_name']} (${test_event['orders'][0]['price_in_cents']/100:.2f})")
    print(f"Event type: {test_event.get('event', {}).get('type')}")
    print("-" * 80)

    result = lambda_handler(test_event, None)

    print("-" * 80)
    print("Result:")
    print(json.dumps(result, indent=2))
