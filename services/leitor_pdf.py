import fitz


def extrair_texto_pdf(arquivo_pdf):
    paginas = []

    documento = fitz.open(stream=arquivo_pdf, filetype="pdf")

    try:
        for numero, pagina in enumerate(documento, start=1):
            texto = pagina.get_text("text")

            paginas.append({
                "pagina": numero,
                "texto": texto.strip()
            })
    finally:
        documento.close()

    return paginas