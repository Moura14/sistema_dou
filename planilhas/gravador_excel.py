
from openpyxl import load_workbook
from io import BytesIO


def enviar_para_planilha_em_memoria(
    arquivo_excel,
    dados,
    mapeamento,
    aba=None
):
    workbook = load_workbook(
        BytesIO(arquivo_excel)
    )

    try:
        planilha = (
            workbook[aba] if aba
            else workbook.active
        )

        cabecalhos = {}

        for coluna in range(1, planilha.max_column + 1):
            valor = planilha.cell(1, coluna).value

            if valor is not None:
                cabecalhos[str(valor).strip().casefold()] = coluna

        faltantes = [
            cabecalho
            for cabecalho in mapeamento.values()
            if cabecalho.casefold() not in cabecalhos
        ]

        if faltantes:
            raise ValueError(
                f"Cabeçalhos não encontrados: {faltantes}"
            )

        primeira_linha = planilha.max_row + 1

        for registro in dados:
            nova_linha = planilha.max_row + 1

            for campo, cabecalho in mapeamento.items():
                coluna = cabecalhos[cabecalho.casefold()]
                valor = registro.get(campo)

                if isinstance(valor, list):
                    valor = ", ".join(map(str, valor))

                planilha.cell(
                    row=nova_linha,
                    column=coluna,
                    value=valor
                )

        arquivo_saida = BytesIO()
        workbook.save(arquivo_saida)
        arquivo_saida.seek(0)

        return primeira_linha, arquivo_saida.getvalue()

    finally:
        workbook.close()
