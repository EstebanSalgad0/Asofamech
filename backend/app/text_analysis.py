"""Frecuencia de terminos en texto libre en español.

Alimenta la nube de palabras del panel de analisis, que resume de un vistazo
que respondio el curso en las preguntas abiertas sin obligar al docente a leer
cientos de respuestas una por una.

Se implementa aqui, sin dependencias externas: la lista de vacias del español
es corta y estable, y el volumen (unos cientos de respuestas por encuesta) no
justifica arrastrar NLTK o spaCy al contenedor.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

# Palabras vacias del español + muletillas frecuentes en respuestas de encuesta.
# Sin tildes: la comparacion se hace sobre la forma ya normalizada.
STOPWORDS_ES = {
    "a", "al", "algo", "algun", "alguna", "algunas", "alguno", "algunos", "ante",
    "antes", "aqui", "asi", "aun", "aunque", "bastante", "bien", "cada", "casi",
    "como", "con", "cual", "cuales", "cuando", "cuanto", "de", "del", "demas",
    "desde", "donde", "dos", "durante", "e", "el", "ella", "ellas", "ello",
    "ellos", "en", "entre", "era", "eran", "eres", "es", "esa", "esas", "ese",
    "eso", "esos", "esta", "estaba", "estan", "estar", "estas", "este", "esto",
    "estos", "estoy", "fue", "fueron", "ha", "habia", "han", "hace", "hacer",
    "hacia", "hasta", "hay", "he", "hemos", "incluso", "l", "la", "las", "le",
    "les", "lo", "los", "mas", "me", "mi", "mis", "misma", "mismo", "mucha",
    "muchas", "mucho", "muchos", "muy", "nada", "ni", "no", "nos", "nosotros",
    "nuestra", "nuestro", "nunca", "o", "otra", "otras", "otro", "otros", "para",
    "pero", "poco", "por", "porque", "pude", "puede", "pueden", "pues", "que",
    "quien", "se", "sea", "segun", "ser", "si", "sido", "siempre", "sin",
    "sobre", "solo", "son", "su", "sus", "tambien", "tan", "tanto", "te",
    "tener", "tengo", "tiene", "tienen", "toda", "todas", "todo", "todos", "tu",
    "un", "una", "unas", "uno", "unos", "usted", "ustedes", "ya", "yo",
    # Respuestas que no aportan contenido tematico.
    "cosa", "cosas", "gracias", "n", "na", "nada", "ninguna", "ninguno", "ok",
    "si", "sí", "vez", "veces",
}

MIN_WORD_LENGTH = 4
_TOKEN_PATTERN = re.compile(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ][\wáéíóúüñÁÉÍÓÚÜÑ-]*", re.UNICODE)


def _strip_accents(word: str) -> str:
    normalized = unicodedata.normalize("NFD", word)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _normalize(word: str) -> str:
    return _strip_accents(word.lower()).strip("-")


def word_frequencies(texts: list[str], limit: int = 60) -> list[dict]:
    """Cuenta terminos y devuelve los `limit` mas frecuentes.

    El agrupamiento se hace sobre la forma sin tildes y en minusculas ("clínico"
    y "Clinico" son el mismo termino), pero se muestra la variante mas escrita
    por los estudiantes, que suele ser la ortograficamente correcta.

    `responses` cuenta en cuantas respuestas distintas aparece el termino: un
    estudiante que repite una palabra cinco veces no debe dominar la nube.
    """
    counts: Counter[str] = Counter()
    documents: dict[str, int] = defaultdict(int)
    surface_forms: dict[str, Counter[str]] = defaultdict(Counter)

    for text in texts:
        if not text:
            continue
        seen_in_document: set[str] = set()
        for match in _TOKEN_PATTERN.finditer(text):
            raw = match.group(0)
            key = _normalize(raw)
            if len(key) < MIN_WORD_LENGTH or key in STOPWORDS_ES:
                continue
            counts[key] += 1
            surface_forms[key][raw.lower()] += 1
            seen_in_document.add(key)
        for key in seen_in_document:
            documents[key] += 1

    ranked = counts.most_common(limit)
    return [
        {
            "text": surface_forms[key].most_common(1)[0][0],
            "count": count,
            "responses": documents[key],
        }
        for key, count in ranked
    ]
