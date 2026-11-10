
import math
import numbers
import re
import unicodedata
from datetime import date, datetime

FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y")


def valor_vazio(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    if isinstance(valor, numbers.Real):
        return math.isnan(valor)
    return False


def normalizar(valor) -> str:
    if valor_vazio(valor):
        return ""
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def texto_exibicao(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def converter_valor(valor, tipo: str):
    if valor_vazio(valor):
        return None
    if isinstance(valor, str):
        valor = valor.strip()

    if tipo == "data":
        if isinstance(valor, datetime):
            return valor
        if isinstance(valor, date):
            return datetime.combine(valor, datetime.min.time())
        for formato in FORMATOS_DATA:
            try:
                return datetime.strptime(valor, formato)
            except ValueError:
                pass
        return valor

    if tipo == "numero" and isinstance(valor, str):
        if re.fullmatch(r"-?\d+", valor):
            return int(valor)
        try:
            return float(valor.replace(",", "."))
        except ValueError:
            return valor

    return valor


def _tipo_coluna(valores) -> str:
    vs = [v for v in valores if v not in (None, "")]
    if vs and all(isinstance(v, (datetime, date)) for v in vs):
        return "data"
    if vs and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in vs
    ):
        return "numero"
    return "texto"

