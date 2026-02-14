"""
Lambda function to handle company-related webhook events.
Processes patient registration events, creating and updating companies (families) in HubSpot.
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
    Main Lambda handler for company events.
    Routes events to appropriate handler functions.
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
        if event_type == "patient.registered":
            result = handle_patient_registered(body)
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


def handle_patient_registered(body: Dict) -> Dict:
    """
    Handle patient.registered event.
    Creates a Company (Family) with name like "The Johnson Family".
    Associates the company with guardian contact and deal.
    """
    contact_data = body.get("contact", {})
    patient_data = body.get("patient", {})

    # Generate family name from guardian's last name
    guardian_last_name = contact_data.get("last_name")
    family_name = f"The {guardian_last_name} Family"

    # Use guardian external_id as family_external_id
    family_external_id = contact_data.get("external_id")

    # Company properties
    company_properties = {
        "family_external_id": family_external_id
    }

    # Check if company already exists
    existing_company = hubspot.search_company_by_external_id(family_external_id)
    if existing_company:
        company_id = existing_company["id"]
        company = hubspot.update_company(company_id, company_properties)
        logger.info(f"Updated existing company: {company_id}")
    else:
        company = hubspot.create_company(family_name, company_properties)
        company_id = company["id"]
        logger.info(f"Created new company: {company_id}")

    # Find guardian contact to associate with company
    guardian_external_id = contact_data.get("external_id")
    guardian = hubspot.search_contact_by_external_id(guardian_external_id)

    if guardian:
        guardian_id = guardian["id"]
        # Associate company with guardian contact
        try:
            hubspot.associate_company_to_contact(company_id, guardian_id)
            logger.info(f"Associated company {company_id} with guardian contact {guardian_id}")
        except Exception as e:
            logger.warning(f"Company-contact association may already exist: {str(e)}")

        # Find patient's deal to associate with company
        patient_external_id = patient_data.get("external_id")
        deal = hubspot.search_deal_by_patient_id(patient_external_id)

        if deal:
            deal_id = deal["id"]
            # Associate company with deal
            try:
                hubspot.associate_company_to_deal(company_id, deal_id)
                logger.info(f"Associated company {company_id} with deal {deal_id}")
            except Exception as e:
                logger.warning(f"Company-deal association may already exist: {str(e)}")
        else:
            logger.warning(f"No deal found for patient {patient_external_id}, skipping deal association")
    else:
        logger.warning(f"Guardian not found: {guardian_external_id}, skipping associations")

    return {
        "company_id": company_id,
        "family_name": family_name,
        "message": "Company (Family) created and associated"
    }


if __name__ == "__main__":
    import json

    # Load test event from JSON file
    with open("../docs/json_objects/event_patient_register.json", "r") as f:
        test_event = json.load(f)

    print("Testing lambda_company with patient registration event...")
    print(f"Event type: {test_event.get('event', {}).get('type')}")
    print("-" * 80)

    result = lambda_handler(test_event, None)

    print("-" * 80)
    print("Result:")
    print(json.dumps(result, indent=2))
