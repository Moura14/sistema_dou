
from io import BytesIO
from openpyxl import load_workbook

from planilhas.esquema import _tipo_coluna

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
