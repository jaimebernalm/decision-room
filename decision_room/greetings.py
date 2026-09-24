"""Recognize a greeting only when it is the entire owner message."""
import re


GREETINGS = {
    'hola', 'holi', 'buenas', 'buen día', 'buenos días', 'buenas tardes',
    'buenas noches', 'qué tal', 'que tal', 'hey', 'hello', 'hi',
}


def is_greeting(text):
    normalized = re.sub(r'[¡!¿?.,\s]+', ' ', text.casefold()).strip()
    return normalized in GREETINGS
