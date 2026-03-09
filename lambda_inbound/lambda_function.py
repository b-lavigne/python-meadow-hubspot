"""
lambda_inbound
===============
Handles inbound HubSpot webhook events.

Receives POST /webhooks/hubspot from API Gateway (no API key — validated
via HMAC-SHA256 signature in X-HubSpot-Signature header).

HubSpot sends batches of up to 100 events per POST. This Lambda validates
the signature, logs each event, and processes property changes inline.
HubSpot requires a response within 5 seconds — we process synchronously
and return 200 immediately. If we need heavy processing later, add SQS back.
"""

import hashlib
import hmac
import json
import logging
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

import hubspot

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_HUBSPOT_CLIENT_SECRET = None


def lambda_handler(event, context):
    logger.info("Received HubSpot webhook")

    # --- Validate signature ---
    signature  = (event.get("headers") or {}).get("X-HubSpot-Signature", "")
    raw_body   = event.get("body") or ""

    if not _validate_signature(signature, raw_body):
        logger.warning("Invalid HubSpot signature — rejecting request")
        return _response(401, {"error": "Invalid signature"})

    # --- Parse events ---
    try:
        webhook_events = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in webhook body: %s", e)
        return _response(400, {"error": "Invalid JSON"})

    if not isinstance(webhook_events, list):
        webhook_events = [webhook_events]

    logger.info("Processing %d webhook event(s)", len(webhook_events))

    processed = 0
    errors    = 0

    for evt in webhook_events:
        try:
            _process_event(evt)
            processed += 1
        except Exception as e:
            logger.error("Error processing event %s: %s", evt.get("eventId"), e, exc_info=True)
            errors += 1

    # Always return 200 to HubSpot — retries happen at our discretion, not theirs
    return _response(200, {"processed": processed, "errors": errors})


# ---------------------------------------------------------------------------
# Event processing
# ---------------------------------------------------------------------------

def _process_event(evt):
    event_type   = evt.get("subscriptionType") or evt.get("eventType", "")
    object_id    = evt.get("objectId")
    property_name  = evt.get("propertyName")
    property_value = evt.get("propertyValue")

    logger.info(
        "HubSpot event: type=%s objectId=%s property=%s value=%s",
        event_type, object_id, property_name, property_value,
    )

    if "propertyChange" in event_type:
        _handle_property_change(evt, event_type, object_id, property_name, property_value)
    elif "creation" in event_type:
        _handle_creation(evt, event_type, object_id)
    elif "deletion" in event_type:
        _handle_deletion(evt, event_type, object_id)
    elif "associationChange" in event_type:
        _handle_association_change(evt)
    else:
        logger.info("No handler for event type: %s", event_type)


def _handle_property_change(evt, event_type, object_id, property_name, property_value):
    """
    Handle property change notifications from HubSpot.
    Extend this as needed to trigger internal workflows.
    """
    if "contact" in event_type:
        logger.info("Contact %s: %s changed to %s", object_id, property_name, property_value)
        # TODO: trigger email workflow, notify care team, update patient DB, etc.

    elif "deal" in event_type:
        logger.info("Deal %s: %s changed to %s", object_id, property_name, property_value)
        if property_name == "dealstage":
            logger.info("Deal %s moved to stage: %s", object_id, property_value)
            # TODO: trigger stage-specific actions (e.g. notify care team on active_subscriber)

    elif "company" in event_type:
        logger.info("Company %s: %s changed to %s", object_id, property_name, property_value)


def _handle_creation(evt, event_type, object_id):
    logger.info("Object created: type=%s id=%s", event_type, object_id)
    # TODO: sync newly created HubSpot objects back to internal DB if needed


def _handle_deletion(evt, event_type, object_id):
    logger.info("Object deleted: type=%s id=%s", event_type, object_id)
    # TODO: handle deletions (e.g. archive patient record, audit log)


def _handle_association_change(evt):
    logger.info("Association change: %s", json.dumps(evt))
    # TODO: handle association changes if needed


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------

def _validate_signature(signature: str, raw_body: str) -> bool:
    """
    Validate HubSpot HMAC-SHA256 signature.
    HubSpot signs: HMAC-SHA256(client_secret + raw_body)
    """
    if not signature:
        return False

    client_secret = _get_client_secret()
    if not client_secret:
        logger.warning("No HubSpot client secret configured — skipping signature validation")
        return True  # fail open in dev; tighten for prod

    expected = hmac.new(
        client_secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


def _get_client_secret() -> str:
    global _HUBSPOT_CLIENT_SECRET
    if _HUBSPOT_CLIENT_SECRET:
        return _HUBSPOT_CLIENT_SECRET

    # In prod, pull from Secrets Manager via the shared module's key
    _HUBSPOT_CLIENT_SECRET = hubspot.get_hubspot_api_key()
    return _HUBSPOT_CLIENT_SECRET


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(body),
    }
