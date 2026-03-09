"""
Lambda function to handle contact-related webhook events.
Processes patient registration and intake events, creating and updating contacts in HubSpot.
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
    Main Lambda handler for contact events.
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
            result = handle_registration_started(body)
        elif event_type == "intake.started":
            result = handle_intake_started(body)
        elif event_type == "intake.abandoned":
            result = handle_intake_abandoned(body)
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


def handle_registration_started(body: Dict) -> Dict:
    """
    Handle patient.registration_started event.
    Creates guardian contact and patient contact, then associates them.
    """
    contact_data = body.get("contact", {})
    patient_data = body.get("patient", {})

    # Create or update guardian contact
    guardian_email = contact_data.get("email")
    guardian_properties = {
        "firstname": contact_data.get("first_name"),
        "lastname": contact_data.get("last_name"),
        "phone": contact_data.get("phone"),
        "state": contact_data.get("state"),
        "parent_external_id": contact_data.get("external_id"),
        "patient_relationship": "parent"
    }

    # Check if guardian already exists
    existing_guardian = hubspot.search_contact_by_external_id(contact_data.get("external_id"))
    if existing_guardian:
        guardian_id = existing_guardian["id"]
        guardian = hubspot.update_contact(guardian_id, guardian_properties)
        logger.info(f"Updated existing guardian contact: {guardian_id}")
    else:
        guardian = hubspot.create_contact(guardian_email, guardian_properties)
        guardian_id = guardian["id"]
        logger.info(f"Created new guardian contact: {guardian_id}")

    # Create or update patient contact with synthetic email
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

    # Check if patient already exists
    existing_patient = hubspot.search_contact_by_external_id(patient_external_id)
    if existing_patient:
        patient_id = existing_patient["id"]
        patient = hubspot.update_contact(patient_id, patient_properties)
        logger.info(f"Updated existing patient contact: {patient_id}")
    else:
        patient = hubspot.create_contact(patient_email, patient_properties)
        patient_id = patient["id"]
        logger.info(f"Created new patient contact: {patient_id}")

    # Create parent-child association
    try:
        hubspot.create_contact_association(guardian_id, patient_id)
        logger.info(f"Associated guardian {guardian_id} with patient {patient_id}")
    except Exception as e:
        logger.warning(f"Association may already exist: {str(e)}")

    return {
        "guardian_id": guardian_id,
        "patient_id": patient_id,
        "message": "Patient contact created and associated with guardian"
    }


def handle_registration_completed(body: Dict) -> Dict:
    """
    Handle patient.registration_completed event.
    Updates both guardian and patient contacts with registration_status = complete.
    """
    contact_data = body.get("contact", {})
    patient_data = body.get("patient", {})

    # Update guardian contact
    guardian = hubspot.search_contact_by_external_id(contact_data.get("external_id"))
    if guardian:
        hubspot.update_contact(guardian["id"], {"registration_status": "complete"})
        logger.info(f"Updated guardian registration status: {guardian['id']}")

    # Update patient contact
    patient = hubspot.search_contact_by_external_id(patient_data.get("external_id"))
    if patient:
        hubspot.update_contact(patient["id"], {"registration_status": "complete"})
        logger.info(f"Updated patient registration status: {patient['id']}")

    return {
        "message": "Registration completed - statuses updated"
    }


def handle_intake_started(body: Dict) -> Dict:
    """
    Handle intake.started event.
    Updates patient contact with intake_status and completion percentage.
    """
    patient_data = body.get("patient", {})
    context = body.get("context", {})

    patient = hubspot.search_contact_by_external_id(patient_data.get("external_id"))
    if not patient:
        raise Exception(f"Patient not found: {patient_data.get('external_id')}")

    properties = {
        "intake_status": "in_progress",
        "intake_completion_pct": context.get("completion_pct", 0)
    }

    hubspot.update_contact(patient["id"], properties)
    logger.info(f"Updated patient intake status: {patient['id']}")

    return {
        "patient_id": patient["id"],
        "message": "Intake started"
    }


def handle_intake_abandoned(body: Dict) -> Dict:
    """
    Handle intake.abandoned event.
    Updates patient contact with intake_status = abandoned and completion percentage.
    """
    patient_data = body.get("patient", {})
    context = body.get("context", {})

    patient = hubspot.search_contact_by_external_id(patient_data.get("external_id"))
    if not patient:
        raise Exception(f"Patient not found: {patient_data.get('external_id')}")

    properties = {
        "intake_status": "abandoned",
        "intake_completion_pct": context.get("completion_pct", 0),
        "intake_abandoned_at": body.get("event", {}).get("timestamp")
    }

    hubspot.update_contact(patient["id"], properties)
    logger.info(f"Updated patient intake abandoned: {patient['id']}")

    return {
        "patient_id": patient["id"],
        "message": "Intake abandoned"
    }


if __name__ == "__main__":
    import json
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

    print("Testing lambda_contact with patient registration event...")
    print(f"Guardian: {first_name} {last_name} ({email})")
    print(f"Patient: {child_name} {last_name}")
    print(f"Event type: {test_event.get('event', {}).get('type')}")
    print("-" * 80)

    result = lambda_handler(test_event, None)

    print("-" * 80)
    print("Result:")
    print(json.dumps(result, indent=2))