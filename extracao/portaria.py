
import re
import unicodedata


MESES = (
    "janeiro|fevereiro|março|marco|abril|maio|junho|"
    "julho|agosto|setembro|outubro|novembro|dezembro"
)

DATA_EXTENSO = rf"\d{{1,2}}\s+de\s+(?:{MESES})\s+de\s+\d{{4}}"


def normalizar_texto(texto):
    """Remove espaços repetidos sem eliminar as quebras de linha."""
    linhas = [
        re.sub(r"[ \t]+", " ", linha).strip()
        for linha in texto.splitlines()
    ]

    return "\n".join(linha for linha in linhas if linha)


def encontrar_um(padrao, texto, flags=re.IGNORECASE):
    resultado = re.search(padrao, texto, flags)
    return resultado.group(1).strip() if resultado else None


def extrair_nomes(texto):
    """
    Procura nomes em trechos relacionados a atos administrativos.
    É uma heurística inicial, não uma identificação infalível.
    """

    gatilhos = (
        r"(?:ao|a|do|da)\s+servidor(?:a)?"
        r"|nomear"
        r"|exonerar"
        r"|designar"
        r"|dispensar"
        r"|autorizar"
        r"|conceder"
        r"|ceder"
        r"|aposentar"
        r"|reconduzir"
        r"|redistribuir"
    )

    nome_maiusculo = (
        r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ]+"
        r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ]+){1,6})"
    )

    nomes = []

    for gatilho in re.finditer(gatilhos, texto, re.IGNORECASE):
        trecho = texto[gatilho.end():gatilho.end() + 180]

       
        candidato = re.match(
            r"[\s,:-]*" + nome_maiusculo,
            trecho
        )

        if candidato:
            nome = candidato.group(1).strip()

            if nome not in nomes:
                nomes.append(nome)

    return nomes


def identificar_tipo_ato(texto):
    regras = [
        ("nomeação", r"\bnomear\b|\bnomeia\b|\bnomeação\b"),
        ("exoneração", r"\bexonerar\b|\bexonera\b|\bexoneração\b"),
        ("designação", r"\bdesignar\b|\bdesigna\b|\bdesignação\b"),
        ("dispensa", r"\bdispensar\b|\bdispensa\b|\bdispensado\b"),
        ("aposentadoria", r"\baposentar\b|\baposentadoria\b"),
        ("cessão", r"\bceder\b|\bcessão\b|\bcedido\b"),
        ("licença", r"\blicença\b|\blicenciar\b"),
        ("teletrabalho", r"\bteletrabalho\b"),
        ("permuta", r"\bpermuta\b"),
        ("autorização", r"\bautorizar\b|\bautorização\b"),
        ("revogação", r"\brevogar\b|\brevogação\b"),
    ]

    texto_inicial = texto[:5000].lower()

    encontrados = [
        tipo
        for tipo, padrao in regras
        if re.search(padrao, texto_inicial)
    ]

    return encontrados


def extrair_informacoes(texto):
    texto = normalizar_texto(texto)

    
    titulo = re.search(
        rf"PORTARIA\s+(?:N[º°.]?\s*)?(\d+)\s*,?\s*DE\s+"
        rf"({DATA_EXTENSO})",
        texto,
        re.IGNORECASE
    )

    numero_portaria = titulo.group(1) if titulo else None
    data_portaria = titulo.group(2) if titulo else None

    
    data_publicacao = encontrar_um(
        r"Publicado em:\s*(\d{2}/\d{2}/\d{4})",
        texto
    )

    
    orgao = encontrar_um(
        r"Órgão:\s*([^\n]+)",
        texto
    )

    
    assunto = None

    if titulo:
        inicio = titulo.end()
        restante = texto[inicio:]

        preambulo = re.search(
            r"\n\s*(?:O|A)\s+"
            r"(?:MINISTRO|MINISTRA|SECRETÁRIO|SECRETÁRIA|"
            r"PRESIDENTE|PRESIDENTA)\b",
            restante,
            re.IGNORECASE
        )

        if preambulo:
            candidato = restante[:preambulo.start()].strip()
            candidato = re.sub(r"\s+", " ", candidato)

            if candidato:
                assunto = candidato

  
    if not assunto:
        artigo = re.search(
            r"Art\.\s*1º?\s*(.*?)(?=\n\s*Art\.\s*2º?|\Z)",
            texto,
            re.IGNORECASE | re.DOTALL
        )

        if artigo:
            assunto = re.sub(
                r"\s+", " ", artigo.group(1)
            ).strip()

    
    codigos = re.findall(
        r"\b(?:CCE|FCE)\s*\d+(?:\.\d+)+\b",
        texto,
        re.IGNORECASE
    )

    codigos = list(dict.fromkeys(
        codigo.upper().replace(" ", "")
        for codigo in codigos
    ))

    return {
        "numero_portaria": numero_portaria,
        "data_portaria": data_portaria,
        "data_publicacao": data_publicacao,
        "orgao": orgao,
        "assunto": assunto or None,
        "nomes": extrair_nomes(texto),
        "codigos_cargo": codigos,
        "tipos_ato_identificados": identificar_tipo_ato(texto),
    }
