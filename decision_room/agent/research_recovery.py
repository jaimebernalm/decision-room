"""Opt-in salvage of computed evidence, never of rejected model conclusions."""
from .research_contract import validate_research_action

REASON = 'Cierre parcial tras dos respuestas inválidas; los cálculos conservados requieren interpretación y revisión.'


class ValidationExhausted(ValueError):
    """Only domain-validation exhaustion, not transport, stale data or execution errors."""


def recovery_actions(snapshot, observations, findings, options):
    """Deterministic, individually validated registrations; no model or Python call.

    Input observations are the same bounded, visible records offered to the model.
    A candidate is raw material for independent review, not an approved conclusion.
    Legacy runs retain only their latest scalar result; continuity retains visible
    metrics and series across successful calculations, including before a failure.
    """
    closed = {f['investigation_key'] for f in findings} | set(options.get('discarded_keys', []))
    actions = []
    for item in snapshot['proposal']['investigations']:
        key = item['key']
        attempts = [o for o in observations if o['investigation_key'] == key]
        if key in closed or not attempts:
            continue
        visible = [o for o in attempts if o['status'] == 'completed' and not o.get('result_omitted')
                   and o.get('current') is not False and (o.get('result') or {}).get('verification') != 'rejected']
        refs = [dict(execution_id=o['execution_id'], metric_keys=list(o['result'].get('metrics', {})),
                     series_keys=list(o['result'].get('series', {}))) for o in visible]
        refs = [r for r in refs if r['metric_keys'] or r['series_keys']][:12]
        metrics = []
        if not options.get('research_continuity'):
            last = attempts[-1]
            metrics = list(last['result'].get('metrics', {})) if last in visible else []
        candidate = bool(refs) if options.get('research_continuity') else bool(metrics)
        action = dict(action='record_candidate' if candidate else 'block', investigation_key=key,
                      code='', table_ids=[], metric_keys=metrics, followups=[], assignments=[], synthesis=None,
                      summary=REASON if candidate else 'No hay cálculos visibles utilizables para registrar una conclusión; cierre parcial tras respuestas inválidas.')
        if options.get('research_continuity'):
            action.update(evidence_refs=refs if candidate else [], continuation=None,
                          closure=dict(reason='unusable', pending_calculation=None,
                                       decision_if_different='No se ha establecido una decisión; hace falta interpretar y revisar los cálculos.',
                                       explanation='La respuesta de investigación no superó la validación. No se puede inferir con seguridad un cálculo pendiente ni una conclusión.'))
        try:
            action = validate_research_action(action, snapshot, observations, findings, options)
        except ValueError:
            # Dependencies/readiness or evidence limits may still preclude safe
            # registration. Keep raw executions durable, without bypassing checks.
            continue
        actions.append(action)
    return actions
