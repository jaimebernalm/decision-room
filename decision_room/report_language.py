"""Export chrome follows the saved generation language; evidence text is preserved."""
from copy import deepcopy
import re

LABELS = {
    'Revisado': 'Reviewed', ' · Entrega parcial': ' · Partial delivery',
    'Contexto y alcance': 'Context and scope', 'Pregunta del análisis': 'Analysis question',
    'Siguiente comprobación': 'Next check', 'Periodo / categoría': 'Period / category',
    'Valores exactos': 'Exact values', 'Cómo se ha calculado': 'Calculation method',
    'Fuentes y evidencia': 'Sources and evidence', 'Resultado guardado': 'Saved result',
    'Valor': 'Value', 'Cobertura de las preguntas': 'Question coverage',
    'Respondida': 'Answered', 'Información no disponible': 'Information unavailable',
    'Pendiente': 'Pending', 'Limitaciones': 'Limitations',
    'Decision Room · Informe revisado': 'Decision Room · Reviewed report',
    'Decision Room · Informe de negocio': 'Decision Room · Business report',
    'Exportado:': 'Exported:',
    'Presentación · Versión': 'Presentation · Version',
    '. Cálculos y fuentes del análisis original conservados.': '. Original analysis calculations and sources preserved.',
    'Entrega parcial · Consulta las preguntas pendientes en alcance y límites.':
        'Partial delivery · See pending questions in scope and limitations.',
    'Cifras clave': 'Key figures', 'Ver cómo se ha calculado': 'View calculation method',
    'Código original': 'Original code', 'Alcance y límites': 'Scope and limitations',
    'Unidad visible indicada por el propietario. Unidad del análisis:':
        'Display unit provided by the owner. Analysis unit:',
    'unidad visible indicada por el propietario. Unidad del análisis:':
        'display unit provided by the owner. Analysis unit:',
}


def label(text, language):
    return LABELS.get(text, text) if language == 'en' else text


def number(value, language):
    if language == 'en' and re.fullmatch(r'[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?', value):
        return value.translate(str.maketrans({'.': ',', ',': '.'}))
    return value


def export_view(report):
    result = deepcopy(report)
    if result.get('response_language') != 'en':
        return result
    for highlight in result.get('highlights', []):
        highlight['value'] = number(highlight['value'], 'en')
    for chart in result.get('charts', []):
        chart['response_language'] = 'en'
        for point in chart['points']:
            point['formatted'] = number(point['formatted'], 'en')
    return result
