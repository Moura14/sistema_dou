import re

from config.acoes import _RAIZES
from config.limpeza_texto import (
    _RE_CARGO,
    _RE_CARGO_APOS_CPF,
    _RE_CARGO_APOS_NOME,
    _RE_CODIGO,
    _RE_CPF,
    _RE_DATA_CAB,
    _RE_EFEITO,
    _RE_ITEM_SUBST,
    _RE_NUM_BARRA,
    _RE_NUM_ITEM,
    _RE_NUM_TITULO,
    _RE_NUMERO,
    _RE_PROCESSO,
    _RE_SIAPE,
    _RE_TITULO,
)
from config.regex_atos import (
    RE_ACAO as _RE_ACAO,
    RE_INFINITIVO as _RE_INFINITIVO,
    RE_PASSADO as _RE_PASSADO,
    RE_PORTARIA_REF as _RE_PORTARIA_REF,
    RE_RESOLVE as _RE_RESOLVE,
    _RE_VERBO_ESPACADO,
    RE_VIGOR as _RE_VIGOR,
)
from config.regex_datas import _DATA, _NUM_MES
from config.regex_nomes import (
    _MAIUSC_NOME,
    _MINUSC,
    _NAO_NOME,
    _NAO_NOME_EXTRA,
    _RE_DESTINO,
    _RE_NOME,
    _RE_NOME_ANTES_MATRICULA,
    _RE_NOME_PASSIVO,
    _RE_NOME_SERVIDOR,
    _RE_NOME_SOLTO,
)
from config.regras_colunas import _REGRAS

_RE_DATA_ABERTURA = re.compile(r"\b(" + _DATA + r")\b", re.I)
_RE_LETRA = re.compile(r'\bLetra\s+["“”]?([A-Z])["“”]?', re.I)
