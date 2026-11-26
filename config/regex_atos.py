import re

from .acoes import ACOES

_INF = (r"tornar\s+sem\s+efeito|demitir|nomear|exonerar|dispensar|designar|aposentar|ceder|revogar|"
        r"reconduzir|redistribuir|transferir|remover|prorrogar|conceder|afastar|lotar|substituir|renovar")

_PART = (r"tornad[oa]s?\s+sem\s+efeito|demitid[oa]s?|nomead[oa]s?|exonerad[oa]s?|dispensad[oa]s?|designad[oa]s?|"
         r"aposentad[oa]s?|cedid[oa]s?|revogad[oa]s?|reconduzid[oa]s?|"
         r"redistribuíd[oa]s?|transferid[oa]s?|removid[oa]s?|prorrogad[oa]s?|concedid[oa]s?|"
         r"afastad[oa]s?|lotad[oa]s?|substituíd[oa]s?|renovad[oa]s?")

RE_INFINITIVO = re.compile(rf"\b(?:{_INF})\b", re.I)

RE_ACAO = re.compile(rf"\b({_INF}|{_PART})\b", re.I)
RE_PASSADO = re.compile(
    r"\bque\s+(?:nomeou|exonerou|dispensou|designou|aposentou|cedeu|revogou|"
    r"reconduziu|redistribuiu|transferiu|removeu|prorrogou|concedeu|afastou|lotou|substituiu|renovou)\b", re.I)

RE_PORTARIA_REF = re.compile(
    r"\bPortaria(?:\s+((?:de\s+Pessoal\s+)?[A-Z][A-Za-z/.\\-]*))?\s+n\s*[º°o.]?\s*(\d+(?:\.\d+)*)", re.I)
RE_VIGOR = re.compile(r"entra\s+em\s+vigor\s+na\s+data\s+d[ea]\s+(?:sua|presente)\s+publicação", re.I)
RE_RESOLVE = re.compile(r"\bresolve(?:m)?\s*:?", re.I)

_VERBOS_MAIUSC = (
    "NOMEAR", "EXONERAR", "DISPENSAR", "DESIGNAR", "APOSENTAR", "CEDER", "REVOGAR",
    "RECONDUZIR", "REDISTRIBUIR", "TRANSFERIR", "REMOVER", "PRORROGAR", "CONCEDER",
    "AFASTAR", "LOTAR", "SUBSTITUIR", "RENOVAR", "DEMITIR",
)

_RE_VERBO_ESPACADO = re.compile(
    r"(?m)^([ \t]*(?:Art\.?\s*\d+\s*[º°]?\s*|N[º°.]?\s*\d[\d.]*\s*[-–—]\s*)?)"
    r"((?:" + "|".join(r"\s*".join(v) for v in _VERBOS_MAIUSC) + r"))"
    r"(?=[ \t]*(?:,|$))"
)