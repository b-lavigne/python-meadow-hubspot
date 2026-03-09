"""
Lambda Router - receives all webhook events and routes to appropriate SQS queue.

Architecture:
API Gateway → Lambda Router → SQS Queue → Event-specific Lambda

Routing logic based on event.type:
- patient.registered → registration_queue → lambda_registration
- intake.started, intake.abandoned, checkout.abandoned → deal_queue → lambda_deal
- order.created, payment.succeeded, subscription.* → deal_queue → lambda_deal
"""

import json
import os
import sys
import logging
import boto3
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Initialize SQS client
sqs = boto3.client('sqs')

# SQS Queue URLs from environment variables
REGISTRATION_QUEUE_URL = os.environ.get("REGISTRATION_QUEUE_URL")
DEAL_QUEUE_URL = os.environ.get("DEAL_QUEUE_URL")
CONTACT_QUEUE_URL = os.environ.get("CONTACT_QUEUE_URL")

# Event type to queue mapping
EVENT_ROUTING = {
    "patient.registered": "REGISTRATION_QUEUE_URL",
    "intake.started": "DEAL_QUEUE_URL",
    "intake.abandoned": "DEAL_QUEUE_URL",
    "checkout.abandoned": "DEAL_QUEUE_URL",
    "order.created": "DEAL_QUEUE_URL",
    "payment.succeeded": "DEAL_QUEUE_URL",
    "payment.failed": "DEAL_QUEUE_URL",
    "subscription.restarted": "DEAL_QUEUE_URL",
    "subscription.refill_pushed": "DEAL_QUEUE_URL",
    "subscription.canceled": "DEAL_QUEUE_URL",
}


def lambda_handler(event, context):
    """
    Main Lambda handler for webhook routing.
    Receives webhook from API Gateway and routes to appropriate SQS queue.
    """
    try:
        # Parse event body from API Gateway
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event

        event_type = body.get("event", {}).get("type")
        idempotency_key = body.get("event", {}).get("idempotency_key")

        logger.info(f"Routing event: {event_type}", extra={
            "event_type": event_type,
            "idempotency_key": idempotency_key
        })

        # Determine target queue
        queue_env_var = EVENT_ROUTING.get(event_type)
        if not queue_env_var:
            logger.warning(f"Unknown event type: {event_type}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown event type: {event_type}"})
            }

        # Get queue URL from environment
        queue_url = os.environ.get(queue_env_var)
        if not queue_url:
            logger.error(f"Queue URL not configured for: {queue_env_var}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Queue configuration error"})
            }

        # Send message to SQS queue
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(body),
            MessageAttributes={
                'event_type': {
                    'StringValue': event_type,
                    'DataType': 'String'
                },
                'idempotency_key': {
                    'StringValue': idempotency_key or '',
                    'DataType': 'String'
                }
            }
        )

        logger.info(f"Message sent to queue: {queue_env_var}", extra={
            "message_id": response['MessageId'],
            "event_type": event_type
        })

        # Return 200 immediately to webhook sender
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Event received and queued",
                "message_id": response['MessageId']
            })
        }

    except Exception as e:
        logger.error(f"Error routing event: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


if __name__ == "__main__":
    import random
    import uuid
    from datetime import datetime

    # Generate random test data
    FIRST_NAMES = ["Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "William"]
    LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    CHILD_FIRST_NAMES = ["Tommy", "Lily", "Max", "Sophie", "Jake", "Emma", "Oliver", "Chloe", "Lucas", "Mia"]
    STATES = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "MI", "NC", "GA"]

    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    child_name = random.choice(CHILD_FIRST_NAMES)
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    phone = f"1{random.randint(2000000000, 9999999999)}"
    state = random.choice(STATES)
    guardian_id = f"{random.randint(100000, 999999)}-"
    patient_id = str(random.randint(10, 99))
    guardian_num = int(guardian_id.rstrip('-'))

    test_event = {
        "event": {
            "type": "patient.registered",
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "patient_portal",
            "idempotency_key": f"evt_reg_usr{random.randint(10, 99)}"
        },
        "contact": {
            "external_id": guardian_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "state": state,
            "domain_slug": "foothillsderm.com"
        },
        "patient": {
            "external_id": patient_id,
            "first_name": child_name,
            "last_name": last_name,
            "date_of_birth": "2017-03-15",
            "gender": "MALE",
            "is_minor": True,
            "guardian_id": guardian_num,
            "relationship_to_contact": "child"
        },
        "context": {
            "utm_*": "",
            "fbclid": ""
        }
    }

    print("Testing lambda_router with patient registration event...")
    print(f"Guardian: {first_name} {last_name} ({email})")
    print(f"Patient: {child_name} {last_name}")
    print(f"Event type: {test_event.get('event', {}).get('type')}")
    print(f"Target queue: {EVENT_ROUTING.get(test_event.get('event', {}).get('type'))}")
    print("-" * 80)

    # Mock environment for local testing
    os.environ['REGISTRATION_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789/registration-queue'
    os.environ['DEAL_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789/deal-queue'
    os.environ['CONTACT_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789/contact-queue'

    print("\nNOTE: Running locally without SQS access - would send to queue in AWS")
    print(f"Event would be routed to: {os.environ.get(EVENT_ROUTING.get(test_event['event']['type']))}")
    print("\nEvent payload:")
    print(json.dumps(test_event, indent=2))
