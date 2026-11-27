import re

from .regex_datas import _DATA, _MESES_RE
from .regex_nomes import _MAIUSC_NOME, _NOME, _PARADA_CARGO
from .regex_orgaos import _P_MIN, _P_UNI

_RE_LIXO = re.compile(
    r"(?mi)^[^\n]*(?:ISSN\s*\d|Documento assinado digitalmente|Este documento pode ser verificado|"
    r"que institui a Infraestrutura|autenticidade\.html|DI[ÁA]RIO OFICIAL DA UNI[ÃA]O\s*-\s*Se)[^\n]*$"
    r"|^\s*Se[çc][ãa]o\s+\d+\s*$"
    r"|^\s*Nº\s+\d+,\s*(?:segunda|terça|quarta|quinta|sexta)-feira[^\n]*$"
)

_RE_SUMARIO = re.compile(
    r"(?mi)^[ \t]*SUM[ÁA]RIO[ \t]*$"
    r"|^[^\n]*(?:\.[ \t]*){4,}\d{1,4}[ \t]*$"
    r"|^[ \t]*P[áa]g(?:ina|\.)?[ \t]*\d+[ \t]*$"
)

_RE_CARGO = re.compile(
    r"\b(?:cargo|função|emprego|mandato|encargo)"
    r"(?:\s+(?:em\s+comissão|de\s+confiança|de\s+natureza\s+especial|"
    r"comissionad[oa]|efetiv[oa]))*"
    r"(?:\s+(?-i:[A-ZÀ-Ý][\wà-ÿ\\-]*)){0,3}"
    r"\s+de\s+(.{1,220}?)" + _PARADA_CARGO,
    re.I | re.S,
)

_RE_CARGO_APOS_CPF = re.compile(
    r"CPF\s*(?:n[ºo°]\s*)?[\d*.\\-]+\s*,\s*(.{3,150}?)\s*"
    r"(?=,\s*(?:código|(?-i:CCE|FCE|FCPE|DAS|FG|CD|NE))\b)",
    re.I | re.S,
)

_RE_CARGO_APOS_NOME = re.compile(r",\s*([^,]{3,120}?),\s*[Mm]atrícula\s+(?i:siape)")

_RE_CODIGO = re.compile(
    r"\b((?i:CCE|FCE|FCPE)|DAS|FG|CD|CGE|FUC|FST|NE)[\s\\-]*(\d+(?:[.,]\d+)*)\b"
)

_RE_SIAPE = re.compile(
    r"\b(?:(?:Matrícula\s+)?SIAPE|Matrícula)\s*"
    r"(?:n[ºo°]\s*)?[:\\-]?\s*"
    r"([\d*Xx]+(?:[.\\-][\d*Xx]+)*)\b",
    re.IGNORECASE,
)

_RE_PROCESSO = re.compile(
    r"\bprocesso\b\s*(?:administrativo\s*)?(?:SEI\s*)?"
    r"(?:n[º°o.]?\s*)?[:\\-]?\s*"
    r"(\d[\d./-]{4,})",
    re.IGNORECASE
)

_RE_EFEITO = re.compile(
    r"(?:a\s+partir\s+d[eoa]|a\s+contar\s+d[eoa]|com\s+efeitos?\s+(?:a\s+partir\s+)?d[eoa])"
    r"\s+(" + _DATA + r")",
    re.I,
)

_RE_ITEM_SUBST = re.compile(
    r"(?:^|\s)([IVX]+)\s*[-–—]\s*(" + _MAIUSC_NOME + r")\s*,\s*"
    r"(?i:matr[ií]cula\s+siape)\s*(?:n[ºo°.]*\s*)?([\d.]+)"
)

_RE_PUBLICACAO = re.compile(r"Publicado em:\s*(\d{2}/\d{2}/\d{4})", re.I)

_RE_ORGAO = re.compile(r"Órgão:\s*([^\n]+)", re.I)

_FIM_TITULO = r"[ \t]*(?:[-–—(*][^\n]{0,60})?$"

_DATA_TITULO = r"\d{1,2}\s*[º°]?\s+DE\s+(?:" + _MESES_RE + r")\s+DE\s+\d{4}"

_RE_DATA_CAB = re.compile(
    r"(?im)^\s*PORTARIAS?\b[^\n]*?\bDE\s+(" + _DATA_TITULO + r")" + _FIM_TITULO)

_RE_NUM_TITULO = re.compile(
    r"(?im)^\s*(?:PORTARIAS?\b(?P<sigla>[^\n]*?))?"
    r"\bN\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)\s*,?\s*DE\s+" + _DATA_TITULO + _FIM_TITULO)

_RE_NUM_ITEM = re.compile(
    r"(?m)^\s*(?P<sigla>)N\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)\s*[-–—]\s")

_RE_NUMERO = re.compile(
    r"(?im)^\s*(?:PORTARIAS?\b(?P<sigla>[^\n]*?))?"
    r"\bN\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)"
    r"\s*(?=(?:[-–—]\s*|,?\s+DE\b))"
)

_RE_NUM_BARRA = re.compile(
    r"(?im)^\s*(?:PORTARIAS?|DESPACHO|RESOLU[ÇC][ÃA]O)\b(?P<sigla>[^\n]*?)"
    r"\bN\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)\s*/\s*\d{2,4}")

_RE_MINISTERIO = re.compile(r"(?m)^[ \t]*" + _P_MIN)

_RE_UNIDADE = re.compile(r"(?m)^[ \t]*" + _P_UNI)

_RE_CORTE = re.compile(r"(?m)^[ \t]*(?:" + _P_MIN + "|" + _P_UNI + ")")

_RE_DATA_DOU = re.compile(
    r"(?:(?:segunda|terça|quarta|quinta|sexta)-feira|sábado|domingo),\s*"
    r"(\d{1,2}\s+de\s+[A-Za-zçÇ]+\s+de\s+\d{4})", re.I)

_RE_EMISSOR = re.compile(
    r"\bD[AO]\s+([A-ZÀ-Ý][A-ZÀ-Ý \\-]{3,80}?)\s*,\s*nos?\s+uso\b")

_RE_TITULO = re.compile(
    r"(?im)^\s*PORTARIAS?\b[^\n]*?\bN\s*[º°.]?\s*([\d]+(?:\.[\d]+)*)"
    r"\s*,?\s*DE\s+([^\n]+)"
)

_RE_DESPACHO = re.compile(r"(?m)^\s*DESPACHO\s*$")

_RE_AFASTAMENTO = re.compile(
    r"autoriza\s*o\s*afastamento\s*do\s*Pa[ií]s\s*d[eo]\s*"
    r"(?P<nome>(?-i:" + _NOME + r"))\s*,\s*(?P<cargo>[^,]{3,150}?)\s*,\s*para\s*"
    r"(?P<motivo>.{1,500}?)\s*,\s*no\s*per[ií]odo\s*de\s*(?P<periodo>[^,]{3,80}?)\s*,\s*com\s*[ôo]nus",
    re.I | re.S,
)

_RE_CPF = re.compile(
    r"\bCPF(?:\s*/\s*M\.?\s*F\.?)?\b\s*"
    r"(?:(?:sob\s+(?:o\s+)?)?n[ºo°.]?\s*)?[:\\-]?\s*"
    r"([*Xx\d]{2,3}[.\s-]?"
    r"[*Xx\d]{3}[.\s-]?"
    r"[*Xx\d]{3}[.\s-]?"
    r"[*Xx\d]{2})",
    re.IGNORECASE
)