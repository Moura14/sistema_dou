
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

    # 1. Atualizar registros existentes
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

    # 2. Identificar a última linha preenchida
    modelo = esquema["ultima_linha"]
    linha_cab = esquema["linha_cab"]

    tem_modelo = modelo > linha_cab

    # Guardar a quantidade de colunas antes das inclusões
    total_colunas = ws.max_column

    proxima = modelo + 1
    linhas_novas = []

    # 3. Criar novos registros
    for dados in novas:

        if tem_modelo:

            # Copiar TODOS os valores e formatações
            # da última linha preenchida.
            for c in range(1, total_colunas + 1):

                origem = ws.cell(modelo, c)
                destino = ws.cell(proxima, c)

                # Copiar valor ou fórmula
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

                # Copiar formatação
                if origem.has_style:
                    destino._style = copy(origem._style)

                # Copiar outras propriedades
                if origem.number_format:
                    destino.number_format = origem.number_format

                if origem.alignment:
                    destino.alignment = copy(origem.alignment)

                if origem.protection:
                    destino.protection = copy(origem.protection)

                if origem.hyperlink:
                    destino._hyperlink = copy(origem.hyperlink)

            # Copiar altura da linha
            altura = ws.row_dimensions[modelo].height

            if altura is not None:
                ws.row_dimensions[proxima].height = altura

        for nome_col in esquema.get("colunas_ignoradas", ()):
            try:
                ws.cell(proxima, colunas[nome_col]).value = None
            except Exception as erro:
                falhas.append(
                    f"linha nova {proxima}, '{nome_col}': {erro}"
                )

        # 4. Substituir somente os campos recebidos
        for nome_col, valor in dados.items():

            # Não substituir valores herdados por campos vazios
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

    # 5. Salvar arquivo
    saida = BytesIO()

    wb.save(saida)
    wb.close()

    return {
        "arquivo": saida.getvalue(),
        "celulas": celulas,
        "linhas_novas": linhas_novas,
        "falhas": falhas,
    }
