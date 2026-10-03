"""Mechanical view selection, never inferred from client prose or business names."""
from ..series import saved_series
from ..chart_evidence import resolve_chart


def selection_manifest(report, observations):
    charts = {c['key']: c for c in report.get('charts', [])}
    selections = report.get('delivery_selections', [])
    keys = [s['key'] for s in selections]
    if len(keys) != len(set(keys)):
        raise ValueError('Delivery selection keys must be unique.')
    result = []
    for selection in selections:
        names = selection['chart_keys']
        if len(set(names)) != len(names) or not set(names) <= charts.keys():
            raise ValueError('Delivery selection references a missing/duplicate current chart.')
        groups = set()
        for name in names:
            chart, points = resolve_chart(charts[name], observations)
            labels = {p['label'] for p in points}
            if selection['axis'] == 'points':
                groups.update(labels)
            else:
                encoding = chart.get('encoding')
                coordinates = encoding['coordinates'] if encoding else []
                if len(coordinates) != len(labels) or {p['label'] for p in coordinates} != labels:
                    raise ValueError('Grouping selections need explicit coordinates for every actual point.')
                groups.update(p['category' if selection['axis'] == 'categories' else 'series'] for p in coordinates)
        if len(groups) != selection['shown_group_count']:
            raise ValueError(f"Selection {selection['key']} declares {selection['shown_group_count']} groups but delivers {len(groups)}.")
        population = selection.get('population')
        population_labels = None
        if population:
            population_labels = {p['label'] for p in saved_series(observations, population)['points']}
            if not groups <= population_labels:
                raise ValueError('Selected groups must use exact identities from the saved reference population.')
        if selection['coverage'] == 'all_reference':
            if population_labels is None or groups != population_labels:
                raise ValueError('All-reference coverage requires the whole saved reference population in the current views.')
        result.append({**selection, 'actual_group_count': len(groups), 'groups': sorted(groups),
                       'reference_group_count': len(population_labels) if population_labels is not None else None})
    return result


def validate_selections(report, observations, policy):
    selections = selection_manifest(report, observations)
    if policy >= 5:
        covered = {key for s in selections for key in s['chart_keys']}
        if covered != {c['key'] for c in report['charts']}:
            raise ValueError('Every current chart needs an honest delivery selection; no-chart reports use an empty list.')
    return selections


def selection_notes(report, observations):
    notes = []
    for item in selection_manifest(report, observations):
        count = item['actual_group_count']
        text = f"Selección entregada: {item['title']}: {count} elementos mostrados"
        reference = item['reference_group_count']
        if reference is not None:
            text += f' de {reference} en la serie de referencia'
        # Exhaustiveness concerns this saved reference only. The reviewer still
        # checks its source operation, meaning and any selection in that source.
        notes.append(text + '.')
    return notes
