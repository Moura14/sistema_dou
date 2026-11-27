import re

from .config.acoes import ACOES, RAIZES
from .config.regex_atos import (
    RE_INFINITIVO,
    RE_ACAO,
    RE_PASSADO,
)


def identificar_ato(texto: str) -> str | None:
    texto = texto.upper()

    for raiz, tipo in RAIZES.items():
        if re.search(raiz, texto):
            return tipo

        return None