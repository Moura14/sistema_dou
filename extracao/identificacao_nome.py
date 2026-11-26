import re

from .config.regex_nomes import (
    MAIUSC_NOME,
    RE_NOME,
    RE_NOME_PASSIVO,
    RE_NOME_SOLTO,
    RE_NOME_SERVIDOR,
    RE_NOME_ANTES_MATRICULA,
)


def identificar_nome(texto: str) -> str | None:
    match = RE_NOME_SERVIDOR.search(texto)

    if match:
        return match.group(1).strip()

    match = RE_NOME_PASSIVO.search(texto)

    if match:
        return match.group(1).strip()

    return None