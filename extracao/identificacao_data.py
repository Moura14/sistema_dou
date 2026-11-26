import re
from datetime import datetime

from .config.regex_datas import DATA, MESES, NUM_MES


RE_DATA = re.compile(DATA, re.I)


def encontrar_datas(texto: str) -> list[str]:
    return RE_DATA.findall(texto)


def normalizar_data(data: str) -> str | None:
    data = data.strip()

    formatos = (
        "%d/%m/%Y",
        "%d-%m-%Y",
    )

    for formato in formatos:
        try:
            return datetime.strptime(data, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue

    return None