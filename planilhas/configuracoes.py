
import hashlib
import json
from pathlib import Path

from planilhas.esquema import normalizar

ARQ_CONFIG = Path("config_planilhas.json")

def chave_planilha(colunas: list[str]) -> str:
    base = "|".join(normalizar(c) for c in colunas)
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def carregar_config(chave: str) -> dict:
    try:
        return json.loads(ARQ_CONFIG.read_text(encoding="utf-8")).get(chave, {})
    except (OSError, ValueError):
        return {}


def salvar_config(chave: str, config: dict) -> None:
    try:
        dados = json.loads(ARQ_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    dados[chave] = config
    ARQ_CONFIG.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
