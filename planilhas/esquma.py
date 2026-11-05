
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import copy
from datetime import date, datetime
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

ARQ_CONFIG = Path("config_planilhas.json")
FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y")


def normalizar(valor) -> str:
    if valor is None:
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
    if valor is None:
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        if valor == "":
            return None

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


def listar_abas(arquivo: bytes) -> list[str]:
    wb = load_workbook(BytesIO(arquivo), read_only=True)
    try:
        return wb.sheetnames
    finally:
        wb.close()


def detectar_linha_cabecalho(ws, max_linhas: int = 20) -> int:
    melhor_linha, melhor_pontos = 1, 0
    for r, linha in enumerate(
        ws.iter_rows(min_row=1, max_row=max_linhas, values_only=True),
        start=1,
    ):
        pontos = sum(1 for v in linha if isinstance(v, str) and v.strip())
        if pontos > melhor_pontos:
            melhor_linha, melhor_pontos = r, pontos
    return melhor_linha


def ler_planilha(arquivo: bytes, aba: str, linha_cab: int | None = None) -> dict:
    wb = load_workbook(BytesIO(arquivo))  
    ws = wb[aba]

    if linha_cab is None:
        linha_cab = detectar_linha_cabecalho(ws)

    colunas: dict[str, int] = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(linha_cab, c).value
        if v is None or not str(v).strip():
            continue
        nome = " ".join(str(v).split())
        base, n = nome, 2
        while nome in colunas: 
            nome = f"{base} ({n})"
            n += 1
        colunas[nome] = c

    tabela: dict[int, dict] = {}
    ultima = linha_cab
    for r, linha in enumerate(
        ws.iter_rows(min_row=linha_cab + 1, values_only=True),
        start=linha_cab + 1,
    ):
        dados = {
            nome: (linha[c - 1] if c - 1 < len(linha) else None)
            for nome, c in colunas.items()
        }
        if any(v not in (None, "") for v in dados.values()):
            tabela[r] = dados
            ultima = r

    exemplos, tipos = {}, {}
    for nome in colunas:
        preenchidos = [
            d[nome]
            for d in tabela.values()
            if d[nome] not in (None, "")
            and not (isinstance(d[nome], str) and d[nome].startswith("="))
        ]
        exemplos[nome] = preenchidos[:3]
        tipos[nome] = _tipo_coluna(preenchidos[:20])

    return {
        "linha_cab": linha_cab,
        "colunas": colunas,
        "tabela": tabela,
        "ultima_linha": ultima,
        "exemplos": exemplos,
        "tipos": tipos,
    }

def sugerir_colunas_chave(colunas: list[str]) -> list[str]:
    for c in colunas:
        if "nome" in normalizar(c):
            return [c]
    return colunas[:1]


def localizar_linha(
    tabela: dict,
    colunas_chave: list[str],
    valores_chave: dict,
    limite: float = 0.88,
):
    alvo = {c: normalizar(valores_chave.get(c)) for c in colunas_chave}
    alvo = {c: v for c, v in alvo.items() if v}
    if not alvo:
        return None, 0.0, 0

    exatos = [
        linha
        for linha, dados in tabela.items()
        if all(normalizar(dados.get(c)) == v for c, v in alvo.items())
    ]
    if exatos:
        return exatos[0], 1.0, len(exatos)

    melhor, melhor_score, empates = None, 0.0, 0
    for linha, dados in tabela.items():
        scores = []
        for c, v in alvo.items():
            atual = normalizar(dados.get(c))
            scores.append(SequenceMatcher(None, v, atual).ratio() if atual else 0.0)
        score = sum(scores) / len(scores)
        if score > melhor_score + 1e-9:
            melhor, melhor_score, empates = linha, score, 1
        elif melhor is not None and abs(score - melhor_score) <= 1e-9:
            empates += 1

    if melhor is not None and melhor_score >= limite:
        return melhor, melhor_score, empates
    return None, melhor_score, 0


def calcular_alteracoes(atuais: dict, valores: dict, excluir=()) -> list[dict]:
    resultado = []
    for coluna, (novo, origem) in valores.items():
        if coluna in excluir or novo in (None, ""):
            continue
        atual = atuais.get(coluna)
        if isinstance(atual, str) and atual.startswith("="):
            continue
        if normalizar(atual) == normalizar(novo):
            continue
        resultado.append({
            "coluna": coluna,
            "atual": atual,
            "novo": novo,
            "tipo": "preencher" if normalizar(atual) == "" else "alterar",
            "origem": origem,
        })
    return resultado

def _gravar(celula, valor) -> None:
    formato_geral = celula.number_format == "General"
    celula.value = valor
    if isinstance(valor, (datetime, date)) and formato_geral:
        celula.number_format = "DD/MM/YYYY"


def aplicar_alteracoes(
    arquivo: bytes,
    aba: str,
    esquema: dict,
    atualizacoes: list[tuple[int, str, object]],
    novas: list[dict],
) -> dict:
    wb = load_workbook(BytesIO(arquivo))
    ws = wb[aba]
    colunas = esquema["colunas"]
    falhas: list[str] = []
    celulas = 0

    for linha, nome_col, valor in atualizacoes:
        try:
            _gravar(ws.cell(linha, colunas[nome_col]), valor)
            celulas += 1
        except Exception as erro:
            falhas.append(f"linha {linha}, '{nome_col}': {erro}")

    modelo = esquema["ultima_linha"]
    tem_modelo = modelo > esquema["linha_cab"]
    proxima = esquema["ultima_linha"] + 1
    linhas_novas: list[int] = []

    for dados in novas:
        if tem_modelo: 
            for c in colunas.values():
                ws.cell(proxima, c)._style = copy(ws.cell(modelo, c)._style)
        for nome_col, valor in dados.items():
            try:
                _gravar(ws.cell(proxima, colunas[nome_col]), valor)
                celulas += 1
            except Exception as erro:
                falhas.append(f"linha nova {proxima}, '{nome_col}': {erro}")
        linhas_novas.append(proxima)
        proxima += 1

    saida = BytesIO()
    wb.save(saida)
    return {
        "arquivo": saida.getvalue(),
        "celulas": celulas,
        "linhas_novas": linhas_novas,
        "falhas": falhas,
    }


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