"""Validated values and user-visible HTTP errors shared by web services."""
from uuid import UUID


class WebError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def identifier(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise WebError('Identificador no válido.') from None


def bounded(value, label, limit, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise WebError(f'Revisa {label}: ' + (f'es obligatorio y admite hasta {limit} caracteres.' if required else f'admite hasta {limit} caracteres.'))
    return value.strip()
