"""
Generate randomized test data for webhook events.
Creates JSON files with random names, emails, and IDs.

Usage: python generate_test_data.py
"""

import json
import random
import uuid
from datetime import datetime, timedelta

# Random name pools
FIRST_NAMES = ["Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "William"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

CHILD_FIRST_NAMES = ["Tommy", "Lily", "Max", "Sophie", "Jake", "Emma", "Oliver", "Chloe", "Lucas", "Mia"]

PRODUCTS = [
    {"id": 12, "name": "Autism Treatment", "enum": "AUTISM", "price": 9900},
    {"id": 13, "name": "ADHD Treatment", "enum": "ADHD", "price": 8900},
    {"id": 14, "name": "Anxiety Treatment", "enum": "ANXIETY", "price": 7900}
]

STATES = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "MI", "NC", "GA"]


def generate_random_guardian():
    """Generate random guardian data."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    phone = f"+1{random.randint(2000000000, 9999999999)}"
    state = random.choice(STATES)
    external_id = f"{random.randint(100000, 999999)}-"

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "state": state,
        "external_id": external_id
    }


def generate_random_patient(guardian_external_id):
    """Generate random patient data."""
    first_name = random.choice(CHILD_FIRST_NAMES)
    external_id = str(random.randint(10, 99))

    return {
        "first_name": first_name,
        "external_id": external_id,
        "is_minor": True,
        "guardian_id": int(guardian_external_id.rstrip('-'))
    }


def generate_random_product():
    """Get random product."""
    return random.choice(PRODUCTS)


def generate_timestamp(days_offset=0):
    """Generate ISO timestamp."""
    dt = datetime.now() + timedelta(days=days_offset)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_patient_registered():
    """Generate patient.registered event."""
    guardian = generate_random_guardian()
    patient = generate_random_patient(guardian["external_id"])

    return {
        "event": {
            "type": "patient.registered",
            "timestamp": generate_timestamp(),
            "source": "patient_portal",
            "idempotency_key": f"evt_reg_{uuid.uuid4().hex[:8]}"
        },
        "contact": guardian,
        "patient": {
            **patient,
            "date_of_birth": "2015-03-15"
        },
        "context": {
            "funnel_step": "registration",
            "completion_pct": 100,
            "domain_slug": "meadowbio.com"
        }
    }


def generate_order_created(guardian_external_id, patient_external_id):
    """Generate order.created event."""
    guardian = generate_random_guardian()
    guardian["external_id"] = guardian_external_id

    patient = generate_random_patient(guardian_external_id)
    patient["external_id"] = patient_external_id

    product = generate_random_product()
    order_id = random.randint(100, 999)

    return {
        "event": {
            "type": "order.created",
            "timestamp": generate_timestamp(),
            "source": "patient_portal",
            "idempotency_key": f"evt_ord_{uuid.uuid4().hex[:8]}"
        },
        "contact": guardian,
        "patient": patient,
        "orders": [
            {
                "external_id": str(order_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "product_enum": product["enum"],
                "billing_period": "MONTHLY",
                "billing_frequency_in_weeks": 4,
                "price_in_cents": product["price"]
            }
        ],
        "context": {
            "funnel_step": "checkout_completed",
            "completion_pct": 100,
            "domain_slug": "meadowbio.com"
        }
    }


def main():
    print("=" * 80)
    print("Generating Randomized Test Data")
    print("=" * 80)
    print()

    # Generate patient.registered event
    registered_event = generate_patient_registered()
    guardian_id = registered_event["contact"]["external_id"]
    patient_id = registered_event["patient"]["external_id"]

    print(f"Guardian: {registered_event['contact']['first_name']} {registered_event['contact']['last_name']}")
    print(f"  Email: {registered_event['contact']['email']}")
    print(f"  External ID: {guardian_id}")
    print()
    print(f"Patient: {registered_event['patient']['first_name']}")
    print(f"  External ID: {patient_id}")
    print()

    # Save patient.registered
    with open("docs/json_objects/event_patient_register.json", "w") as f:
        json.dump(registered_event, f, indent=2)
    print("✓ Generated: docs/json_objects/event_patient_register.json")

    # Generate order.created event with same IDs
    order_event = generate_order_created(guardian_id, patient_id)

    print(f"Order: {order_event['orders'][0]['product_name']}")
    print(f"  Order ID: {order_event['orders'][0]['external_id']}")
    print(f"  Price: ${order_event['orders'][0]['price_in_cents'] / 100:.2f}")
    print()

    # Save order.created
    with open("docs/json_objects/event_order_created.json", "w") as f:
        json.dump(order_event, f, indent=2)
    print("✓ Generated: docs/json_objects/event_order_created.json")

    print()
    print("=" * 80)
    print("Test data generated successfully!")
    print("=" * 80)
    print()
    print("Run tests with:")
    print("  ./test_local.sh contact")
    print("  ./test_local.sh deal")
    print()
    print("Clean up with:")
    print("  ./test_local.sh cleanup")


if __name__ == "__main__":
    main()
