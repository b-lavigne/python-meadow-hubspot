"""
Helper to manage consistent test data across lambda functions.
Ensures all lambdas use the same IDs so they can find each other's created objects.
"""

import json
import os
import random
from datetime import datetime

try:
    from faker import Faker
    fake = Faker()
    USE_FAKER = True
except ImportError:
    USE_FAKER = False
    print("WARNING: Faker library not installed. Using basic random names.")
    print("Install with: pip install faker")

TEST_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.test_data.json')


def get_or_generate_test_data():
    """
    Load existing test data or generate new random data.
    This ensures all lambda test runs use the same IDs within a test session.
    """
    # Try to load existing test data first
    if os.path.exists(TEST_DATA_FILE):
        try:
            with open(TEST_DATA_FILE, 'r') as f:
                data = json.load(f)
                print(f"✓ Using existing test data from {TEST_DATA_FILE}")
                print(f"  Guardian: {data['first_name']} {data['last_name']} (ID: {data['guardian_id']})")
                print(f"  Patient: {data['child_name']} (ID: {data['patient_id']})")
                return data
        except Exception as e:
            print(f"Warning: Could not load test data: {e}")

    # Generate new random test data if file doesn't exist
    # Valid US states for HubSpot
    VALID_STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
                    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
                    "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
                    "WV", "WI", "WY"]

    if USE_FAKER:
        # Use Faker for truly random realistic names
        first_name = fake.first_name()
        last_name = fake.last_name()
        child_name = fake.first_name()
        state = random.choice(VALID_STATES)  # Use valid US states only
    else:
        # Fallback to basic random selection
        FIRST_NAMES = ["Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "William",
                       "Charlotte", "James", "Amelia", "Benjamin", "Harper", "Lucas", "Evelyn", "Henry", "Abigail", "Alexander"]
        LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                      "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
        CHILD_FIRST_NAMES = ["Tommy", "Lily", "Max", "Sophie", "Jake", "Emma", "Oliver", "Chloe", "Lucas", "Mia",
                            "Ethan", "Ava", "Noah", "Isabella", "Liam", "Sophia", "Mason", "Charlotte", "Logan", "Amelia"]
        STATES = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "MI", "NC", "GA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI", "CO", "MN"]

        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        child_name = random.choice(CHILD_FIRST_NAMES)
        state = random.choice(STATES)

    data = {
        "guardian_id": f"{random.randint(100000, 999999)}-",
        "patient_id": str(random.randint(10, 99)),
        "first_name": first_name,
        "last_name": last_name,
        "child_name": child_name,
        "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
        "phone": f"1{random.randint(2000000000, 9999999999)}",
        "state": state
    }

    # Save for future runs
    try:
        with open(TEST_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Generated and saved new test data to {TEST_DATA_FILE}")
    except Exception as e:
        print(f"Warning: Could not save test data: {e}")

    return data


def reset_test_data():
    """Delete the test data file to force generation of new random data."""
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)
        print(f"✓ Deleted test data file: {TEST_DATA_FILE}")
        print("  Next test run will generate new random data")
    else:
        print(f"  No test data file found at {TEST_DATA_FILE}")


def build_registration_event(data):
    """Build a patient.registered event from test data."""
    guardian_num = int(data["guardian_id"].rstrip('-'))

    return {
        "event": {
            "type": "patient.registered",
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "patient_portal",
            "idempotency_key": f"evt_reg_usr{random.randint(10, 99)}"
        },
        "contact": {
            "external_id": data["guardian_id"],
            "email": data["email"],
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "phone": data["phone"],
            "state": data["state"],
            "domain_slug": "foothillsderm.com"
        },
        "patient": {
            "external_id": data["patient_id"],
            "first_name": data["child_name"],
            "last_name": data["last_name"],
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


def build_order_created_event(data):
    """Build an order.created event from test data."""
    guardian_num = int(data["guardian_id"].rstrip('-'))
    order_id = random.randint(100, 999)

    PRODUCTS = [
        {"id": 12, "name": "Autism Treatment", "enum": "AUTISM", "price": 9900},
        {"id": 13, "name": "ADHD Treatment", "enum": "ADHD", "price": 8900},
        {"id": 14, "name": "Anxiety Treatment", "enum": "ANXIETY", "price": 7900}
    ]
    product = random.choice(PRODUCTS)

    return {
        "event": {
            "type": "order.created",
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "patient_portal",
            "idempotency_key": f"evt_ord_{order_id}_{random.randint(100, 999)}"
        },
        "contact": {
            "external_id": data["guardian_id"],
            "email": data["email"],
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "phone": data["phone"]
        },
        "patient": {
            "external_id": data["patient_id"],
            "first_name": data["child_name"],
            "last_name": data["last_name"],
            "is_minor": True,
            "guardian_id": guardian_num
        },
        "orders": [
            {
                "external_id": str(order_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "product_enum": product["enum"],
                "billing_period": "MONTHLT",
                "price_in_cents": product["price"],
                "is_paid": True
            }
        ],
        "context": {}
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset_test_data()
    else:
        data = get_or_generate_test_data()
        print("\nTest Data:")
        print(json.dumps(data, indent=2))

        print("\n\nRegistration Event:")
        print(json.dumps(build_registration_event(data), indent=2))

        print("\n\nOrder Created Event:")
        print(json.dumps(build_order_created_event(data), indent=2))
