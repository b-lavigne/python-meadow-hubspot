"""
Lambda function to handle HubSpot webhook property change events.
Receives events from SQS queue populated by lambda_webhook_router.

HubSpot sends property change notifications when contacts, companies, or deals are updated.
This function will process those events and determine appropriate actions.
"""

import json
import os
import sys
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event, context):
    """
    Main Lambda handler for HubSpot webhook property change events.
    Triggered by SQS messages from lambda_webhook_router.

    SQS event format:
    {
        "Records": [
            {
                "body": "{...HubSpot webhook event...}",
                "messageAttributes": {
                    "event_type": "contact.propertyChange",
                    "event_id": "12345",
                    "object_id": "67890"
                }
            }
        ]
    }

    HubSpot webhook event structure:
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
    """
    try:
        # Log raw event for debugging
        logger.info(f"Received event with {len(event.get('Records', []))} records")

        # Parse SQS records
        if "Records" in event:
            # SQS batch processing
            results = []
            for record in event["Records"]:
                logger.info(f"Processing SQS record. Body type: {type(record.get('body'))}")
                body = json.loads(record["body"])
                result = process_hubspot_event(body)
                results.append(result)

            return {
                "statusCode": 200,
                "body": json.dumps({"processed": len(results), "results": results})
            }
        else:
            # Direct invocation (testing)
            logger.info("Direct invocation (no SQS Records)")
            result = process_hubspot_event(event)
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


def process_hubspot_event(event: Dict) -> Dict:
    """
    Process a single HubSpot webhook event.

    Args:
        event: HubSpot webhook event payload

    Returns:
        Dictionary with processing results
    """
    event_type = event.get("eventType")
    object_id = event.get("objectId")
    event_id = event.get("eventId")
    property_name = event.get("propertyName")
    property_value = event.get("propertyValue")
    occurred_at = event.get("occurredAt")

    logger.info(f"Processing HubSpot event", extra={
        "event_type": event_type,
        "event_id": event_id,
        "object_id": object_id,
        "property_name": property_name,
        "occurred_at": occurred_at
    })

    # Log the full event for now - we'll add specific handling logic later
    logger.info(f"Full HubSpot event: {json.dumps(event)}")

    # Route to appropriate handler based on event type
    if event_type and "propertyChange" in event_type:
        return handle_property_change(event)
    elif event_type and "creation" in event_type:
        return handle_creation(event)
    elif event_type and "deletion" in event_type:
        return handle_deletion(event)
    elif event_type and "associationChange" in event_type:
        return handle_association_change(event)
    else:
        logger.warning(f"Unknown event type: {event_type}")
        return {
            "status": "ignored",
            "event_type": event_type,
            "event_id": event_id,
            "message": f"No handler for event type: {event_type}"
        }


def handle_property_change(event: Dict) -> Dict:
    """
    Handle property change events from HubSpot.

    Property change events are sent when a property value changes on a contact, company, or deal.
    """
    event_type = event.get("eventType")
    object_id = event.get("objectId")
    property_name = event.get("propertyName")
    property_value = event.get("propertyValue")

    logger.info(f"Property change: {event_type} - {property_name}={property_value} on object {object_id}")

    # TODO: Add specific logic based on property changes
    # Example: If lifecyclestage changes to "customer", trigger welcome email
    # Example: If deal stage changes to "closedwon", notify sales team

    return {
        "status": "processed",
        "event_type": event_type,
        "object_id": object_id,
        "property_name": property_name,
        "property_value": property_value,
        "message": "Property change event logged"
    }


def handle_creation(event: Dict) -> Dict:
    """
    Handle object creation events from HubSpot.
    """
    event_type = event.get("eventType")
    object_id = event.get("objectId")

    logger.info(f"Object creation: {event_type} - object {object_id}")

    # TODO: Add specific logic for new object creation
    # Example: When new contact created, enroll in welcome workflow
    # Example: When new deal created, notify sales manager

    return {
        "status": "processed",
        "event_type": event_type,
        "object_id": object_id,
        "message": "Creation event logged"
    }


def handle_deletion(event: Dict) -> Dict:
    """
    Handle object deletion events from HubSpot.
    """
    event_type = event.get("eventType")
    object_id = event.get("objectId")

    logger.info(f"Object deletion: {event_type} - object {object_id}")

    # TODO: Add specific logic for object deletion
    # Example: Clean up related records in external systems
    # Example: Archive data for compliance

    return {
        "status": "processed",
        "event_type": event_type,
        "object_id": object_id,
        "message": "Deletion event logged"
    }


def handle_association_change(event: Dict) -> Dict:
    """
    Handle association change events from HubSpot.

    Association changes occur when objects are linked or unlinked.
    """
    event_type = event.get("eventType")
    from_object_id = event.get("fromObjectId")
    to_object_id = event.get("toObjectId")
    association_type = event.get("associationType")

    logger.info(f"Association change: {event_type} - {association_type} between {from_object_id} and {to_object_id}")

    # TODO: Add specific logic for association changes
    # Example: When contact is associated with company, update records
    # Example: When deal is associated with contact, sync to CRM

    return {
        "status": "processed",
        "event_type": event_type,
        "from_object_id": from_object_id,
        "to_object_id": to_object_id,
        "association_type": association_type,
        "message": "Association change event logged"
    }


if __name__ == "__main__":
    import time

    # Test with sample HubSpot webhook events
    current_timestamp = int(time.time() * 1000)

    # Example 1: Contact property change
    contact_property_change = {
        "objectId": 12469651,
        "eventId": 38162793401,
        "subscriptionId": 251,
        "portalId": 331,
        "appId": 11604521,
        "occurredAt": current_timestamp,
        "eventType": "contact.propertyChange",
        "subscriptionType": "contact.propertyChange",
        "propertyName": "lifecyclestage",
        "propertyValue": "customer",
        "changeSource": "CRM",
        "attemptNumber": 0
    }

    # Example 2: Deal creation
    deal_creation = {
        "objectId": 99887766,
        "eventId": 38162793403,
        "subscriptionId": 253,
        "portalId": 331,
        "appId": 11604521,
        "occurredAt": current_timestamp,
        "eventType": "deal.creation",
        "subscriptionType": "deal.creation",
        "changeSource": "CRM",
        "attemptNumber": 0
    }

    print("=" * 80)
    print("Testing lambda_webhook_property with HubSpot events...")
    print("=" * 80)

    # Test property change
    print("\n1. Testing property change event:")
    result1 = lambda_handler(contact_property_change, None)
    print(f"Result: {json.dumps(result1, indent=2)}")

    # Test creation event
    print("\n2. Testing creation event:")
    result2 = lambda_handler(deal_creation, None)
    print(f"Result: {json.dumps(result2, indent=2)}")
