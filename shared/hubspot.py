"""
Shared HubSpot API operations for all Lambda functions.
Handles creating and updating contacts, deals, and tickets in HubSpot.
"""

import os
import requests
from typing import Dict, Optional, List


HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY")
HUBSPOT_BASE_URL = "https://api.hubapi.com"


def get_headers() -> Dict[str, str]:
    """Return headers for HubSpot API requests."""
    return {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type": "application/json"
    }


# ============================================================================
# CONTACT OPERATIONS
# ============================================================================

def search_contact_by_external_id(external_id: str) -> Optional[Dict]:
    """
    Search for a contact by external_id (tries both patient_external_id and parent_external_id).
    Returns contact data if found, None otherwise.
    """
    # Try patient_external_id first
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "patient_external_id",
                "operator": "EQ",
                "value": external_id
            }]
        }],
        "properties": ["email", "firstname", "lastname", "phone", "patient_external_id", "parent_external_id"]
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]

    # Try parent_external_id
    payload["filterGroups"][0]["filters"][0]["propertyName"] = "parent_external_id"
    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        return results[0] if results else None
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error: {response.status_code} - {response.text}")


def get_contact_by_email(email: str) -> Optional[Dict]:
    """
    Get a contact by email address.
    Returns contact data if found, None otherwise.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator": "EQ",
                "value": email
            }]
        }]
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        return results[0] if results else None
    else:
        return None


def create_contact(email: str, properties: Dict) -> Dict:
    """
    Create a new contact in HubSpot.
    Returns the created contact data including the HubSpot ID.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts"
    payload = {
        "properties": {
            "email": email,
            **properties
        }
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 201:
        return response.json()
    elif response.status_code == 409:
        # Contact already exists - try to get it
        return get_contact_by_email(email)
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        error_detail = ""
        try:
            error_json = response.json()
            if "message" in error_json:
                error_detail = f" - {error_json['message']}"
            if "validationResults" in error_json:
                error_detail += f"\nValidation errors: {error_json['validationResults']}"
        except:
            pass
        raise Exception(f"HubSpot API error creating contact: {response.status_code}{error_detail}\nPayload sent: {payload}")


def update_contact(contact_id: str, properties: Dict) -> Dict:
    """
    Update an existing contact in HubSpot.
    Returns the updated contact data.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{contact_id}"
    payload = {"properties": properties}

    response = requests.patch(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error updating contact: {response.status_code} - {response.text}")


def generate_synthetic_email(first_name: str, last_name: str, patient_id: str) -> str:
    """
    Generate a synthetic email for a minor patient.
    Pattern: {firstname}.{lastname}+p{patient_id}@meadowbio.com
    """
    first = first_name.lower().replace(" ", "")
    last = last_name.lower().replace(" ", "")
    return f"{first}.{last}+p{patient_id}@meadowbio.com"


# ============================================================================
# DEAL OPERATIONS
# ============================================================================

def search_deal_by_patient_id(patient_external_id: str) -> Optional[Dict]:
    """
    Search for a deal by patient_external_id custom property.
    Returns deal data if found, None otherwise.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "patient_external_id",
                "operator": "EQ",
                "value": patient_external_id
            }]
        }],
        "properties": ["dealname", "dealstage", "amount", "subscription_external_id", "mrr", "next_refill_date", "patient_external_id"]
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        return results[0] if results else None
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error: {response.status_code} - {response.text}")


def search_deal_by_external_id(external_id: str) -> Optional[Dict]:
    """
    Search for a deal by subscription_external_id custom property.
    Returns deal data if found, None otherwise.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "subscription_external_id",
                "operator": "EQ",
                "value": external_id
            }]
        }],
        "properties": ["dealname", "dealstage", "amount", "subscription_external_id", "mrr", "next_refill_date", "patient_external_id"]
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        return results[0] if results else None
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error: {response.status_code} - {response.text}")


def create_deal(dealname: str, properties: Dict) -> Dict:
    """
    Create a new deal in HubSpot.
    Returns the created deal data including the HubSpot ID.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals"
    payload = {
        "properties": {
            "dealname": dealname,
            **properties
        }
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 201:
        return response.json()
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error creating deal: {response.status_code} - {response.text}")


def update_deal(deal_id: str, properties: Dict) -> Dict:
    """
    Update an existing deal in HubSpot.
    Returns the updated deal data.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals/{deal_id}"
    payload = {"properties": properties}

    response = requests.patch(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error updating deal: {response.status_code} - {response.text}")


# ============================================================================
# TICKET OPERATIONS
# ============================================================================

def create_ticket(subject: str, properties: Dict) -> Dict:
    """
    Create a new ticket in HubSpot.
    Returns the created ticket data including the HubSpot ID.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/tickets"
    payload = {
        "properties": {
            "subject": subject,
            "hs_pipeline": "0",  # Default pipeline
            "hs_pipeline_stage": "1",  # New/Open
            **properties
        }
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 201:
        return response.json()
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error creating ticket: {response.status_code} - {response.text}")


# ============================================================================
# COMPANY OPERATIONS
# ============================================================================

def search_company_by_external_id(external_id: str) -> Optional[Dict]:
    """
    Search for a company by family_external_id custom property.
    Returns company data if found, None otherwise.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "family_external_id",
                "operator": "EQ",
                "value": external_id
            }]
        }],
        "properties": ["name", "family_external_id"]
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        return results[0] if results else None
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error: {response.status_code} - {response.text}")


def create_company(name: str, properties: Dict) -> Dict:
    """
    Create a new company in HubSpot.
    Returns the created company data including the HubSpot ID.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies"
    payload = {
        "properties": {
            "name": name,
            **properties
        }
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 201:
        return response.json()
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        error_detail = ""
        try:
            error_json = response.json()
            if "message" in error_json:
                error_detail = f" - {error_json['message']}"
            if "validationResults" in error_json:
                error_detail += f"\nValidation errors: {error_json['validationResults']}"
        except:
            pass
        raise Exception(f"HubSpot API error creating company: {response.status_code}{error_detail}\nPayload sent: {payload}")


def update_company(company_id: str, properties: Dict) -> Dict:
    """
    Update an existing company in HubSpot.
    Returns the updated company data.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/{company_id}"
    payload = {"properties": properties}

    response = requests.patch(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error updating company: {response.status_code} - {response.text}")


# ============================================================================
# ASSOCIATION OPERATIONS
# ============================================================================

def create_contact_association(parent_id: str, child_id: str) -> bool:
    """
    Create a generic association between two contacts.
    Using v3 API for simpler association creation.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{parent_id}/associations/contacts/{child_id}/contact_to_contact"

    response = requests.put(url, headers=get_headers())

    if response.status_code in [200, 201, 204]:
        return True
    elif response.status_code == 409:
        # Association already exists - this is fine
        return True
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error creating contact association: {response.status_code} - {response.text}")


def associate_deal_to_contact(deal_id: str, contact_id: str) -> bool:
    """
    Create an association between a deal and a contact.
    Using v3 API for simpler association creation.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/deal_to_contact"

    response = requests.put(url, headers=get_headers())

    if response.status_code in [200, 201, 204]:
        return True
    elif response.status_code == 409:
        # Association already exists - this is fine
        return True
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error creating deal association: {response.status_code} - {response.text}")


def associate_ticket_to_contact(ticket_id: str, contact_id: str) -> bool:
    """
    Create an association between a ticket and a contact.
    Using v3 API for simpler association creation.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/tickets/{ticket_id}/associations/contacts/{contact_id}/ticket_to_contact"

    response = requests.put(url, headers=get_headers())

    if response.status_code in [200, 201, 204]:
        return True
    elif response.status_code == 409:
        # Association already exists - this is fine
        return True
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error creating ticket association: {response.status_code} - {response.text}")


def associate_company_to_contact(company_id: str, contact_id: str) -> bool:
    """
    Create an association between a company and a contact.
    Using v3 API for simpler association creation.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/{company_id}/associations/contacts/{contact_id}/company_to_contact"

    response = requests.put(url, headers=get_headers())

    if response.status_code in [200, 201, 204]:
        return True
    elif response.status_code == 409:
        # Association already exists - this is fine
        return True
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error creating company-contact association: {response.status_code} - {response.text}")


def associate_company_to_deal(company_id: str, deal_id: str) -> bool:
    """
    Create an association between a company and a deal.
    Using v3 API for simpler association creation.
    """
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/{company_id}/associations/deals/{deal_id}/company_to_deal"

    response = requests.put(url, headers=get_headers())

    if response.status_code in [200, 201, 204]:
        return True
    elif response.status_code == 409:
        # Association already exists - this is fine
        return True
    elif response.status_code == 429:
        raise Exception("HubSpot rate limit exceeded")
    else:
        raise Exception(f"HubSpot API error creating company-deal association: {response.status_code} - {response.text}")
