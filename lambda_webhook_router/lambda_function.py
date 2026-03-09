"""
Lambda Webhook Router - receives HubSpot webhook events and routes to appropriate SQS queue.

Architecture:
HubSpot → API Gateway → Lambda Webhook Router → SQS Queue → Event-specific Lambda

HubSpot Webhook Events:
- contact.propertyChange → Process contact property updates
- deal.propertyChange → Process deal property updates
- company.propertyChange → Process company property updates
- contact.creation → New contact created
- deal.creation → New deal created
- company.creation → New company created
- contact.deletion → Contact deleted
- deal.deletion → Deal deleted
- company.deletion → Company deleted

HubSpot sends batches of up to 100 events per webhook POST request.
"""

import json
import os
import sys
import logging
import boto3
import hashlib
import hmac
from typing import Dict, Any, List

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Initialize SQS client
sqs = boto3.client('sqs')

# SQS Queue URLs from environment variables
HUBSPOT_EVENTS_QUEUE_URL = os.environ.get("HUBSPOT_EVENTS_QUEUE_URL")

# HubSpot App Secret for signature validation
HUBSPOT_APP_SECRET = os.environ.get("HUBSPOT_APP_SECRET")


def verify_hubspot_signature(request_body: str, signature: str) -> bool:
    """
    Verify HubSpot webhook signature using HMAC SHA-256.

    HubSpot sends X-HubSpot-Signature header with SHA-256 hash of:
    app_secret + request_body

    Args:
        request_body: Raw request body string
        signature: X-HubSpot-Signature header value

    Returns:
        True if signature is valid, False otherwise
    """
    if not HUBSPOT_APP_SECRET:
        logger.warning("HUBSPOT_APP_SECRET not configured - skipping signature validation")
        return True  # Allow in dev/test environments

    try:
        # HubSpot concatenates app_secret + request_body, then SHA-256 hashes it
        expected_signature = hashlib.sha256(
            (HUBSPOT_APP_SECRET + request_body).encode('utf-8')
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error validating signature: {e}")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler for HubSpot webhook routing.

    HubSpot sends batches of events (up to 100 per request) as JSON array.
    Each event is sent to SQS for asynchronous processing.

    Expected payload format:
    [
        {
            "objectId": 1246965,
            "eventId": 3816279340,
            "subscriptionId": 25,
            "portalId": 33,
            "appId": 1160452,
            "occurredAt": 1462216307945,
            "eventType": "contact.propertyChange",
            "subscriptionType": "contact.propertyChange",
            "propertyName": "email",
            "propertyValue": "test@example.com",
            "changeSource": "CRM",
            "attemptNumber": 0
        }
    ]
    """
    try:
        # Extract request body and headers from API Gateway event
        request_body = event.get("body", "")
        headers = event.get("headers", {})

        # HubSpot signature validation (X-HubSpot-Signature header)
        signature = headers.get("X-HubSpot-Signature") or headers.get("x-hubspot-signature")

        if signature and not verify_hubspot_signature(request_body, signature):
            logger.error("Invalid HubSpot signature")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Invalid signature"})
            }

        # Parse HubSpot events (array of events)
        if isinstance(request_body, str):
            events = json.loads(request_body)
        else:
            events = request_body

        # HubSpot sends array of events
        if not isinstance(events, list):
            events = [events]

        logger.info(f"Received {len(events)} HubSpot events")

        # Validate queue configuration
        if not HUBSPOT_EVENTS_QUEUE_URL:
            logger.error("HUBSPOT_EVENTS_QUEUE_URL not configured")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Queue configuration error"})
            }

        # Process each event in the batch
        message_ids = []
        for hubspot_event in events:
            event_type = hubspot_event.get("eventType")
            event_id = hubspot_event.get("eventId")
            object_id = hubspot_event.get("objectId")

            logger.info(f"Processing HubSpot event: {event_type}", extra={
                "event_type": event_type,
                "event_id": event_id,
                "object_id": object_id
            })

            # Send message to SQS queue
            response = sqs.send_message(
                QueueUrl=HUBSPOT_EVENTS_QUEUE_URL,
                MessageBody=json.dumps(hubspot_event),
                MessageAttributes={
                    'event_type': {
                        'StringValue': event_type or '',
                        'DataType': 'String'
                    },
                    'event_id': {
                        'StringValue': str(event_id) if event_id else '',
                        'DataType': 'String'
                    },
                    'object_id': {
                        'StringValue': str(object_id) if object_id else '',
                        'DataType': 'String'
                    }
                }
            )

            message_ids.append(response['MessageId'])

        logger.info(f"Queued {len(message_ids)} events to SQS")

        # Return 200 immediately to HubSpot (must respond within 5 seconds)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Received and queued {len(events)} events",
                "queued_count": len(message_ids)
            })
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON"})
        }

    except Exception as e:
        logger.error(f"Error processing HubSpot webhook: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


if __name__ == "__main__":
    import random
    import time

    # Generate HubSpot-style test webhook events
    current_timestamp = int(time.time() * 1000)  # HubSpot uses milliseconds

    # Example 1: Contact property change (email updated)
    contact_property_change = {
        "objectId": 12469651,
        "eventId": 38162793401,
        "subscriptionId": 251,
        "portalId": 331,
        "appId": 11604521,
        "occurredAt": current_timestamp,
        "eventType": "contact.propertyChange",
        "subscriptionType": "contact.propertyChange",
        "propertyName": "email",
        "propertyValue": "updated.email@example.com",
        "changeSource": "CRM",
        "attemptNumber": 0
    }

    # Example 2: Deal stage change
    deal_property_change = {
        "objectId": 78945612,
        "eventId": 38162793402,
        "subscriptionId": 252,
        "portalId": 331,
        "appId": 11604521,
        "occurredAt": current_timestamp,
        "eventType": "deal.propertyChange",
        "subscriptionType": "deal.propertyChange",
        "propertyName": "dealstage",
        "propertyValue": "1302219588",  # activesubscriber stage
        "changeSource": "IMPORT",
        "attemptNumber": 0
    }

    # Example 3: New contact created
    contact_creation = {
        "objectId": 99887766,
        "eventId": 38162793403,
        "subscriptionId": 253,
        "portalId": 331,
        "appId": 11604521,
        "occurredAt": current_timestamp,
        "eventType": "contact.creation",
        "subscriptionType": "contact.creation",
        "changeSource": "CRM",
        "attemptNumber": 0
    }

    # HubSpot sends batch of events
    test_webhook_batch = [
        contact_property_change,
        deal_property_change,
        contact_creation
    ]

    print("=" * 80)
    print("Testing lambda_webhook_router with HubSpot webhook events...")
    print("=" * 80)
    print(f"\nReceived batch of {len(test_webhook_batch)} events:\n")

    for i, event in enumerate(test_webhook_batch, 1):
        print(f"{i}. {event['eventType']}")
        print(f"   Object ID: {event['objectId']}")
        print(f"   Event ID: {event['eventId']}")
        if 'propertyName' in event:
            print(f"   Property: {event['propertyName']} = {event['propertyValue']}")
        print()

    print("-" * 80)

    # Mock environment for local testing
    os.environ['HUBSPOT_EVENTS_QUEUE_URL'] = 'https://sqs.us-east-2.amazonaws.com/253260000779/hubspot-events-queue'
    os.environ['HUBSPOT_APP_SECRET'] = 'test-secret-for-local-dev'

    # Simulate API Gateway event structure
    api_gateway_event = {
        "body": json.dumps(test_webhook_batch),
        "headers": {
            "X-HubSpot-Signature": "mock-signature-for-testing"
        }
    }

    print("\nNOTE: Running locally without SQS access - would send to queue in AWS")
    print(f"Target queue: {os.environ.get('HUBSPOT_EVENTS_QUEUE_URL')}")
    print("\nWebhook payload (HubSpot batch format):")
    print(json.dumps(test_webhook_batch, indent=2))
