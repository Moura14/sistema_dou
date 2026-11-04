
from io import BytesIO

from openpyxl import load_workbook


def _abrir_workbook(arquivo_excel):
    return load_workbook(BytesIO(arquivo_excel))


def listar_abas(arquivo_excel):
    workbook = _abrir_workbook(arquivo_excel)

    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def obter_cabecalhos(arquivo_excel, aba=None, linha_cabecalho=1):
    workbook = _abrir_workbook(arquivo_excel)

    try:
        if aba is not None and aba not in workbook.sheetnames:
            raise ValueError(f"A aba '{aba}' não existe na planilha.")

        planilha = workbook[aba] if aba else workbook.active
        cabecalhos = []

        for coluna in range(1, planilha.max_column + 1):
            valor = planilha.cell(linha_cabecalho, coluna).value

            if valor is not None and str(valor).strip():
                cabecalhos.append(str(valor).strip())

        return cabecalhos

    finally:
        workbook.close()


def enviar_para_planilha_em_memoria(
    arquivo_excel,
    dados,
    mapeamento,
    aba=None,
    chave=None
):
    workbook = _abrir_workbook(arquivo_excel)

    try:
        if aba is not None and aba not in workbook.sheetnames:
            raise ValueError(f"A aba '{aba}' não existe na planilha.")

        planilha = workbook[aba] if aba else workbook.active

        cabecalhos = {}

        for coluna in range(1, planilha.max_column + 1):
            valor = planilha.cell(1, coluna).value

            if valor is not None and str(valor).strip():
                nome = str(valor).strip().casefold()
                cabecalhos[nome] = coluna

        
        colunas_destino = {}
        faltantes = []

        for cabecalho, campo in mapeamento.items():
            nome = str(cabecalho).strip().casefold()

            if nome not in cabecalhos:
                faltantes.append(cabecalho)
            else:
                colunas_destino[cabecalho] = (
                    cabecalhos[nome],
                    campo
                )

        if faltantes:
            raise ValueError(
                f"Cabeçalhos não encontrados na aba "
                f"'{planilha.title}': {faltantes}"
            )

        
        coluna_chave = None

        if chave:
            for coluna, campo in colunas_destino.values():
                if campo == chave:
                    coluna_chave = coluna
                    break

            if coluna_chave is None:
                raise ValueError(
                    f"O campo '{chave}' precisa estar mapeado "
                    "para verificar duplicatas."
                )

        existentes = set()

        if coluna_chave:
            for linha in range(2, planilha.max_row + 1):
                valor = planilha.cell(
                    row=linha,
                    column=coluna_chave
                ).value

                if valor is not None:
                    existentes.add(str(valor).strip().casefold())

        primeira_linha = planilha.max_row + 1
        inseridos = 0
        ignorados = 0

        for registro in dados:
            valor_chave = registro.get(chave) if chave else None

            if coluna_chave and valor_chave is not None:
                identificador = str(valor_chave).strip().casefold()

                if identificador in existentes:
                    ignorados += 1
                    continue

                existentes.add(identificador)

            nova_linha = planilha.max_row + 1

            for coluna, campo in colunas_destino.values():
                valor = registro.get(campo)

                if isinstance(valor, (list, tuple)):
                    valor = ", ".join(map(str, valor))

                planilha.cell(
                    row=nova_linha,
                    column=coluna,
                    value=valor
                )

            inseridos += 1

        arquivo_saida = BytesIO()
        workbook.save(arquivo_saida)
        arquivo_saida.seek(0)

        return {
            "primeira_linha": primeira_linha,
            "arquivo": arquivo_saida.getvalue(),
            "inseridos": inseridos,
            "ignorados": ignorados,
        }

    finally:
        workbook.close()
