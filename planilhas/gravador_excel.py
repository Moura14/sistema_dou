
from openpyxl import load_workbook
from pathlib import Path


def enviar_para_planilha(caminho, dados, mapeamento, aba=None):
    caminho = Path(caminho)

    if not caminho.exists():
        raise FileNotFoundError(
            f"Planilha não encontrada: {caminho}"
        )

    
    workbook = load_workbook(caminho)

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

       
        nova_linha = planilha.max_row + 1

        for campo, cabecalho in mapeamento.items():
            coluna = cabecalhos[cabecalho.casefold()]
            planilha.cell(
                row=nova_linha,
                column=coluna,
                value=dados.get(campo)
            )

        
        workbook.save(caminho)

        return nova_linha

    finally:
        workbook.close()
