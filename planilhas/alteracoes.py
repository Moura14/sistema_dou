
from copy import copy
from datetime import date, datetime
from io import BytesIO

from openpyxl import load_workbook

from planilhas.esquema import normalizar, valor_vazio
from openpyxl.formula.translate import Translator


def detectar_valores_padrao(tabela: dict[int, dict]) -> dict[str, object]:
    if len(tabela) < 2:
        return {}

    colunas = next(iter(tabela.values()), {}).keys()
    padroes = {}
    for coluna in colunas:
        valores = [
            linha.get(coluna)
            for linha in tabela.values()
            if not valor_vazio(linha.get(coluna))
        ]
        if len(valores) < 2 or any(
            isinstance(valor, str) and valor.startswith("=")
            for valor in valores
        ):
            continue

        valor_referencia = valores[0]
        if all(
            normalizar(valor) == normalizar(valor_referencia)
            for valor in valores[1:]
        ):
            padroes[coluna] = valor_referencia

    return padroes


def calcular_alteracoes(atuais: dict, valores: dict, excluir=()) -> list[dict]:
    resultado = []
    for coluna, (novo, origem) in valores.items():
        if coluna in excluir or valor_vazio(novo):
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

    for nome_col in esquema.get("colunas_novas", ()):
        indice = ws.max_column + 1
        colunas[nome_col] = indice
        cabecalho = ws.cell(esquema["linha_cab"], indice)
        cabecalho.value = nome_col
        if indice > 1:
            anterior = ws.cell(esquema["linha_cab"], indice - 1)
            if anterior.has_style:
                cabecalho._style = copy(anterior._style)

    for linha, nome_col, valor in atualizacoes:

        if valor_vazio(valor):
            continue

        try:
            _gravar(
                ws.cell(linha, colunas[nome_col]),
                valor
            )
            celulas += 1

        except Exception as erro:
            falhas.append(
                f"linha {linha}, '{nome_col}': {erro}"
            )

    
    modelo = esquema["ultima_linha"]
    linha_cab = esquema["linha_cab"]

    tem_modelo = modelo > linha_cab

    
    total_colunas = ws.max_column

    proxima = modelo + 1
    linhas_novas = []

  
    for dados in novas:

        if tem_modelo:

        
            for c in range(1, total_colunas + 1):

                origem = ws.cell(modelo, c)
                destino = ws.cell(proxima, c)

             
                valor_origem = origem.value

                if isinstance(valor_origem, str) and valor_origem.startswith("="):
                    try:
                        valor_origem = Translator(
                            valor_origem,
                            origin=origem.coordinate
                        ).translate_formula(destino.coordinate)
                    except Exception:
                        pass

                destino.value = valor_origem

          
                if origem.has_style:
                    destino._style = copy(origem._style)

            
                if origem.number_format:
                    destino.number_format = origem.number_format

                if origem.alignment:
                    destino.alignment = copy(origem.alignment)

                if origem.protection:
                    destino.protection = copy(origem.protection)

                if origem.hyperlink:
                    destino._hyperlink = copy(origem.hyperlink)

            
            altura = ws.row_dimensions[modelo].height

            if altura is not None:
                ws.row_dimensions[proxima].height = altura

        for nome_col in esquema.get("colunas_a_limpar_novas", ()):
            try:
                ws.cell(proxima, colunas[nome_col]).value = None
            except Exception as erro:
                falhas.append(
                    f"linha nova {proxima}, '{nome_col}': {erro}"
                )

       
        for nome_col, valor in dados.items():

            
            if valor_vazio(valor):
                continue

            try:
                _gravar(
                    ws.cell(proxima, colunas[nome_col]),
                    valor
                )
                celulas += 1

            except Exception as erro:
                falhas.append(
                    f"linha nova {proxima}, "
                    f"'{nome_col}': {erro}"
                )

        linhas_novas.append(proxima)
        proxima += 1

    
    saida = BytesIO()

    wb.save(saida)
    wb.close()

    return {
        "arquivo": saida.getvalue(),
        "celulas": celulas,
        "linhas_novas": linhas_novas,
        "falhas": falhas,
    }
