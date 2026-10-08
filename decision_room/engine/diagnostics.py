"""Safe controller diagnostics: no exception text, paths, URLs or traceback leaks."""
import re

import httpx

# Exact controller-owned messages. Unknown messages are replaced, not redacted:
# a provider/database/filesystem error can contain secrets in arbitrary formats.
_MESSAGES = {
    'The job tool connection is not ready.': ('mcp_not_ready', 'The job MCP connection was not ready before prompting.'),
    'OpenCode transport failed; reconcile persisted state before retrying.': ('opencode_transport', 'The isolated OpenCode transport failed. Reconcile persisted state before retrying.'),
    'Malformed OpenCode response.': ('opencode_response', 'OpenCode returned an invalid response.'),
    'OpenCode response exceeds the byte limit.': ('opencode_response_limit', 'The OpenCode response exceeded its byte limit.'),
    'Unexpected OpenCode version or health state.': ('opencode_health', 'The OpenCode version or health state did not match the pinned runtime.'),
    'Runtime did not become healthy.': ('runtime_health', 'The runtime did not become healthy within the startup bound.'),
    'Job HTTP tunnel failed to start.': ('tunnel_start', 'The isolated job tunnel failed to start.'),
    'Job HTTP tunnel stopped; preserve state and reconcile.': ('tunnel_stopped', 'The job tunnel stopped. Preserve state and reconcile.'),
    'Docker operation uncertain; reconcile the runtime identity.': ('docker_uncertain', 'The Docker operation has an uncertain outcome. Reconcile the runtime identity.'),
    'Docker runtime operation failed; retained state requires reconciliation.': ('docker_failed', 'The Docker operation failed. Reconcile retained runtime state.'),
    'Root session identity is ambiguous.': ('session_ambiguous', 'More than one root session was found; no prompt was submitted.'),
    'Prompt must be nonempty and no larger than 256 KiB.': ('prompt_size', 'The prompt is empty or exceeds the size limit.'),
    'Prompt key already used with different content.': ('prompt_conflict', 'The prompt key was already used with different content.'),
    'Missing runtime credential after execution began.': ('credential_missing', 'Runtime credentials are missing after execution began; automatic replay is unsafe.'),
    'An incomplete restore requires explicit recovery.': ('restore_incomplete', 'A previous restore is incomplete and requires explicit recovery.'),
    'Runtime checkpoint failed its integrity check.': ('checkpoint_integrity', 'The runtime checkpoint failed its integrity check.'),
    'CSV snapshot changed or exceeds the per-file bound.': ('input_integrity', 'The CSV input changed or exceeded its size limit.'),
    'This engine runtime currently requires CSV source files.': ('input_format', 'This runtime supports CSV input files only.'),
}


def describe(error, stage):
    name = type(error).__name__
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}', name):
        name = 'Exception'
    # args are inspected only for matching trusted constants. Never serialize
    # error, repr(error), __cause__, exception attributes or the other arguments.
    message = error.args[0] if error.args and isinstance(error.args[0], str) and len(error.args[0]) <= 500 else None
    reason, safe = _MESSAGES.get(message, ('unexpected_exception', 'The controller operation failed; the original exception message was withheld.'))
    result = {'stage': stage, 'exception_type': name, 'reason': reason, 'message': safe}
    status = re.fullmatch(r'OpenCode request failed \(([1-5][0-9]{2})\)\.', message or '')
    if status:
        result.update(reason='opencode_http_status', message='OpenCode returned an unsuccessful HTTP status.', http_status=int(status[1]))
    elif isinstance(error, FileNotFoundError):
        result.update(reason='file_missing', message='A required local file was not found; its path is withheld.')
    elif isinstance(error, PermissionError):
        result.update(reason='file_permission', message='A required local operation was denied; its path is withheld.')
    elif isinstance(error, TimeoutError):
        result.update(reason='operation_timeout', message='The controller operation timed out; reconcile before replaying a mutation.')
    return result


def describe_proxy(error, stage):
    """Use a fixed vocabulary; never persist upstream text, headers or URLs."""
    result = describe(error, stage)
    if isinstance(error, httpx.TimeoutException):
        result.update(reason='transport_timeout', message='The model proxy transport timed out; the request was not retried.')
    elif isinstance(error, httpx.TransportError):
        result.update(reason='transport_failure', message='The model proxy transport failed; the request was not retried.')
    elif isinstance(error, (BrokenPipeError, ConnectionResetError)):
        result.update(reason='connection_closed', message='The downstream connection closed; the request was not retried.')
    elif result['reason'] == 'unexpected_exception':
        result['message'] = 'The model proxy operation failed; the original exception message was withheld.'
    return result
