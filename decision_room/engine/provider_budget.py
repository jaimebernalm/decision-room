"""Frozen per-run dollar envelope; never bootstrap it during a provider send."""
from uuid import UUID
import sqlite3
import os
import httpx

from ..agent import api_budget
from ..storage import Storage


def path(config, business, run):
    business, run = UUID(str(business)), UUID(str(run))
    raw = config.storage / str(business) / 'provider-budgets' / (str(run) + '.sqlite')
    if any(p.is_symlink() for p in (raw, raw.parent, raw.parent.parent)):
        raise api_budget.BudgetStopped('The run provider budget is unavailable.')
    return Storage(config.storage).path(business, str(raw.relative_to(config.storage)))


def create(config, business, run, settings, limits):
    ceiling = settings.get('usd_ceiling')
    if not ceiling:
        return  # Historical/direct profiles remain unchanged, never silently upgraded.
    if ceiling['cap_micro_usd'] * 1000 < api_budget.MAX_INPUT * api_budget.INPUT_RATE + api_budget.MAX_OUTPUT * api_budget.OUTPUT_RATE:
        raise ValueError('The engine USD ceiling cannot reserve one bounded provider call.')
    target = path(config, business, run)
    # A run UUID is new. O_EXCL refuses an existing budget, including an orphan.
    return api_budget.Ledger.create(target, cap_micro_usd=ceiling['cap_micro_usd'],
        scope_cap_micro_usd=ceiling['cap_micro_usd'],
        input_tokens=api_budget.MAX_INPUT * limits.calls,
        output_tokens=api_budget.MAX_OUTPUT * limits.calls,
        calls=limits.calls, seconds=1_000_000_000)


def ledger(config, job):
    ceiling = job['profile'].get('usd_ceiling')
    if not ceiling:
        return None
    if ceiling.get('version') != api_budget.VERSION:
        raise api_budget.BudgetStopped('Unsupported run provider budget policy.')
    # Missing storage is a loss of the existing budget, not a new allowance.
    try:
        result = api_budget.Ledger(path(config, job['business_id'], job['id']))
        with result.db() as db:
            policy = db.execute('SELECT version,cap,scope_cap FROM policy').fetchone()
    except sqlite3.Error:
        raise api_budget.BudgetStopped('The run provider budget is unreadable.') from None
    if (not policy or policy['version'] != ceiling['version'] or
            policy['cap'] != ceiling['cap_micro_usd'] * 1000 or policy['scope_cap'] != policy['cap']):
        raise api_budget.BudgetStopped('Run provider budget differs from its frozen ceiling.')
    return result


def transport(config, job, inner):
    result = ledger(config, job)
    if result is None:
        return inner
    return api_budget.BudgetTransport(result, inner or httpx.HTTPTransport(
        trust_env=False, retries=0, limits=httpx.Limits(max_keepalive_connections=0)),
        'engine:' + str(job['id']), reserve_model_output=True)


def usage(config, job):
    """A conservative bound, separate from catalogue estimates or an invoice."""
    ceiling = job['profile'].get('usd_ceiling')
    if not ceiling:
        return {'status': 'not_configured', 'charged_nano_usd': None}
    try:
        state = ledger(config, job).snapshot()
    except (api_budget.BudgetStopped, sqlite3.Error, OSError):
        return {'status': 'unavailable', 'charged_nano_usd': None, **ceiling}
    return {'status': 'stopped' if state['policy']['stopped'] else 'active',
            **ceiling, 'charged_nano_usd': state['charged_nano_usd'],
            'uncertain': state['uncertain'], 'attempts': len(state['calls'])}


def ledgers(config, job):
    """The run ceiling and optional shared trial ceiling, never a new allowance."""
    own = ledger(config, job)
    if own is not None:
        yield own
    trial = os.environ.get('DECISION_ROOM_API_BUDGET_PATH')
    if trial:
        yield api_budget.Ledger(trial)


def guard(config, job, *, resolved=False):
    identifier = 'engine:' + str(job['id'])
    for budget in ledgers(config, job):
        state = budget.scope_state(identifier)
        if state['stopped'] or (resolved and state['uncertain']):
            raise api_budget.BudgetStopped('Run provider budget stopped or unresolved.')


def recover(config, job):
    # Caller must first stop the controller/delegated runtime. The trial's
    # version decides whether orphan usage blocks this attempt or the batch.
    for budget in ledgers(config, job):
        budget.reconcile_scope('engine:' + str(job['id']))
