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
    Main Lambda handler for registration events.
    Triggered by SQS messages from lambda_router.

    SQS event format:
    {
        "Records": [
            {
                "body": "{...patient registration payload...}",
                "messageAttributes": {...}
            }
        ]
    }
    """
    try:
        # Log raw event for debugging
        logger.info(f"Received event: {json.dumps(event)[:1000]}")

        # Parse SQS records
        if "Records" in event:
            # SQS batch processing
            results = []
            for record in event["Records"]:
                logger.info(f"Processing SQS record. Body type: {type(record.get('body'))}")
                body = json.loads(record["body"])
                result = process_event(body)
                results.append(result)

            return {
                "statusCode": 200,
                "body": json.dumps({"processed": len(results), "results": results})
            }
        else:
            # Direct invocation (testing)
            logger.info("Direct invocation (no SQS Records)")
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
    Process a single registration event.
    """
    # Log body structure for debugging
    logger.info(f"Body keys: {list(body.keys())}, has 'event': {'event' in body}")
    logger.info(f"Raw body (first 500 chars): {json.dumps(body)[:500]}")

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
        logger.warning(f"Unknown event type: {event_type}. Full body: {json.dumps(body)}")
        raise ValueError(f"Unknown event type: {event_type}")

    logger.info(f"Successfully processed event: {event_type}")
    return result


def handle_patient_registered(body: Dict) -> Dict:
    """
    Handle patient.registered event.
    Creates: Family (Company), Parent (Guardian Contact), Child (Patient Contact).
    Does NOT create Deal - that happens later in the flow.
    """
    contact_data = body.get("contact", {})
    patient_data = body.get("patient", {})

    # 1. Create or update guardian contact (Parent)
    guardian_email = contact_data.get("email")
    guardian_properties = {
        "firstname": contact_data.get("first_name"),
        "lastname": contact_data.get("last_name"),
        "phone": contact_data.get("phone"),
        "state": contact_data.get("state"),
        "parent_external_id": contact_data.get("external_id"),
        "patient_relationship": "parent"
    }

    existing_guardian = hubspot.search_contact_by_external_id(contact_data.get("external_id"))
    if existing_guardian:
        guardian_id = existing_guardian["id"]
        guardian = hubspot.update_contact(guardian_id, guardian_properties)
        logger.info(f"Updated existing guardian contact: {guardian_id}")
    else:
        guardian = hubspot.create_contact(guardian_email, guardian_properties)
        guardian_id = guardian["id"]
        logger.info(f"Created new guardian contact: {guardian_id}")

    # 2. Create or update patient contact (Child) with synthetic email
    patient_external_id = patient_data.get("external_id")
    patient_email = hubspot.generate_synthetic_email(
        patient_data.get("first_name"),
        patient_data.get("last_name"),
        patient_external_id
    )

    patient_properties = {
        "firstname": patient_data.get("first_name"),
        "lastname": patient_data.get("last_name"),
        "patient_external_id": patient_external_id,
        "is_minor": "true" if patient_data.get("is_minor") else "false",
        "guardian_external_id": contact_data.get("external_id"),
        "date_of_birth": patient_data.get("date_of_birth"),
    }

    existing_patient = hubspot.search_contact_by_external_id(patient_external_id)
    if existing_patient:
        patient_id = existing_patient["id"]
        patient = hubspot.update_contact(patient_id, patient_properties)
        logger.info(f"Updated existing patient contact: {patient_id}")
    else:
        patient = hubspot.create_contact(patient_email, patient_properties)
        patient_id = patient["id"]
        logger.info(f"Created new patient contact: {patient_id}")

    # Associate guardian and patient (Parent ↔ Child)
    try:
        hubspot.create_contact_association(guardian_id, patient_id)
        logger.info(f"Associated guardian {guardian_id} with patient {patient_id}")
    except Exception as e:
        logger.warning(f"Contact association may already exist: {str(e)}")

    # 3. Create company (Family)
    guardian_last_name = contact_data.get("last_name")
    family_name = f"The {guardian_last_name} Family"
    family_external_id = contact_data.get("external_id")

    company_properties = {
        "family_external_id": family_external_id
    }

    existing_company = hubspot.search_company_by_external_id(family_external_id)
    if existing_company:
        company_id = existing_company["id"]
        company = hubspot.update_company(company_id, company_properties)
        logger.info(f"Updated existing company: {company_id}")
    else:
        company = hubspot.create_company(family_name, company_properties)
        company_id = company["id"]
        logger.info(f"Created new company: {company_id}")

    # Associate company with guardian and patient (Family ↔ Parent, Family ↔ Child)
    try:
        hubspot.associate_company_to_contact(company_id, guardian_id)
        hubspot.associate_company_to_contact(company_id, patient_id)
        logger.info(f"Associated company {company_id} with contacts")
    except Exception as e:
        logger.warning(f"Company-contact associations may already exist: {str(e)}")

    return {
        "company_id": company_id,
        "guardian_id": guardian_id,
        "patient_id": patient_id,
        "family_name": family_name,
        "message": "Registration complete: Family, Parent, and Child created"
    }


if __name__ == "__main__":
    import json
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
    from test_data_helper import get_or_generate_test_data, build_registration_event

    # Get or generate consistent test data
    data = get_or_generate_test_data()
    test_event = build_registration_event(data)

    print("Testing lambda_registration with patient registration event...")
    print(f"Guardian: {data['first_name']} {data['last_name']} ({data['email']})")
    print(f"Patient: {data['child_name']} {data['last_name']}")
    print(f"Guardian ID: {data['guardian_id']}")
    print(f"Patient ID: {data['patient_id']}")
    print(f"Event type: {test_event.get('event', {}).get('type')}")
    print("-" * 80)

    result = lambda_handler(test_event, None)

    print("-" * 80)
    print("Result:")
    print(json.dumps(result, indent=2))
