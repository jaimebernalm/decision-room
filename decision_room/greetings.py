"""Recognize a greeting only when it is the entire owner message."""
import re
import unicodedata


GREETINGS = {
    'hola', 'holi', 'buenas', 'buen dia', 'buenos dias', 'buenas tardes',
    'buenas noches', 'que tal', 'hey', 'hello', 'hi',
}


def normalized(text):
    plain = ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))
    return re.sub(r'[¡!¿?.,\s]+', ' ', plain).strip()


def is_greeting(text):
    phrase = '|'.join(re.escape(item) for item in sorted(GREETINGS, key=len, reverse=True))
    return bool(re.fullmatch(rf'(?:{phrase})(?: (?:{phrase}))*', normalized(text)))


def salutation(text):
    plain = normalized(text)
    for phrase, reply in [('buenos dias', 'buenos días'), ('buen dia', 'buen día'),
                          ('buenas tardes', 'buenas tardes'), ('buenas noches', 'buenas noches')]:
        if re.search(rf'\b{phrase}\b', plain):
            return f'¡Hola, {reply}!' if re.search(r'\bhola\b', plain) else f'¡{reply[0].upper() + reply[1:]}!'
    return '¡Hola!'
