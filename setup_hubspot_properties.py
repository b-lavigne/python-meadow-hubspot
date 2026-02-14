"""
Script to create custom properties in HubSpot for Meadow Bio integration.
Run this once before deploying the Lambda functions.

Usage: python setup_hubspot_properties.py
"""

import os
import requests
import json

# Load environment variables
HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY")

if not HUBSPOT_API_KEY:
    print("ERROR: HUBSPOT_API_KEY environment variable not set")
    print("Run: export $(cat .env | xargs)")
    exit(1)

HUBSPOT_BASE_URL = "https://api.hubapi.com"

headers = {
    "Authorization": f"Bearer {HUBSPOT_API_KEY}",
    "Content-Type": "application/json"
}

# Define custom contact properties
CONTACT_PROPERTIES = [
    {
        "name": "parent_external_id",
        "label": "Parent External ID",
        "type": "string",
        "fieldType": "text",
        "groupName": "contactinformation",
        "description": "External ID from the patient portal for the parent/guardian"
    },
    {
        "name": "patient_external_id",
        "label": "Patient External ID",
        "type": "string",
        "fieldType": "text",
        "groupName": "contactinformation",
        "description": "External ID from the patient portal for the patient"
    },
    {
        "name": "guardian_external_id",
        "label": "Guardian External ID",
        "type": "string",
        "fieldType": "text",
        "groupName": "contactinformation",
        "description": "External ID of the patient's guardian"
    },
    {
        "name": "patient_relationship",
        "label": "Patient Relationship",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "Relationship to patient",
        "options": [
            {"label": "Parent", "value": "parent"},
            {"label": "Guardian", "value": "guardian"},
            {"label": "Self", "value": "self"}
        ]
    },
    {
        "name": "is_minor",
        "label": "Is Minor",
        "type": "enumeration",
        "fieldType": "booleancheckbox",
        "groupName": "contactinformation",
        "description": "Whether this patient is a minor",
        "options": [
            {"label": "Yes", "value": "true"},
            {"label": "No", "value": "false"}
        ]
    },
    {
        "name": "registration_status",
        "label": "Registration Status",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "Patient registration status",
        "options": [
            {"label": "Started", "value": "started"},
            {"label": "Complete", "value": "complete"}
        ]
    },
    {
        "name": "intake_status",
        "label": "Intake Status",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "Patient intake questionnaire status",
        "options": [
            {"label": "Not Started", "value": "not_started"},
            {"label": "In Progress", "value": "in_progress"},
            {"label": "Complete", "value": "complete"},
            {"label": "Abandoned", "value": "abandoned"}
        ]
    },
    {
        "name": "intake_completion_pct",
        "label": "Intake Completion %",
        "type": "number",
        "fieldType": "number",
        "groupName": "contactinformation",
        "description": "Percentage of intake questionnaire completed (0-100)"
    },
    {
        "name": "intake_abandoned_at",
        "label": "Intake Abandoned At",
        "type": "datetime",
        "fieldType": "date",
        "groupName": "contactinformation",
        "description": "When the intake was abandoned"
    },
    {
        "name": "payment_status",
        "label": "Payment Status",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "Payment status",
        "options": [
            {"label": "Active", "value": "active"},
            {"label": "Failed", "value": "failed"},
            {"label": "Pending", "value": "pending"}
        ]
    },
    {
        "name": "subscription_status",
        "label": "Subscription Status",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "Subscription status",
        "options": [
            {"label": "None", "value": "none"},
            {"label": "Active", "value": "active"},
            {"label": "Paused", "value": "paused"},
            {"label": "Canceled", "value": "canceled"}
        ]
    },
    {
        "name": "cancellation_reason",
        "label": "Cancellation Reason",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "Reason for subscription cancellation",
        "options": [
            {"label": "Cost", "value": "cost"},
            {"label": "Side Effects", "value": "side_effects"},
            {"label": "Not Effective", "value": "not_effective"},
            {"label": "Other", "value": "other"}
        ]
    }
]

# Define custom company properties
COMPANY_PROPERTIES = [
    {
        "name": "family_external_id",
        "label": "Family External ID",
        "type": "string",
        "fieldType": "text",
        "groupName": "companyinformation",
        "description": "External ID from patient portal for the family/household"
    }
]

# Define custom deal properties
DEAL_PROPERTIES = [
    {
        "name": "patient_external_id",
        "label": "Patient External ID",
        "type": "string",
        "fieldType": "text",
        "groupName": "dealinformation",
        "description": "External ID of the patient this deal tracks"
    },
    {
        "name": "subscription_external_id",
        "label": "Subscription External ID",
        "type": "string",
        "fieldType": "text",
        "groupName": "dealinformation",
        "description": "External subscription ID from patient portal (set when order created)"
    },
    {
        "name": "next_refill_date",
        "label": "Next Refill Date",
        "type": "date",
        "fieldType": "date",
        "groupName": "dealinformation",
        "description": "Date of next medication refill"
    },
    {
        "name": "last_payment_date",
        "label": "Last Payment Date",
        "type": "date",
        "fieldType": "date",
        "groupName": "dealinformation",
        "description": "Date of last successful payment"
    },
    {
        "name": "mrr",
        "label": "MRR",
        "type": "number",
        "fieldType": "number",
        "groupName": "dealinformation",
        "description": "Monthly Recurring Revenue"
    },
    {
        "name": "product_name",
        "label": "Product Name",
        "type": "string",
        "fieldType": "text",
        "groupName": "dealinformation",
        "description": "Name of the product/treatment"
    }
]


def create_property(object_type, property_def):
    """Create a custom property in HubSpot."""
    url = f"{HUBSPOT_BASE_URL}/crm/v3/properties/{object_type}"

    response = requests.post(url, headers=headers, json=property_def)

    if response.status_code == 201:
        print(f"✓ Created {object_type} property: {property_def['name']}")
        return True
    elif response.status_code == 409:
        print(f"⊘ Property already exists: {property_def['name']}")
        return True
    else:
        print(f"✗ Failed to create {property_def['name']}: {response.status_code} - {response.text}")
        return False


def main():
    print("=" * 80)
    print("Creating HubSpot Custom Properties for Meadow Bio")
    print("=" * 80)
    print()

    print("Creating Company Properties...")
    print("-" * 80)
    company_success = 0
    for prop in COMPANY_PROPERTIES:
        if create_property("companies", prop):
            company_success += 1

    print()
    print("Creating Contact Properties...")
    print("-" * 80)
    contact_success = 0
    for prop in CONTACT_PROPERTIES:
        if create_property("contacts", prop):
            contact_success += 1

    print()
    print("Creating Deal Properties...")
    print("-" * 80)
    deal_success = 0
    for prop in DEAL_PROPERTIES:
        if create_property("deals", prop):
            deal_success += 1

    print()
    print("=" * 80)
    print(f"Summary: {company_success}/{len(COMPANY_PROPERTIES)} company properties, {contact_success}/{len(CONTACT_PROPERTIES)} contact properties, {deal_success}/{len(DEAL_PROPERTIES)} deal properties")
    print("=" * 80)

    if company_success == len(COMPANY_PROPERTIES) and contact_success == len(CONTACT_PROPERTIES) and deal_success == len(DEAL_PROPERTIES):
        print("✓ All properties created successfully!")
        print("\nYou can now run the Lambda functions.")
    else:
        print("⚠ Some properties failed to create. Check the errors above.")


if __name__ == "__main__":
    main()
