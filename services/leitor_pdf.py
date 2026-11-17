import fitz


FATOR_ESPACO = 0.15


def _texto_da_pagina(pagina, fator=FATOR_ESPACO):
    dados = pagina.get_text("rawdict")
    linhas = []
    for bloco in dados["blocks"]:
        if bloco.get("type") != 0: 
            continue
        for linha in bloco["lines"]:
            partes, ultimo_x1 = [], None
            for span in linha["spans"]:
                limite = span["size"] * fator
                for ch in span["chars"]:
                    x0, _, x1, _ = ch["bbox"]
                    if (
                        ultimo_x1 is not None
                        and ch["c"] != " "
                        and partes
                        and partes[-1] != " "
                        and x0 - ultimo_x1 > limite
                    ):
                        partes.append(" ")
                    partes.append(ch["c"])
                    ultimo_x1 = x1
            linhas.append("".join(partes))
    return "\n".join(linhas)


def extrair_texto_pdf(arquivo_pdf):
    paginas = []

    documento = fitz.open(stream=arquivo_pdf, filetype="pdf")

    try:
        for numero, pagina in enumerate(documento, start=1):
            paginas.append({
                "pagina": numero,
                "texto": _texto_da_pagina(pagina).strip(),
            })
    finally:
        documento.close()

    return paginas