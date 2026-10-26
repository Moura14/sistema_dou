
import re
from datetime import datetime


def buscar(padrao, texto, grupo=1):
    resultado = re.search(
        padrao,
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )

    if resultado:
        return resultado.group(grupo).strip()

    return None


def extrair_informacoes(texto):
    # Uniformiza espaços sem remover a estrutura dos artigos.
    texto = re.sub(r"\s+", " ", texto).strip()

    # Nome e matrícula do servidor.
    nome = buscar(
        r"ao servidor\s+(.+?),\s*matrícula\s+SIAPE",
        texto
    )

    matricula = buscar(
        r"matrícula\s+SIAPE\s+n[º°o.]?\s*([\d.-]+)",
        texto
    )

    # Processo administrativo.
    processo = buscar(
        r"Processo\s+n[º°o.]?\s*([\d./-]+)",
        texto
    )

    # Local de teletrabalho no exterior.
    pais = buscar(
        r"no exterior,\s*na\s+([^,;.]+)",
        texto
    )

    # Prazo em meses.
    prazo = buscar(
        r"pelo prazo de\s+(\d+)\s*\(?(?:doze|um|dois|três|tres|"
        r"quatro|cinco|seis|sete|oito|nove|dez|onze|"
        r"treze|catorze|quatorze|quinze|dezesseis|"
        r"dezessete|dezoito|dezenove|vinte)?\)?\s*meses?",
        texto
    )

    # Data de início da autorização.
    inicio = buscar(
        r"a contar de\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
        texto
    )

    # Classificação preliminar pelo conteúdo.
    texto_lower = texto.lower()

    if "teletrabalho" in texto_lower:
        tipo = "Autorização para teletrabalho"
    elif "nomear" in texto_lower or "nomeação" in texto_lower:
        tipo = "Nomeação"
    elif "exonerar" in texto_lower or "exoneração" in texto_lower:
        tipo = "Exoneração"
    elif "aposentadoria" in texto_lower or "aposentar" in texto_lower:
        tipo = "Aposentadoria"
    elif "cessão" in texto_lower or "ceder" in texto_lower:
        tipo = "Cessão"
    elif "remoção" in texto_lower or "remover" in texto_lower:
        tipo = "Remoção"
    elif "licença" in texto_lower:
        tipo = "Licença"
    else:
        tipo = "Não identificado"

    return {
        "tipo_de_ato": tipo,
        "nome_servidor": nome,
        "matricula_siape": matricula,
        "pais": pais,
        "prazo_meses": prazo,
        "data_inicio": inicio,
        "processo": processo,
        "texto_original": texto
    }


if __name__ == "__main__":
    texto_exemplo = """
    O MINISTRO DE ESTADO DO ESPORTE, considerando o constante
    do Processo nº 71000.069593/2026-14, resolve:
    Art. 1º Conceder ao servidor CARLOS EUGÊNIO ZARDINI FILHO,
    matrícula SIAPE nº 1732811, autorização para teletrabalho
    no exterior, na Austrália, a critério da Administração,
    pelo prazo de 12 (doze) meses, a contar de
    17 de novembro de 2026.
    Art. 2º Esta Portaria entra em vigor na data de sua publicação.
    """

    resultado = extrair_informacoes(texto_exemplo)

    for campo, valor in resultado.items():
        print(f"{campo}: {valor}")
