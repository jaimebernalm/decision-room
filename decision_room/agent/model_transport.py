"""Bounded provider diagnostics; never retain error messages or arbitrary headers."""
import json
import math
import re
import httpx
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


ERROR_CODES = {
    'rate_limit_exceeded', 'rate_limit_reached', 'slow_down',
    'credit_balance_exhausted', 'insufficient_quota',
    'organization_spend_limit_exceeded', 'project_spend_limit_exceeded',
    'organization_usage_limit_exceeded', 'billing_hard_limit_reached',
    'billing_not_active', 'server_is_overloaded',
}
ACCOUNT_CODES = ERROR_CODES - {
    'rate_limit_exceeded', 'rate_limit_reached', 'slow_down', 'server_is_overloaded',
}
ERROR_TYPES = {
    'rate_limit_error', 'insufficient_quota', 'tokens', 'requests',
    'invalid_request_error', 'service_unavailable_error', 'server_error',
}
MAX_ERROR_BYTES = 16 * 1024
MAX_RETRY_WAIT = 300


def retry_after(response):
    raw = response.headers.get('Retry-After')
    if not raw or len(raw) > 128:
        return None
    try:
        value = float(raw)
    except ValueError:
        try:
            value = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0, value) if math.isfinite(value) else None


def duration(raw):
    """Parse only numeric reset durations, e.g. 1m0.25s; reject free text."""
    if not raw or len(raw) > 128:
        return None
    parts = re.findall(r'(\d+(?:\.\d+)?)(ms|s|m|h|d)', raw)
    if not parts or ''.join(a + b for a, b in parts) != raw:
        return None
    units = {'ms': .001, 's': 1, 'm': 60, 'h': 3600, 'd': 86400}
    value = sum(float(n) * units[u] for n, u in parts)
    return value if math.isfinite(value) and value <= 365 * 86400 else None


def diagnostics(response):
    result = {}
    request_id = response.headers.get('x-request-id', '')
    if re.fullmatch(r'(?:req_)?[a-fA-F0-9-]{16,128}', request_id):
        result['request_id'] = request_id
    limits = {}
    for field in ('limit-requests', 'remaining-requests', 'limit-tokens',
                  'remaining-tokens', 'limit-project-tokens', 'remaining-project-tokens'):
        raw = response.headers.get('x-ratelimit-' + field, '')
        if re.fullmatch(r'\d{1,12}', raw):
            limits[field.replace('-', '_')] = int(raw)
    for field in ('requests', 'tokens', 'project-tokens'):
        value = duration(response.headers.get('x-ratelimit-reset-' + field))
        if value is not None:
            limits['reset_' + field.replace('-', '_') + '_seconds'] = value
    if limits:
        result['rate_limits'] = limits
    wait = retry_after(response)
    if wait is not None:
        result['retry_after_seconds'] = wait
    if response.status_code == 200:
        return result
    # An explicit rejection is known even if its optional diagnostic body fails.
    try:
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=1024):
            body.extend(chunk)
            if len(body) > MAX_ERROR_BYTES:
                return result
        error = json.loads(body).get('error') if body else None
        if isinstance(error, dict):
            for field, allowed in (('code', ERROR_CODES), ('type', ERROR_TYPES)):
                value = error.get(field)
                if isinstance(value, str):
                    result['error_' + field] = value if value in allowed else 'unrecognized'
    except (ValueError, AttributeError, httpx.HTTPError):
        pass
    code, kind = result.get('error_code'), result.get('error_type')
    if code in ACCOUNT_CODES or kind == 'insufficient_quota':
        result['error_category'] = 'account_limit'
    elif code == 'slow_down':
        result['error_category'] = 'slow_down'
    elif code in ('rate_limit_exceeded', 'rate_limit_reached') or kind in ('rate_limit_error', 'tokens', 'requests'):
        result['error_category'] = 'rate_limit'
    elif code == 'server_is_overloaded':
        result['error_category'] = 'overloaded'
    return result


def retry_delay(response, attempt, details=None):
    if details and details.get('error_category') == 'account_limit':
        return None
    raw = response.headers.get('Retry-After')
    wait = retry_after(response)
    # Nonfinite hints are not safe to replace with an earlier wait.
    if raw:
        try:
            if not math.isfinite(float(raw)):
                return None
        except ValueError:
            pass
    if wait is None:
        wait = 2 ** (attempt + (response.status_code == 429))
    if response.status_code == 429 and details:
        limits = details.get('rate_limits', {})
        for kind in ('requests', 'tokens', 'project_tokens'):
            if kind in ('tokens', 'project_tokens') or limits.get('remaining_' + kind) == 0:
                wait = max(wait, limits.get('reset_' + kind + '_seconds', 0))
    # Both 429 and 503 hints are minima. A long wait requires deferred recovery.
    return max(1, wait) if wait <= MAX_RETRY_WAIT else None


async def async_diagnostics(response):
    """Bounded async error read; once rejected, a broken error body is still rejected."""
    if response.status_code == 200:
        return diagnostics(response)
    body = bytearray()
    try:
        async for chunk in response.aiter_bytes(chunk_size=1024):
            body.extend(chunk)
            if len(body) > MAX_ERROR_BYTES:
                body.clear()
                break
    except httpx.HTTPError:
        body.clear()
    return diagnostics(httpx.Response(response.status_code, headers=response.headers, content=bytes(body)))
