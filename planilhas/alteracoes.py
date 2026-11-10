
from copy import copy
from datetime import date, datetime
from io import BytesIO

from openpyxl import load_workbook

from planilhas.esquema import normalizar

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
