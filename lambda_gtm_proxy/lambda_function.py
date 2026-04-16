"""
lambda_gtm_proxy — GTM behavioral event proxy to HubSpot workflows.

Receives frontend GTM events from the patient portal and forwards them
to the appropriate HubSpot workflow webhook URL based on event name prefix.

API Gateway: POST /api/event (byx2vgnsqd.execute-api.us-east-2.amazonaws.com)

Environment variables:
  ENVIRONMENT                   production | staging | local
  HUBSPOT_WEBHOOK_URL           fallback for unmatched events
  WEBHOOK_CTA_CLICK             click.get-started, click.join-*, click.sign-up, etc.
  WEBHOOK_NAV_CLICK             click.about, click.science, click.pricing, etc.
  WEBHOOK_CONTACT_CLICK         contact.*
  WEBHOOK_SOCIAL_CLICK          social.*
  WEBHOOK_SCROLL_DEPTH          scroll.*
  WEBHOOK_FAQ_TOGGLE            faq-toggle.*
  WEBHOOK_OUTBOUND_CLICK        outbound.*
  WEBHOOK_VIDEO_PLAY            video-play.*
  WEBHOOK_VIDEO_MIDPOINT        video-mid.*
  WEBHOOK_VIDEO_COMPLETE        video-end.*
  WEBHOOK_FORM_SUBMIT           form-submit.*
"""

import json
import logging
import os
from urllib.parse import urlparse

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
TIMEOUT = 5  # seconds for HubSpot webhook calls

ALLOWED_ORIGINS = [
    "https://meadowbiosciences.com",
    "https://www.meadowbiosciences.com",
    "https://app2.meadowbiosciences.com",  # patient portal
]

# Mapping of event name prefixes → env var name
# Order matters: more specific prefixes first
_PREFIX_TO_ENV: list[tuple[str, str]] = [
    ("click.get-started",   "WEBHOOK_CTA_CLICK"),
    ("click.join-",         "WEBHOOK_CTA_CLICK"),
    ("click.start-",        "WEBHOOK_CTA_CLICK"),
    ("click.sign-up",       "WEBHOOK_CTA_CLICK"),
    ("click.book-",         "WEBHOOK_CTA_CLICK"),
    ("click.schedule-",     "WEBHOOK_CTA_CLICK"),
    ("click.enroll",        "WEBHOOK_CTA_CLICK"),
    ("click.apply",         "WEBHOOK_CTA_CLICK"),
    ("click.about",         "WEBHOOK_NAV_CLICK"),
    ("click.science",       "WEBHOOK_NAV_CLICK"),
    ("click.pricing",       "WEBHOOK_NAV_CLICK"),
    ("click.faq",           "WEBHOOK_NAV_CLICK"),
    ("click.home",          "WEBHOOK_NAV_CLICK"),
    ("click.blog",          "WEBHOOK_NAV_CLICK"),
    ("contact.",            "WEBHOOK_CONTACT_CLICK"),
    ("social.",             "WEBHOOK_SOCIAL_CLICK"),
    ("scroll.",             "WEBHOOK_SCROLL_DEPTH"),
    ("faq-toggle.",         "WEBHOOK_FAQ_TOGGLE"),
    ("outbound.",           "WEBHOOK_OUTBOUND_CLICK"),
    ("video-play.",         "WEBHOOK_VIDEO_PLAY"),
    ("video-mid.",          "WEBHOOK_VIDEO_MIDPOINT"),
    ("video-end.",          "WEBHOOK_VIDEO_COMPLETE"),
    ("form-submit.",        "WEBHOOK_FORM_SUBMIT"),
]


def _get_webhook_url(event_name: str) -> str | None:
    """Return the webhook URL for the given event name, or fallback URL."""
    for prefix, env_var in _PREFIX_TO_ENV:
        if event_name.startswith(prefix):
            url = os.environ.get(env_var, "")
            if url:
                return url
    return os.environ.get("HUBSPOT_WEBHOOK_URL", "")


def _cors_headers(origin: str) -> dict:
    allowed = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]
    return {
        "Access-Control-Allow-Origin":  allowed,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age":       "86400",
    }


def _response(status_code: int, body: dict, origin: str = "") -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            **_cors_headers(origin),
        },
        "body": json.dumps(body),
    }


def lambda_handler(event: dict, context) -> dict:
    origin = (event.get("headers") or {}).get("origin") or \
             (event.get("headers") or {}).get("Origin") or ""

    # Handle CORS preflight
    http_method = (event.get("requestContext") or {}).get("httpMethod") or \
                  event.get("httpMethod") or ""
    if http_method == "OPTIONS":
        return _response(200, {}, origin)

    # Parse body
    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"}, origin)

    event_name = body.get("eventName") or body.get("event_name") or ""
    properties = body.get("properties") or {}

    if not event_name:
        return _response(400, {"error": "Missing eventName"}, origin)

    logger.info("Routing event: %s", event_name)

    webhook_url = _get_webhook_url(event_name)
    if not webhook_url:
        logger.info("No webhook URL configured for event: %s — discarding", event_name)
        return _response(200, {"forwarded": False, "reason": "no_route"}, origin)

    # Validate URL is HTTPS before forwarding
    parsed = urlparse(webhook_url)
    if parsed.scheme != "https":
        logger.error("Webhook URL is not HTTPS — refusing to forward event=%s", event_name)
        return _response(500, {"error": "Misconfigured webhook URL"}, origin)

    # Forward to HubSpot workflow webhook
    payload = {
        "eventName":   event_name,
        "properties":  properties,
        "environment": ENVIRONMENT,
    }

    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        logger.info(
            "Forwarded event=%s status=%d url=%s",
            event_name, resp.status_code, webhook_url,
        )
        return _response(200, {"forwarded": True, "eventName": event_name}, origin)

    except requests.exceptions.Timeout:
        logger.error("Webhook timeout event=%s url=%s", event_name, webhook_url)
        return _response(504, {"error": "Webhook timeout"}, origin)

    except Exception as exc:
        logger.error("Webhook forward failed event=%s: %s", event_name, str(exc))
        return _response(502, {"error": "Forward failed"}, origin)
