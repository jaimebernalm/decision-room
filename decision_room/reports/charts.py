"""Bounded chart declarations; values always resolve through report references."""
from copy import deepcopy


def normalize(value, finding_keys):
    if not isinstance(value, list) or len(value) > 8:
        raise ValueError('At most eight report charts are supported.')
    result = []; seen = set(); count = 0
    def text(value, *, required=False):
        if not isinstance(value, str) or (required and not value) or len(value) > 2000:
            raise ValueError('Invalid chart text.')
        return value
    def identity(value, known):
        if not isinstance(value, str) or not 1 <= len(value) <= 100 or value in known:
            raise ValueError('Invalid or duplicate chart identity.')
        known.add(value); return value
    for chart in value:
        if not isinstance(chart, dict) or set(chart) - {'key', 'kind', 'title', 'caption', 'series', 'recommendation_id'}:
            raise ValueError('Unsupported chart fields.')
        key = identity(chart.get('key'), seen)
        if chart.get('kind') not in ('bar', 'line', 'table'):
            raise ValueError('Unsupported chart kind.')
        recommendation = chart.get('recommendation_id')
        if recommendation is not None and recommendation not in finding_keys:
            raise ValueError('Chart refers to an unknown finding.')
        series = chart.get('series')
        if not isinstance(series, list) or not 1 <= len(series) <= 6:
            raise ValueError('Provide one to six chart series.')
        normalized = []; keys = set()
        for item in series:
            if not isinstance(item, dict) or set(item) != {'key', 'label', 'points'}:
                raise ValueError('Unsupported series fields.')
            series_key = identity(item['key'], keys)
            if not isinstance(item['points'], list) or not 1 <= len(item['points']) <= 100:
                raise ValueError('Provide one to one hundred points.')
            points = []
            for point in item['points']:
                if not isinstance(point, dict) or set(point) != {'label', 'number_key'}:
                    raise ValueError('Chart points must reference report numbers.')
                label = text(point['label'], required=True)
                reference = point['number_key']
                if not isinstance(reference, str) or not 1 <= len(reference) <= 100 or any(c in reference for c in '{}'):
                    raise ValueError('Invalid chart number reference.')
                count += 1
                if count > 800:
                    raise ValueError('Report charts exceed the point limit.')
                points.append({'label': label, 'number_key': reference, 'value_text': '{{n:' + reference + '}}'})
            normalized.append({'key': series_key, 'label': text(item['label'], required=True), 'points': points})
        result.append({'key': key, 'kind': chart['kind'], 'title': text(chart.get('title'), required=True),
                       'caption': text(chart.get('caption', '')), 'series': normalized, 'recommendation_id': recommendation})
    return result


def texts(charts):
    for i, chart in enumerate(charts):
        base = f'/charts/{i}'
        for field in ('title', 'caption'):
            yield base+'/'+field, chart[field], chart['recommendation_id']
        for j, series in enumerate(chart['series']):
            yield f'{base}/series/{j}/label', series['label'], chart['recommendation_id']
            for k, point in enumerate(series['points']):
                for field in ('label', 'value_text'):
                    yield f'{base}/series/{j}/points/{k}/{field}', point[field], chart['recommendation_id']


def project(charts, figures):
    output = deepcopy(charts)
    by_path = {f['path']: f for f in figures if f['path'].endswith('/value_text')}
    for i, chart in enumerate(output):
        for j, series in enumerate(chart['series']):
            for k, point in enumerate(series['points']):
                path = f'/charts/{i}/series/{j}/points/{k}/value_text'
                figure = by_path.get(path)
                point['value'] = figure.get('value') if figure and figure['text'] == point['value_text'] else None
                point['unit'] = figure.get('unit') if figure else None
                point['path'] = path
    return output
