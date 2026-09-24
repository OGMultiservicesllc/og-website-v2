"""Thin wrapper around Square's official Python SDK (`square`, PyPI package `squareup`). Sandbox-only for
now — deliberately refuses to build a "production" client unless `SQUARE_ALLOW_PRODUCTION=1` is ALSO set,
a second explicit opt-in beyond `SQUARE_ENVIRONMENT=production`, so a mistyped env var can never silently
start moving real money (see docs/SQUARE_PRODUCTION_ACTIVATION.md for the real activation procedure).

Money is always integer cents (matches this project's existing `amount_cents` convention in
`TaxPriceRule`/`DlPriceRule` — never a float) and Square's own `Money.amount` is itself an integer in the
currency's smallest unit, so no conversion happens at the boundary."""

import hashlib
import hmac
import base64
import logging

from flask import current_app

logger = logging.getLogger("og_payments")


class SquareNotConfigured(Exception):
    pass


def is_configured():
    c = current_app.config
    return bool(c.get("SQUARE_ACCESS_TOKEN") and c.get("SQUARE_LOCATION_ID") and c.get("SQUARE_APPLICATION_ID"))


def is_sandbox():
    return (current_app.config.get("SQUARE_ENVIRONMENT") or "sandbox").strip().lower() != "production"


def location_id():
    return current_app.config.get("SQUARE_LOCATION_ID", "")


def application_id():
    """Safe to send to the browser — identifies the app to Square's Web Payments SDK, not a secret."""
    return current_app.config.get("SQUARE_APPLICATION_ID", "")


_client_cache = {}


def get_client():
    """A `square.Square` client bound to the configured environment. Cached per access token so repeated
    calls within one request don't re-build the HTTP client."""
    from square import Square
    from square.environment import SquareEnvironment

    if not is_configured():
        raise SquareNotConfigured("Square is not configured (SQUARE_ACCESS_TOKEN/LOCATION_ID/APPLICATION_ID missing).")
    env_name = (current_app.config.get("SQUARE_ENVIRONMENT") or "sandbox").strip().lower()
    if env_name == "production" and not current_app.config.get("SQUARE_ALLOW_PRODUCTION"):
        raise SquareNotConfigured(
            "SQUARE_ENVIRONMENT=production but SQUARE_ALLOW_PRODUCTION is not set — refusing to place a live "
            "charge. See docs/SQUARE_PRODUCTION_ACTIVATION.md before going live."
        )
    token = current_app.config["SQUARE_ACCESS_TOKEN"]
    cached = _client_cache.get(token)
    if cached is not None:
        return cached
    environment = SquareEnvironment.PRODUCTION if env_name == "production" else SquareEnvironment.SANDBOX
    client = Square(token=token, environment=environment)
    _client_cache[token] = client
    return client


def create_payment(*, source_id, idempotency_key, amount_cents, currency="USD", customer_note=None, buyer_email=None):
    """A single Square payment for `amount_cents` (integer, never a float). `idempotency_key` MUST be
    stable across retries of the SAME logical attempt (see app/payments.py — it is generated once per
    `Payment` row and reused verbatim on every retry, per Square's own idempotency contract)."""
    client = get_client()
    resp = client.payments.create(
        source_id=source_id,
        idempotency_key=idempotency_key,
        amount_money={"amount": amount_cents, "currency": currency},
        location_id=location_id(),
        note=(customer_note or "")[:500] or None,
        buyer_email_address=buyer_email or None,
    )
    return resp.payment


def get_payment(square_payment_id):
    client = get_client()
    return client.payments.get(payment_id=square_payment_id).payment


def create_refund(*, payment_id, amount_cents, currency="USD", idempotency_key, reason=None):
    client = get_client()
    resp = client.refunds.refund_payment(
        idempotency_key=idempotency_key,
        amount_money={"amount": amount_cents, "currency": currency},
        payment_id=payment_id,
        reason=(reason or "")[:190] or None,
    )
    return resp.refund


def verify_webhook_signature(request_body: bytes, signature_header: str, notification_url: str) -> bool:
    """Square's documented HMAC-SHA256 scheme: base64(HMAC-SHA256(webhook_signature_key, notification_url +
    raw_request_body)), compared to the `x-square-hmacsha256-signature` header. Not exposed as a helper by
    the SDK itself, so implemented directly against stdlib `hmac`/`hashlib` per Square's published algorithm.
    `notification_url` MUST be the exact URL registered in the Square dashboard (`SQUARE_WEBHOOK_URL`)."""
    key = current_app.config.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "")
    if not key or not signature_header or not notification_url:
        return False
    payload = (notification_url + request_body.decode("utf-8")).encode("utf-8")
    expected = base64.b64encode(hmac.new(key.encode("utf-8"), payload, hashlib.sha256).digest()).decode("utf-8")
    return hmac.compare_digest(expected, signature_header)
