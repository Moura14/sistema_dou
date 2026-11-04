
import re
import unicodedata


ACOES = {
    "Nomeação": "NOMEAR",
    "Exoneração": "EXONERAR",
    "Dispensa": "DISPENSAR",
    "Designação": "DESIGNAR",
    "Aposentadoria": "APOSENTAR",
    "Cessão": "CEDER",
    "Revogação": "REVOGAR",
    "Recondução": "RECONDUZIR",
    "Redistribuição": "REDISTRIBUIR",
}


def normalizar_texto(texto):
    linhas = [
        re.sub(r"[ \t]+", " ", linha).strip()
        for linha in texto.splitlines()
    ]
    return "\n".join(linha for linha in linhas if linha)


def limpar(texto):
    if not texto:
        return None
    return re.sub(r"\s+", " ", texto).strip(" ,;:-")


def identificar_acao(texto):
    padrao = (
        r"\b(NOMEAR|EXONERAR|DISPENSAR|DESIGNAR|"
        r"APOSENTAR|CEDER|REVOGAR|RECONDUZIR|REDISTRIBUIR|"
        r"NOMEAD[AO]|EXONERAD[AO]|DISPENSAD[AO]|DESIGNAD[AO])\b"
    )

    resultado = re.search(padrao, texto, re.IGNORECASE)

    if not resultado:
        return None, None

    verbo = resultado.group(1).upper()

    equivalencias = {
        "NOMEADA": "NOMEAR",
        "NOMEADO": "NOMEAR",
        "EXONERADA": "EXONERAR",
        "EXONERADO": "EXONERAR",
        "DISPENSADA": "DISPENSAR",
        "DISPENSADO": "DISPENSAR",
        "DESIGNADA": "DESIGNAR",
        "DESIGNADO": "DESIGNAR",
    }

    verbo = equivalencias.get(verbo, verbo)

    tipo = next(
        (nome for nome, acao in ACOES.items() if acao == verbo),
        None
    )

    return tipo, resultado


def extrair_nome_depois_acao(texto, resultado_acao):
    if not resultado_acao:
        return None

    trecho = texto[resultado_acao.end():]

   
    nome_passivo = re.search(
        r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ]+"
        r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]+){1,8})"
        r"\s+para\s+exercer",
        trecho
    )

    if nome_passivo:
        return limpar(nome_passivo.group(1))

    
    nome_normal = re.search(
        r"\s*,?\s*"
        r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ]+"
        r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]+){1,8})"
        r"(?=\s*(?:,|"
        r"\s+da\s+função|\s+do\s+cargo|"
        r"\s+para\s+exercer|\s+do\s+emprego))",
        trecho
    )

    if nome_normal:
        return limpar(nome_normal.group(1))

    return None


def extrair_codigo(bloco):
    codigos = re.findall(
        r"\b(?:FCE|CCE)\s*\d+(?:\.\d+)+\b",
        bloco,
        re.IGNORECASE
    )

    return list(dict.fromkeys(
        codigo.upper().replace(" ", "")
        for codigo in codigos
    ))


def sugerir_campo_para_cabecalho(cabecalho, campos_disponiveis):
    normalizado = unicodedata.normalize("NFKD", str(cabecalho))
    normalizado = normalizado.encode("ascii", "ignore").decode("ascii").casefold()
    palavras = set(re.findall(r"[a-z0-9]+", normalizado))

    sugestoes = (
        ("codigos_cargo", {"codigo", "codigos"}, {"ce", "cce", "fce", "cargo", "funcao"}),
        ("numero_portaria", {"numero", "n"}, {"portaria"}),
        ("data_portaria", {"data"}, {"portaria"}),
        ("data_publicacao", {"data"}, {"publicacao"}),
        ("data_efeito", {"data"}, {"efeito", "inicio", "fim"}),
        ("tipo_ato", {"tipo"}, {"ato", "portaria"}),
        ("tipo_ato", {"motivo"}, set()),
        ("tipo_ato", {"ato"}, set()),
        ("nome", {"nome"}, set()),
        ("cpf", {"cpf"}, set()),
        ("cargo", {"cargo", "funcao"}, set()),
        ("orgao", {"orgao"}, set()),
        ("ministerio", {"ministerio"}, set()),
        ("texto_original_ato", {"texto"}, {"original", "ato"}),
        ("arquivo", {"arquivo", "documento"}, set()),
    )

    for campo, gatilhos, termos in sugestoes:
        if campo in campos_disponiveis and gatilhos.issubset(palavras):
            if not termos or palavras.intersection(termos):
                return campo

    return None


def extrair_cargo(bloco):
    cargo = re.search(
        r"(?:da função de|do cargo de|"
        r"para exercer a função de|"
        r"para exercer o cargo de)\s*(.+?)"
        r"(?=,\s*(?:código|a partir|ficando)|"
        r"\s+código\s|$)",
        bloco,
        re.IGNORECASE | re.DOTALL
    )

    if cargo:
        return limpar(cargo.group(1))

    
    cargo_individual = re.search(
        r"para exercer\s+(?:a função|o cargo)\s+de\s+"
        r"(.+?)(?=\s+(?:na|no)\s+|,|$)",
        bloco,
        re.IGNORECASE | re.DOTALL
    )

    return limpar(cargo_individual.group(1)) if cargo_individual else None


def extrair_data_efeito(bloco):
    resultado = re.search(
        r"(?:a partir de|a contar de|"
        r"com efeitos a partir de)\s*"
        r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|"
        r"\d{2}/\d{2}/\d{4})",
        bloco,
        re.IGNORECASE
    )

    return limpar(resultado.group(1)) if resultado else None


def extrair_informacoes(texto):
    texto = normalizar_texto(texto)

    publicacao = re.search(
        r"Publicado em:\s*(\d{2}/\d{2}/\d{4})",
        texto,
        re.IGNORECASE
    )

    orgao = re.search(
        r"Órgão:\s*([^\n]+)",
        texto,
        re.IGNORECASE
    )

    data_documento = re.search(
        r"(?im)^\s*PORTARIAS?\b[^\n]*?"
        r"\bDE\s+(\d{1,2}\s+DE\s+"
        r"(?:JANEIRO|FEVEREIRO|MARÇO|MARCO|ABRIL|MAIO|"
        r"JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|"
        r"NOVEMBRO|DEZEMBRO)\s+DE\s+\d{4})",
        texto,
        re.IGNORECASE
)

    registros = []

    
    padrao_numero = (
        r"(?im)^\s*(?:PORTARIAS?\b[^\n]*?)?"
        r"\bN\s*[º°.]?\s*([\d]+(?:\.[\d]+)*)"
        r"\s*(?=(?:[-–—]\s*|,?\s+DE\b))"
)

    ocorrencias = list(re.finditer(padrao_numero, texto))

    for i, ocorrencia in enumerate(ocorrencias):

        inicio = ocorrencia.start()

        fim = (
            ocorrencias[i + 1].start()
            if i + 1 < len(ocorrencias)
            else len(texto)
        )

        bloco = texto[inicio:fim]
        numero = ocorrencia.group(1)

        trecho_acao = texto[ocorrencia.end():fim]

        tipo_ato, acao = identificar_acao(trecho_acao)

        nome = extrair_nome_depois_acao(
            trecho_acao, acao
        )

        texto_anterior = texto[:inicio]

        ministerios = list(re.finditer(
            r"(?im)^\s*(MINISTÉRIO .+)$",
            texto_anterior
        ))

        ministerio = (
            limpar(ministerios[-1].group(1))
            if ministerios else None
        )

        registros.append({
            "numero_portaria": numero,
            "data_portaria": (
                data_documento.group(1)
                if data_documento else None
            ),
            "data_publicacao": (
                publicacao.group(1)
                if publicacao else None
            ),
            "orgao": limpar(orgao.group(1)) if orgao else None,
            "ministerio": ministerio,
            "tipo_ato": tipo_ato,
            "nome": nome,
            "cargo": extrair_cargo(bloco),
            "codigos_cargo": extrair_codigo(bloco),
            "data_efeito": extrair_data_efeito(bloco),
            "texto_original_ato": limpar(bloco),
        })

  
    if not registros:

        titulo = re.search(
            r"(?im)^\s*PORTARIAS?\b[^\n]*?"
            r"\bN\s*[º°.]?\s*"
            r"([\d]+(?:\.[\d]+)*)"
            r"\s*,?\s*DE\s+([^\n]+)",
            texto
)

        if titulo:
            numero = titulo.group(1)
            data_portaria = limpar(titulo.group(2))

            tipo_ato, acao = identificar_acao(texto)

            nome = extrair_nome_depois_acao(texto, acao)

            registros.append({
                "numero_portaria": numero,
                "data_portaria": data_portaria,
                "data_publicacao": (
                    publicacao.group(1)
                    if publicacao else None
                ),
                "orgao": limpar(orgao.group(1)) if orgao else None,
                "ministerio": None,
                "tipo_ato": tipo_ato,
                "nome": nome,
                "cargo": extrair_cargo(texto),
                "codigos_cargo": extrair_codigo(texto),
                "data_efeito": extrair_data_efeito(texto),
                "texto_original_ato": limpar(texto),
            })

    return registros
