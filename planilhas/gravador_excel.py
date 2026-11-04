from copy import copy
from io import BytesIO

from openpyxl import load_workbook


def _norm(valor):
    return str(valor).strip().casefold() if valor is not None else ""


def listar_abas_e_cabecalhos(arquivo_excel, aba=None, linha_cabecalho=1):

    wb = load_workbook(BytesIO(arquivo_excel), read_only=True)
    try:
        ws = wb[aba] if aba else wb.active
        cabecalhos = [
            str(c).strip()
            for c in next(
                ws.iter_rows(
                    min_row=linha_cabecalho,
                    max_row=linha_cabecalho,
                    values_only=True,
                ),
                (),
            )
            if c is not None and str(c).strip()
        ]
        return wb.sheetnames, cabecalhos
    finally:
        wb.close()


def _ultima_linha_com_dados(ws, colunas, linha_cabecalho):
    for linha in range(ws.max_row, linha_cabecalho, -1):
        if any(ws.cell(linha, c).value not in (None, "") for c in colunas):
            return linha
    return linha_cabecalho


def enviar_para_planilha_em_memoria(
    arquivo_excel,
    dados,
    mapeamento,
    aba=None,
    linha_cabecalho=1,
    criar_colunas_faltantes=False,
    chave=None,
):
   
    wb = load_workbook(BytesIO(arquivo_excel))
    try:
        ws = wb[aba] if aba else wb.active

        cabecalhos = {}
        for col in range(1, ws.max_column + 1):
            valor = ws.cell(linha_cabecalho, col).value
            if valor is not None and str(valor).strip():
                cabecalhos[_norm(valor)] = col

        faltantes = [h for h in mapeamento.values() if _norm(h) not in cabecalhos]
        if faltantes:
            if not criar_colunas_faltantes:
                raise ValueError(f"Cabeçalhos não encontrados: {faltantes}")
            proxima = max(cabecalhos.values(), default=0) + 1
            for h in faltantes:
                if _norm(h) in cabecalhos:
                    continue
                ws.cell(linha_cabecalho, proxima, value=h)
                cabecalhos[_norm(h)] = proxima
                proxima += 1

        colunas = {campo: cabecalhos[_norm(h)] for campo, h in mapeamento.items()}
        ultima = _ultima_linha_com_dados(ws, colunas.values(), linha_cabecalho)

        
        existentes = set()
        if chave and chave in colunas:
            for linha in range(linha_cabecalho + 1, ultima + 1):
                v = ws.cell(linha, colunas[chave]).value
                if v not in (None, ""):
                    existentes.add(_norm(v))

        primeira_linha = ultima + 1
        linha_atual = ultima
        inseridos = 0
        ignorados = 0

        for registro in dados:
            if chave and chave in colunas:
                k = _norm(registro.get(chave))
                if k and k in existentes:
                    ignorados += 1
                    continue
                existentes.add(k)

            linha_atual += 1
            inseridos += 1

            for campo, col in colunas.items():
                valor = registro.get(campo)
                if isinstance(valor, list):
                    valor = ", ".join(map(str, valor))
                celula = ws.cell(linha_atual, col, value=valor)

                
                modelo = ws.cell(max(linha_atual - 1, linha_cabecalho), col)
                if modelo.has_style:
                    celula.font = copy(modelo.font)
                    celula.border = copy(modelo.border)
                    celula.fill = copy(modelo.fill)
                    celula.number_format = modelo.number_format
                    celula.alignment = copy(modelo.alignment)

        saida = BytesIO()
        wb.save(saida)
        return {
            "arquivo": saida.getvalue(),
            "primeira_linha": primeira_linha,
            "inseridos": inseridos,
            "ignorados": ignorados,
        }
    finally:
        wb.close()