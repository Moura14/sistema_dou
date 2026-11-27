import re


_PAL = r"[A-ZÀ-Ý][A-ZÀ-Ýa-zà-ÿ'’\-]*"
_NOME = _PAL + r"(?:\s+(?:d[aeo]s?\s+|e\s+)?" + _PAL + r"){1,8}"
_MAIUSC = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇÑ]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇÑ]+){1,8}"
_MAIUSC_NOME = _MAIUSC
_DATA_CURTA = r"\d{1,2}[º°]?\s+de\s+[a-zç]+\s+de\s+\d{4}|\d{1,2}[º°]?/\d{1,2}/\d{4}"
_NAO_NOME_EXTRA = {"ministerio", "conselho", "federal", "uniao", "republica", "presidencia"},
_NAO_NOME = {"cargo", "funcao", "ministro", "ministra", "portaria", "chefe"},
_RE_NOME = re.compile(
    r"^[\s,:;\\-]*"
    r"(?:(?:a\s+pedido|de\s+ofício|a\s+(?:contar|partir)\s+d[eo]\s+(?:" + _DATA_CURTA + r"))\s*,?\s*)*"
    r"(?:(?:o|a)\s+)?"
    r"(?:exerc[ií]cio\s+d[eo]\s+mandato\s+d[oa]\s+)?"
    r"(?:(?:servidor|servidora|conselheiro|conselheira|Senhor|Senhora|Sr|Sra)\.?\s+)?"
    r"(" + _NOME + r")"
    r"(?=\s*[,(;]|\s+(?:para|do|da|no|na|à|ao|como|CPF|matrícula|SIAPE|ocupante)\b)"
)
_RE_NOME_PASSIVO = re.compile(r"(" + _MAIUSC + r")\s+para\s+exercer")
_RE_NOME_SOLTO = re.compile(
    r"(" + _MAIUSC + r")(?=\s*(?:,|\s+da\s+função|\s+à\s+função|\s+do\s+cargo|\s+para\s+exercer|\s+do\s+emprego))")
_RE_NOME_SERVIDOR = re.compile(
    r"\b(?i:servidora?|empregad[oa])\s+(" + _MAIUSC_NOME + r")(?=\s*,)"
)
_RE_NOME_ANTES_MATRICULA = re.compile(
    r"(" + _MAIUSC_NOME + r")\s*,\s*[^,;]{3,100}?\s*,\s*(?i:matr[ií]cula)\b"
)

_PARADA_CARGO = (
    r"(?=\s*(?:,(?!\s*(?-i:[A-ZÀ-Ý][a-zà-ÿ]))|[;:])"
    r"|\s+(?:código|(?-i:CCE|FCE|FCPE|DAS|FG|CD|NE))\b"
    r"|\.(?:\s|$)|\s+a\s+partir\b|\s+ficando\b|\s+e\s*$|$)"
)

_RE_DESTINO = re.compile(
    r"\bpara\s+(?:a|o)\s+(.{5,200}?)\s+d[oa]\s+Conselho\b", re.I | re.S)


_MINUSC = {"de", "do", "da", "dos", "das", "e"}


