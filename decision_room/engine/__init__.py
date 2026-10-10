"""Opt-in report engine API. Legacy report generation remains independent."""


def run_report(config, business_id, analysis_id, *, owner_context, request_key, limits=None, context=None, engine_config=None):
    from .api import run_report as run
    return run(config, business_id, analysis_id, owner_context=owner_context, request_key=request_key, limits=limits, context=context, engine_config=engine_config)


def resume_report(config, business_id, engine_run_id, *, answer=None):
    from .api import resume_report as resume
    return resume(config, business_id, engine_run_id, answer=answer)


def export_run(config, business_id, engine_run_id, dest):
    from .export import export_run as export
    return export(config, business_id, engine_run_id, dest)
