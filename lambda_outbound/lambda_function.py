"""
lambda_outbound
================
Handles all outbound events from the patient portal → HubSpot.

Receives POST /events from API Gateway (API key auth) and processes
all event types in a single Lambda — no SQS routing required.

Event types handled:
  patient.registered     — create guardian contact, patient contact, family company, initial deal
  intake.started         — update contact + move deal to intake_in_progress
  intake.abandoned       — update contact + move deal to intake_abandoned
  checkout.abandoned     — move deal to checkout_abandoned
  order.created          — move deal to active_subscriber, set MRR / product
  payment.succeeded      — update last_payment_date on deal
  subscription.created   — move deal to active_subscriber
  subscription.canceled  — move deal to subscriptionended
"""

import json
import logging

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

import hubspot

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    # SQS trigger — process batch of messages from hubspot-sync queue
    if "Records" in event:
        return _handle_sqs_batch(event)

    # API Gateway trigger — existing direct HTTP flow
    logger.info("Received event: %s", json.dumps(event))

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON body: %s", e)
        return _response(400, {"error": "Invalid JSON body"})

    evt  = body.get("event", {})
    evt_type = evt.get("type", "")

    logger.info("Processing event type: %s", evt_type)

    try:
        handler = _ROUTES.get(evt_type)
        if handler is None:
            logger.warning("Unhandled event type: %s", evt_type)
            return _response(200, {"status": "ignored", "event_type": evt_type})

        handler(body)
        return _response(200, {"status": "ok", "event_type": evt_type})

    except Exception as e:
        logger.error("Failed to process %s: %s", evt_type, e, exc_info=True)
        return _response(500, {"error": str(e), "event_type": evt_type})


def _handle_sqs_batch(event):
    """Process SQS messages from the hubspot-sync queue."""
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "")
        try:
            body = json.loads(record["body"])
            event_type = body.get("event_type", "")
            logger.info("SQS event_type=%s message_id=%s", event_type, message_id)

            handler = _SQS_ROUTES.get(event_type)
            if handler is None:
                logger.info("Unhandled SQS event_type=%s — acknowledging", event_type)
                continue

            handler(body)
            logger.info("Completed SQS event_type=%s message_id=%s", event_type, message_id)
        except Exception as e:
            logger.error("Failed SQS message_id=%s: %s", message_id, e, exc_info=True)
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_registration(body):
    """
    patient.registered — create/update guardian + patient contacts, family company,
    parent-child association, and the initial deal in 'registration' stage.
    """
    contact = body.get("contact", {})
    patient = body.get("patient", {})
    hutk    = body.get("context", {}).get("hutk", "")

    guardian_ext_id = str(contact.get("external_id", ""))
    patient_ext_id  = str(patient.get("external_id", ""))

    # --- Guardian contact ---
    guardian_props = {
        "firstname":           contact.get("first_name", ""),
        "lastname":            contact.get("last_name", ""),
        "email":               contact.get("email", ""),
        "phone":               contact.get("phone", ""),
        "state":               contact.get("state", ""),
        "parent_external_id":  guardian_ext_id,
        "contact_type":        "guardian",
    }
    existing_guardian = hubspot.search_contact_by_external_id(guardian_ext_id)
    if existing_guardian:
        guardian_id = existing_guardian["id"]
        hubspot.update_contact(guardian_id, guardian_props)
        logger.info("Updated guardian contact %s", guardian_id)
    else:
        guardian_id = hubspot.create_contact(contact.get("email", ""), guardian_props)
        logger.info("Created guardian contact %s", guardian_id)

    # Link anonymous browsing session to guardian contact via hutk
    if hutk and contact.get("email"):
        try:
            hubspot.create_or_update_contact_with_hutk(contact["email"], guardian_props, hutk)
            logger.info("Linked hutk to guardian contact %s", guardian_id)
        except Exception as e:
            logger.warning("Failed to link hutk (non-fatal): %s", e)

    # --- Patient contact (synthetic email for minors) ---
    patient_email = hubspot.generate_synthetic_email(
        patient.get("first_name", ""),
        patient.get("last_name", ""),
        patient_ext_id,
    )
    patient_props = {
        "firstname":              patient.get("first_name", ""),
        "lastname":               patient.get("last_name", ""),
        "email":                  patient_email,
        "date_of_birth":          str(patient.get("date_of_birth", "")),
        "patient_external_id":    patient_ext_id,
        "contact_type":           "patient",
        "registration_status":    "registered",
    }
    existing_patient = hubspot.search_contact_by_external_id(patient_ext_id)
    if existing_patient:
        patient_id = existing_patient["id"]
        hubspot.update_contact(patient_id, patient_props)
        logger.info("Updated patient contact %s", patient_id)
    else:
        patient_id = hubspot.create_contact(patient_email, patient_props)
        logger.info("Created patient contact %s", patient_id)

    # --- Family company ---
    family_ext_id = guardian_ext_id  # one company per guardian
    company_name  = f"{contact.get('last_name', '')} Family"
    existing_company = hubspot.search_company_by_external_id(family_ext_id)
    if existing_company:
        company_id = existing_company["id"]
    else:
        company_id = hubspot.create_company(company_name, {
            "family_external_id": family_ext_id,
        })
        logger.info("Created family company %s", company_id)

    # --- Associations ---
    hubspot.create_contact_association(guardian_id, patient_id)
    hubspot.associate_company_to_contact(company_id, guardian_id)
    hubspot.associate_company_to_contact(company_id, patient_id)

    # --- Initial deal (registration stage) ---
    deal_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')} Journey"
    existing_deal = hubspot.search_deal_by_patient_id(patient_ext_id)
    if existing_deal:
        deal_id = existing_deal["id"]
        hubspot.update_deal(deal_id, {"dealstage": "registration"})
    else:
        deal_id = hubspot.create_deal(deal_name, {
            "dealstage":           "registration",
            "patient_external_id": patient_ext_id,
            "pipeline":            "default",
        })
        logger.info("Created deal %s", deal_id)

    hubspot.associate_deal_to_contact(deal_id, guardian_id)
    hubspot.associate_deal_to_contact(deal_id, patient_id)
    hubspot.associate_company_to_deal(company_id, deal_id)


def _handle_intake_started(body):
    patient = body.get("patient", {})
    patient_ext_id = str(patient.get("external_id", ""))

    existing = hubspot.search_contact_by_external_id(patient_ext_id)
    if existing:
        hubspot.update_contact(existing["id"], {"intake_status": "started"})

    deal = hubspot.search_deal_by_patient_id(patient_ext_id)
    if deal:
        hubspot.update_deal(deal["id"], {"dealstage": "intake_in_progress"})


def _handle_intake_abandoned(body):
    patient = body.get("patient", {})
    patient_ext_id = str(patient.get("external_id", ""))

    existing = hubspot.search_contact_by_external_id(patient_ext_id)
    if existing:
        hubspot.update_contact(existing["id"], {"intake_status": "abandoned"})

    deal = hubspot.search_deal_by_patient_id(patient_ext_id)
    if deal:
        hubspot.update_deal(deal["id"], {"dealstage": "intake_abandoned"})


def _handle_checkout_abandoned(body):
    patient = body.get("patient", {})
    patient_ext_id = str(patient.get("external_id", ""))

    deal = hubspot.search_deal_by_patient_id(patient_ext_id)
    if deal:
        hubspot.update_deal(deal["id"], {"dealstage": "checkoutincomplete"})
    else:
        logger.warning("No deal found for checkout.abandoned event, patient_id=%s", patient_ext_id)


def _handle_order_created(body):
    patient        = body.get("patient", {})
    patient_ext_id = str(patient.get("external_id", ""))
    evt            = body.get("event", {})
    hutk           = body.get("context", {}).get("hutk", "")

    subscription_id = str(evt.get("subscription_id", ""))
    mrr             = evt.get("mrr", 0)
    product_name    = evt.get("product_name", "")
    amount          = evt.get("amount", mrr)

    deal = hubspot.search_deal_by_patient_id(patient_ext_id)
    if not deal:
        logger.warning("No deal found for order.created, patient_id=%s — creating", patient_ext_id)
        deal_id = hubspot.create_deal(f"Patient {patient_ext_id} Journey", {
            "dealstage":           "active_subscriber",
            "patient_external_id": patient_ext_id,
            "pipeline":            "default",
        })
    else:
        deal_id = deal["id"]

    hubspot.update_deal(deal_id, {
        "dealstage":               "active_subscriber",
        "subscription_external_id": subscription_id,
        "mrr":                     str(mrr),
        "product_name":            product_name,
        "amount":                  str(amount),
    })

    # Link anonymous browsing session to guardian contact via hutk
    contact_email = body.get("contact", {}).get("email", "")
    if hutk and contact_email:
        try:
            hubspot.create_or_update_contact_with_hutk(contact_email, {}, hutk)
            logger.info("Linked hutk to guardian on order.created")
        except Exception as e:
            logger.warning("Failed to link hutk on order (non-fatal): %s", e)


def _handle_payment_succeeded(body):
    evt             = body.get("event", {})
    subscription_id = str(evt.get("subscription_id", ""))
    mrr             = evt.get("mrr", 0)

    deal = hubspot.search_deal_by_external_id(subscription_id)
    if deal:
        hubspot.update_deal(deal["id"], {
            "last_payment_date": evt.get("timestamp", ""),
            "mrr":               str(mrr),
        })
    else:
        logger.warning("No deal found for payment.succeeded, subscription_id=%s", subscription_id)


def _handle_subscription_created(body):
    patient        = body.get("patient", {})
    patient_ext_id = str(patient.get("external_id", ""))
    evt            = body.get("event", {})
    subscription_id = str(evt.get("subscription_id", ""))

    deal = hubspot.search_deal_by_patient_id(patient_ext_id)
    if deal:
        hubspot.update_deal(deal["id"], {
            "dealstage":               "active_subscriber",
            "subscription_external_id": subscription_id,
        })


def _handle_subscription_canceled(body):
    evt             = body.get("event", {})
    subscription_id = str(evt.get("subscription_id", ""))

    deal = hubspot.search_deal_by_external_id(subscription_id)
    if deal:
        hubspot.update_deal(deal["id"], {"dealstage": "subscriptionended"})
    else:
        logger.warning("No deal for subscription.canceled, subscription_id=%s", subscription_id)


# ---------------------------------------------------------------------------
# SQS Handlers (async events from python-meadowbio-app)
# ---------------------------------------------------------------------------

def _handle_order_sync(body):
    """
    HUBSPOT_ORDER_CREATED — link hutk visitor session to guardian contact
    on order creation and advance deal to active_subscriber.

    Payload (from meadow-api-orders handle_create_order):
        user_id, email, patient_id, order_id, subscription_plan, hutk
    """
    payload           = body.get("payload", {})
    email             = payload.get("email", "")
    patient_ext_id    = payload.get("patient_id", "")
    subscription_plan = payload.get("subscription_plan", "")
    hutk              = payload.get("hutk", "")

    deal = hubspot.search_deal_by_patient_id(patient_ext_id)
    if deal:
        hubspot.update_deal(deal["id"], {
            "dealstage":         "active_subscriber",
            "subscription_plan": subscription_plan,
        })

    # Link anonymous browsing session to guardian contact via hutk
    if hutk and email:
        try:
            hubspot.create_or_update_contact_with_hutk(email, {}, hutk)
            logger.info("Linked hutk to guardian on HUBSPOT_ORDER_CREATED email=%s", email[:4] + "***")
        except Exception as e:
            logger.warning("Failed to link hutk on order (non-fatal): %s", e)

    logger.info(
        "HUBSPOT_ORDER_CREATED complete patient_id=%s hutk_present=%s",
        patient_ext_id, bool(hutk),
    )

def _handle_contact_sync(body):
    """
    HUBSPOT_CONTACT_SYNC — create guardian contact, family company,
    associations, and hutk linking.

    Payload (from meadow-api-auth registration):
        user_id, email, first_name, last_name, phone, role, hutk
    """
    payload   = body.get("payload", {})
    email     = payload.get("email", "")
    first_name = payload.get("first_name", "")
    last_name  = payload.get("last_name", "")
    phone      = payload.get("phone", "")
    user_id    = payload.get("user_id", "")
    hutk       = payload.get("hutk", "")

    # --- Guardian contact ---
    guardian_props = {
        "firstname":           first_name,
        "lastname":            last_name,
        "email":               email,
        "phone":               phone,
        "registration_status": "complete",
        "meadow_funnel_stage": "registered",
        "lifecyclestage":      "marketingqualifiedlead",
        "contact_role":        "parent",
        "parent_external_id":  user_id,
    }

    existing = hubspot.search_contact_by_external_id(user_id)
    if existing:
        guardian_id = existing["id"]
        hubspot.update_contact(guardian_id, guardian_props)
        logger.info("Updated guardian contact %s", guardian_id)
    else:
        result = hubspot.create_contact(email, guardian_props)
        guardian_id = result["id"] if result else None
        logger.info("Created guardian contact %s", guardian_id)

    # --- Link hutk for visitor attribution ---
    if hutk and email:
        try:
            hubspot.create_or_update_contact_with_hutk(email, guardian_props, hutk)
            logger.info("Linked hutk to guardian contact %s", guardian_id)
        except Exception as e:
            logger.warning("Failed to link hutk (non-fatal): %s", e)

    # --- Family company ---
    company_name = f"The {last_name} Family"
    existing_company = hubspot.search_company_by_external_id(user_id)
    if existing_company:
        company_id = existing_company["id"]
    else:
        result = hubspot.create_company(company_name, {
            "family_external_id":  user_id,
            "meadow_caregiver_id": user_id,
        })
        company_id = result["id"] if result else None
        logger.info("Created family company %s", company_id)

    # --- Associations ---
    if guardian_id and company_id:
        hubspot.associate_company_to_contact(company_id, guardian_id)

    logger.info(
        "HUBSPOT_CONTACT_SYNC complete user_id=%s contact_id=%s company_id=%s",
        user_id, guardian_id, company_id,
    )


# ---------------------------------------------------------------------------
# Route tables
# ---------------------------------------------------------------------------

# API Gateway routes (direct webhook events)
_ROUTES = {
    "patient.registered":    _handle_registration,
    "intake.started":        _handle_intake_started,
    "intake.abandoned":      _handle_intake_abandoned,
    "checkout.abandoned":    _handle_checkout_abandoned,
    "order.created":         _handle_order_created,
    "payment.succeeded":     _handle_payment_succeeded,
    "subscription.created":  _handle_subscription_created,
    "subscription.canceled": _handle_subscription_canceled,
}

# SQS routes (async events from main app)
_SQS_ROUTES = {
    "HUBSPOT_CONTACT_SYNC":    _handle_contact_sync,
    "HUBSPOT_ORDER_CREATED":   _handle_order_sync,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(body),
    }
