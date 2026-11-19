import re
import unicodedata
from bisect import bisect_right

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
    "Transferência": "TRANSFERIR",
    "Remoção": "REMOVER",
    "Prorrogação": "PRORROGAR",
    "Concessão": "CONCEDER",
    "Afastamento": "AFASTAR",
    "Lotação": "LOTAR",
    "Substituição": "SUBSTITUIR",
    "Renovação": "RENOVAR",
    "Tornar sem efeito": "TORNAR SEM EFEITO",
    "Demissão": "DEMITIR",
}

_RAIZES = (
    ("nomea", "Nomeação"), ("exoner", "Exoneração"), ("dispens", "Dispensa"),
    ("design", "Designação"), ("aposent", "Aposentadoria"), ("ced", "Cessão"),
    ("revog", "Revogação"), ("recondu", "Recondução"),
    ("redistribu", "Redistribuição"), ("transfer", "Transferência"),
    ("remov", "Remoção"), ("prorrog", "Prorrogação"), ("conced", "Concessão"),
    ("afast", "Afastamento"), ("lot", "Lotação"), ("substitu", "Substituição"),
    ("renov", "Renovação"),
    ("tornar", "Tornar sem efeito"),
    ("tornad", "Tornar sem efeito"), ("demit", "Demissão"),
)
_INF = (r"tornar\s+sem\s+efeito|demitir|nomear|exonerar|dispensar|designar|aposentar|ceder|revogar|"
        r"reconduzir|redistribuir|transferir|remover|prorrogar|conceder|afastar|lotar|substituir|renovar")
_PART = (r"tornad[oa]s?\s+sem\s+efeito|demitid[oa]s?|nomead[oa]s?|exonerad[oa]s?|dispensad[oa]s?|designad[oa]s?|"
         r"aposentad[oa]s?|cedid[oa]s?|revogad[oa]s?|reconduzid[oa]s?|"
         r"redistribuíd[oa]s?|transferid[oa]s?|removid[oa]s?|prorrogad[oa]s?|concedid[oa]s?|"
         r"afastad[oa]s?|lotad[oa]s?|substituíd[oa]s?|renovad[oa]s?")
RE_INFINITIVO = re.compile(rf"\b(?:{_INF})\b", re.I)
RE_ACAO = re.compile(rf"\b({_INF}|{_PART})\b", re.I)
RE_PASSADO = re.compile(
    r"\bque\s+(?:nomeou|exonerou|dispensou|designou|aposentou|cedeu|revogou|"
    r"reconduziu|redistribuiu|transferiu|removeu|prorrogou|concedeu|afastou|lotou|substituiu|renovou)\b", re.I)
RE_PORTARIA_REF = re.compile(
    r"\bPortaria(?:\s+((?:de\s+Pessoal\s+)?[A-Z][A-Za-z/.\-]*))?\s+n\s*[º°o.]?\s*(\d+(?:\.\d+)*)", re.I)
RE_VIGOR = re.compile(r"entra\s+em\s+vigor\s+na\s+data\s+d[ea]\s+(?:sua|presente)\s+publicação", re.I)
RE_RESOLVE = re.compile(r"\bresolve(?:m)?\s*:?", re.I)

MESES = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")
_NUM_MES = {m: i for i, m in enumerate(MESES, 1)}
_MESES_RE = "|".join(MESES).replace("marco", "mar[cç]o").upper()




def _sem_acento(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii").lower()


_RE_LIXO = re.compile(
    r"(?mi)^[^\n]*(?:ISSN\s*\d|Documento assinado digitalmente|Este documento pode ser verificado|"
    r"que institui a Infraestrutura|autenticidade\.html|DI[ÁA]RIO OFICIAL DA UNI[ÃA]O\s*-\s*Se)[^\n]*$"
    r"|^\s*Se[çc][ãa]o\s+\d+\s*$"
    r"|^\s*Nº\s+\d+,\s*(?:segunda|terça|quarta|quinta|sexta)-feira[^\n]*$"
)


_VERBOS_MAIUSC = (
    "NOMEAR", "EXONERAR", "DISPENSAR", "DESIGNAR", "APOSENTAR", "CEDER", "REVOGAR",
    "RECONDUZIR", "REDISTRIBUIR", "TRANSFERIR", "REMOVER", "PRORROGAR", "CONCEDER",
    "AFASTAR", "LOTAR", "SUBSTITUIR", "RENOVAR", "DEMITIR",
)
_RE_VERBO_ESPACADO = re.compile(
    r"(?m)^([ \t]*(?:Art\.?\s*\d+\s*[º°]?\s*|N[º°.]?\s*\d[\d.]*\s*[-–—]\s*)?)"
    r"((?:" + "|".join(r"\s*".join(v) for v in _VERBOS_MAIUSC) + r"))"
    r"(?=[ \t]*(?:,|$))"
)


def _juntar_verbo(m):
    return m.group(1) + re.sub(r"\s+", "", m.group(2))


_RE_SUMARIO = re.compile(
    r"(?mi)^[ \t]*SUM[ÁA]RIO[ \t]*$"
    r"|^[^\n]*(?:\.[ \t]*){4,}\d{1,4}[ \t]*$"
    r"|^[ \t]*P[áa]g(?:ina|\.)?[ \t]*\d+[ \t]*$"
)


def normalizar_texto(texto):
    texto = _RE_LIXO.sub("", texto)
    texto = _RE_SUMARIO.sub("", texto)
    texto = _RE_VERBO_ESPACADO.sub(_juntar_verbo, texto)
    texto = texto.replace("\xa0", " ").replace("\u00ad", "")
    texto = re.sub(r"(\w)-\n(?=[a-zà-ú])", r"\1", texto)
    texto = re.sub(r"(?<=[a-zà-ú])(?=[A-ZÀ-Ý]{2})", " ", texto)          
    texto = re.sub(r"(\bArt\.?\s*\d+\s*[º°]?)(?=[A-Za-zÀ-ú])", r"\1 ", texto) 
    texto = re.sub(r"(?<=[.;])[ \t]+(?=N[º°]\s*\d[\d.]*\s*[-–—]\s)", "\n", texto)
    linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in texto.splitlines()]
    return "\n".join(l for l in linhas if l)


def limpar(texto):
    if not texto:
        return None
    return re.sub(r"\s+", " ", texto).strip(" ,;:-") or None


def normalizar_data(txt):
    if not txt:
        return None
    t = _sem_acento(txt)
    m = re.search(r"(\d{1,2})\s*o?\s+(?:de\s+)?([a-z]+)\s+de\s+(\d{4})", t)
    if m and m.group(2) in _NUM_MES:
        return f"{int(m.group(1)):02d}/{_NUM_MES[m.group(2)]:02d}/{m.group(3)}"
    m = re.search(r"(\d{1,2})o?[/.](\d{1,2})[/.](\d{4})", t)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    return limpar(txt)


def _tipo_do_verbo(verbo):
    v = verbo.lower()
    return next((tipo for raiz, tipo in _RAIZES if v.startswith(raiz)), None)


def _inicio_dispositivo(texto):
    m = RE_RESOLVE.search(texto)
    return m.end() if m else 0


def identificar_acao(texto):
    m = RE_ACAO.search(texto, _inicio_dispositivo(texto)) or RE_ACAO.search(texto)
    if not m:
        return None, None
    return _tipo_do_verbo(m.group(1)), m


def dividir_atos(corpo):
    ini = _inicio_dispositivo(corpo)
    marcas = [m.start() for m in RE_INFINITIVO.finditer(corpo, ini)]
    if not marcas and ini:
        ini = 0
        marcas = [m.start() for m in RE_INFINITIVO.finditer(corpo)]
    if len(marcas) <= 1:
        return [corpo[ini:]] if ini else [corpo]
    marcas.append(len(corpo))
    return [corpo[a:b] for a, b in zip(marcas, marcas[1:])]




_PAL = r"[A-ZÀ-Ý][A-ZÀ-Ýa-zà-ÿ'’\-]*"
_NOME = _PAL + r"(?:\s+(?:d[aeo]s?\s+|e\s+)?" + _PAL + r"){1,8}"
_DATA_CURTA = r"\d{1,2}[º°]?\s+de\s+[a-zç]+\s+de\s+\d{4}|\d{1,2}[º°]?/\d{1,2}/\d{4}"
_RE_NOME = re.compile(
    r"^[\s,:;\-]*"
    r"(?:(?:a\s+pedido|de\s+ofício|a\s+(?:contar|partir)\s+d[eo]\s+(?:" + _DATA_CURTA + r"))\s*,?\s*)*"
    r"(?:(?:o|a)\s+)?"
    r"(?:exerc[ií]cio\s+d[eo]\s+mandato\s+d[oa]\s+)?"
    r"(?:(?:servidor|servidora|conselheiro|conselheira|Senhor|Senhora|Sr|Sra)\.?\s+)?"
    r"(" + _NOME + r")"
    r"(?=\s*[,(;]|\s+(?:para|do|da|no|na|à|ao|como|CPF|matrícula|SIAPE|ocupante)\b)"
)
_MAIUSC = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇÑ]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇÑ]+){1,8}"
_RE_NOME_PASSIVO = re.compile(r"(" + _MAIUSC + r")\s+para\s+exercer")
_RE_NOME_SOLTO = re.compile(
    r"(" + _MAIUSC + r")(?=\s*(?:,|\s+da\s+função|\s+à\s+função|\s+do\s+cargo|\s+para\s+exercer|\s+do\s+emprego))")
_MAIUSC_NOME = r"[A-ZÀ-Ý][A-ZÀ-Ý'’\-]+(?:\s+[A-ZÀ-Ý][A-ZÀ-Ý'’\-]+){1,8}"
_NAO_NOME_EXTRA = {"ministerio", "conselho", "federal", "uniao", "republica", "presidencia",
                   "nacional", "fazenda", "casa", "civil", "cpf", "siape", "sei", "art",
                   "decreto", "lei", "diario", "oficial", "mf", "se", "orgao", "turma",
                   "camara", "secao", "julgamento", "administrativo", "recursos", "fiscais",
                   "sistema", "fundo", "programa", "comite", "comissao", "unidade"}
_NAO_NOME = {"cargo", "funcao", "ministro", "ministra", "portaria", "chefe",
             "diretor", "diretora", "secretario", "secretaria", "coordenador",
             "coordenadora", "gabinete", "assessor", "assessora"}


def _nome_valido(nome):
    if not nome:
        return None
    palavras = nome.split()
    if not 2 <= len(palavras) <= 10 or any(c.isdigit() for c in nome):
        return None
    if any(_sem_acento(p) in _NAO_NOME for p in palavras):
        return None
    return nome


def _aparar_nome(nome):
    """Nome em MAIÚSCULAS seguido de palavras em caixa mista: corta onde a caixa muda."""
    if not nome:
        return nome
    palavras = nome.split()
    if not palavras[0].isupper():
        return nome
    saida = []
    for i, p in enumerate(palavras):
        conector = p.lower() in _MINUSC and i + 1 < len(palavras) and palavras[i + 1].isupper()
        if p.isupper() or conector:
            saida.append(p)
        else:
            break
    return " ".join(saida)


def _nome_fallback(resto):
    for m in re.finditer(_MAIUSC_NOME, resto):
        nome = limpar(m.group(0))
        palavras = [_sem_acento(p) for p in nome.split()]
        if any(p in _NAO_NOME_EXTRA for p in palavras):
            continue
        if _nome_valido(nome):
            return nome
    return None


_RE_NOME_SERVIDOR = re.compile(
    r"\b(?i:servidora?|empregad[oa])\s+(" + _MAIUSC_NOME + r")(?=\s*,)"
)
_RE_NOME_ANTES_MATRICULA = re.compile(
    r"(" + _MAIUSC_NOME + r")\s*,\s*[^,;]{3,100}?\s*,\s*(?i:matr[ií]cula)\b"
)


def extrair_nome_depois_acao(texto, resultado_acao):
    if not resultado_acao:
        return None
    resto = texto[resultado_acao.end():]
    m = _RE_NOME.search(resto[:250])
    if m:
        return _nome_valido(_aparar_nome(limpar(m.group(1))))

    # nome distante do verbo: "a servidora NOME," ou "NOME, Cargo, matrícula"
    for padrao in (_RE_NOME_SERVIDOR, _RE_NOME_ANTES_MATRICULA):
        m = padrao.search(resto[:1500])
        if m and _nome_valido(limpar(m.group(1))):
            return _nome_valido(limpar(m.group(1)))

    for padrao in (_RE_NOME_PASSIVO, _RE_NOME_SOLTO):
        m = padrao.search(resto[:400])
        if m and _nome_valido(limpar(m.group(1))):
            return _nome_valido(limpar(m.group(1)))
    return _nome_fallback(resto[:300])


_PARADA_CARGO = (
    r"(?=\s*(?:,(?!\s*(?-i:[A-ZÀ-Ý][a-zà-ÿ]))|[;:])"
    r"|\s+(?:código|(?-i:CCE|FCE|FCPE|DAS|FG|CD|NE))\b"
    r"|\.(?:\s|$)|\s+a\s+partir\b|\s+ficando\b|\s+e\s*$|$)"
)
_RE_CARGO = re.compile(
    r"\b(?:cargo|função|emprego|mandato|encargo)"
    r"(?:\s+(?:em\s+comissão|de\s+confiança|de\s+natureza\s+especial|"
    r"comissionad[oa]|efetiv[oa]))*"
    r"(?:\s+(?-i:[A-ZÀ-Ý][\wà-ÿ\-]*)){0,3}"
    r"\s+de\s+(.{1,220}?)" + _PARADA_CARGO,
    re.I | re.S,
)
_RE_CARGO_APOS_CPF = re.compile(
    r"CPF\s*(?:n[ºo°]\s*)?[\d*.\-]+\s*,\s*(.{3,150}?)\s*"
    r"(?=,\s*(?:código|(?-i:CCE|FCE|FCPE|DAS|FG|CD|NE))\b)",
    re.I | re.S,
)
_RE_CARGO_APOS_NOME = re.compile(r",\s*([^,]{3,120}?),\s*[Mm]atrícula\s+(?i:siape)")
_RE_CODIGO = re.compile(
    r"\b((?i:CCE|FCE|FCPE)|DAS|FG|CD|CGE|FUC|FST|NE)[\s\-]*(\d+(?:[.,]\d+)*)\b"
)


def extrair_cargo(bloco):
    m = (_RE_CARGO.search(bloco) or _RE_CARGO_APOS_CPF.search(bloco)
         or _RE_CARGO_APOS_NOME.search(bloco))
    return limpar(m.group(1)) if m else None


def extrair_codigo(bloco):
    codigos = [f"{s.upper()}{n}" for s, n in _RE_CODIGO.findall(bloco)]
    if not codigos:
        letra = re.search(r"\bLetra\s+[\"“”]?([A-Z])[\"“”]?", bloco)
        if letra:
            codigos = [f"Letra {letra.group(1)}"]
    return ", ".join(dict.fromkeys(codigos))




_RE_CPF = re.compile(
    r"\bCPF(?:\s*/\s*M\.?\s*F\.?)?\b\s*"
    r"(?:(?:sob\s+(?:o\s+)?)?n[ºo°.]?\s*)?[:\-]?\s*"
    r"([*Xx\d]{2,3}[.\s-]?"
    r"[*Xx\d]{3}[.\s-]?"
    r"[*Xx\d]{3}[.\s-]?"
    r"[*Xx\d]{2})",
    re.IGNORECASE
)


_RE_SIAPE = re.compile(
    r"\b(?:(?:Matrícula\s+)?SIAPE|Matrícula)\s*"
    r"(?:n[ºo°]\s*)?[:\-]?\s*"
    r"([\d*Xx]+(?:[.\-][\d*Xx]+)*)\b",
    re.IGNORECASE,
)


_RE_PROCESSO = re.compile(
    r"\bprocesso\b\s*(?:administrativo\s*)?(?:SEI\s*)?"
    r"(?:n[º°o.]?\s*)?[:\-]?\s*"
    r"(\d[\d./-]{4,})",
    re.IGNORECASE
)


def extrair_cpf(bloco):
    m = _RE_CPF.search(bloco)

    if not m:
        return None

    return limpar(m.group(1))

def extrair_siape(bloco):
    m = _RE_SIAPE.search(bloco)
    return limpar(m.group(1)) if m else None


def extrair_processo(bloco):
    m = _RE_PROCESSO.search(bloco)

    if not m:
        return None

    return limpar(m.group(1).rstrip("."))



_DATA = (r"\d{1,2}\s*[º°o]?\s+(?:de\s+)?[A-Za-zçÇ]+\s+de\s+\d{4}"
         r"|\d{1,2}[º°]?/\d{1,2}/\d{4}")
_RE_EFEITO = re.compile(
    r"(?:a\s+partir\s+d[eoa]|a\s+contar\s+d[eoa]|com\s+efeitos?\s+(?:a\s+partir\s+)?d[eoa])"
    r"\s+(" + _DATA + r")",
    re.I,
)


def extrair_data_efeito(bloco):
    m = _RE_EFEITO.search(bloco)
    return normalizar_data(m.group(1)) if m else None


_RE_DESTINO = re.compile(
    r"\bpara\s+(?:a|o)\s+(.{5,200}?)\s+d[oa]\s+Conselho\b", re.I | re.S)


def extrair_destino(bloco):
    m = _RE_DESTINO.search(bloco)
    return limpar(m.group(1)) if m else None



_RE_ITEM_SUBST = re.compile(
    r"(?:^|\s)([IVX]+)\s*[-–—]\s*(" + _MAIUSC_NOME + r")\s*,\s*"
    r"(?i:matr[ií]cula\s+siape)\s*(?:n[ºo°.]*\s*)?([\d.]+)"
)


def extrair_ordem_substituicao(ato):
    return [
        (i + 1, limpar(m.group(2)), m.group(3).rstrip("."))
        for i, m in enumerate(_RE_ITEM_SUBST.finditer(ato))
    ]


_REGRAS = (
    ("codigos_cargo", {"codigo"}, set(), set()),
    ("codigos_cargo", set(), {"cce", "fce"}, set()),
    ("texto_original_ato", {"texto"}, set(), set()),
    ("data_publicacao", set(), {"publicacao", "publicado"}, set()),
    ("data_efeito", set(), {"efeito", "vigencia"}, set()),
    ("data_efeito", {"data"}, {"inicio", "fim"}, set()),
    ("data_portaria", {"data"}, {"portaria", "ato"}, set()),
    ("numero_portaria", {"portaria"}, {"numero", "n", "no", "num"}, set()),
    ("tipo_ato", {"tipo"}, {"ato", "portaria"}, set()),
    ("tipo_ato", set(), {"motivo", "ato", "acao"}, {"data", "texto", "numero"}),
    ("nome", {"nome"}, set(),
     {"cargo", "funcao", "orgao", "ministerio", "arquivo", "documento"}),
    ("cpf", {"cpf"}, set(), set()),
    ("cargo_funcao", {"cargo"}, {"funcao"}, set()),
    ("denominacao_unidade_superior", {"denominacao"}, {"unidade"}, set()),
    ("sigla", {"sigla"}, set(), set()),
    ("unidade_vinculada", {"unidade"}, {"vinculada"}, set()),
    ("cargo", set(), {"cargo", "funcao"}, set()),
    ("orgao", {"orgao"}, set(), set()),
    ("ministerio", {"ministerio"}, set(), set()),
    ("arquivo", set(), {"arquivo", "documento"}, set()),
    ("numero_portaria", {"portaria"}, set(), set()),
    ("siape", {"siape"}, set(), set()),
    ("processo", {"processo"}, set(), set()),
)


def _palavras(cabecalho):
    saida = set()
    for p in re.findall(r"[a-z0-9]+", _sem_acento(cabecalho)):
        if p.endswith("oes"):
            p = p[:-3] + "ao"
        elif len(p) > 3 and p.endswith("s"):
            p = p[:-1]
        saida.add(p)
    return saida


def sugerir_campo_para_cabecalho(cabecalho, campos_disponiveis):
    palavras = _palavras(cabecalho)
    for campo, todas, qualquer, excluir in _REGRAS:
        if (campo in campos_disponiveis
                and todas <= palavras
                and (not qualquer or qualquer & palavras)
                and not excluir & palavras):
            return campo
    return None


_RE_PUBLICACAO = re.compile(r"Publicado em:\s*(\d{2}/\d{2}/\d{4})", re.I)
_RE_ORGAO = re.compile(r"Órgão:\s*([^\n]+)", re.I)
_FIM_TITULO = r"[ \t]*(?:[-–—(*][^\n]{0,60})?$"
_DATA_TITULO = r"\d{1,2}\s*[º°]?\s+DE\s+(?:" + _MESES_RE + r")\s+DE\s+\d{4}"
_RE_DATA_CAB = re.compile(
    r"(?im)^\s*PORTARIAS?\b[^\n]*?\bDE\s+(" + _DATA_TITULO + r")" + _FIM_TITULO)
_RE_NUM_TITULO = re.compile(
    r"(?im)^\s*(?:PORTARIAS?\b(?P<sigla>[^\n]*?))?"
    r"\bN\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)\s*,?\s*DE\s+" + _DATA_TITULO + _FIM_TITULO)
_RE_NUM_ITEM = re.compile(
    r"(?m)^\s*(?P<sigla>)N\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)\s*[-–—]\s")
_RE_NUMERO = re.compile(
    r"(?im)^\s*(?:PORTARIAS?\b(?P<sigla>[^\n]*?))?"
    r"\bN\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)"
    r"\s*(?=(?:[-–—]\s*|,?\s+DE\b))"
)


_RE_NUM_BARRA = re.compile(
    r"(?im)^\s*(?:PORTARIAS?|DESPACHO|RESOLU[ÇC][ÃA]O)\b(?P<sigla>[^\n]*?)"
    r"\bN\s*[º°.]?\s*(?P<num>\d+(?:\.\d+)*)\s*/\s*\d{2,4}")


def _achar_ocorrencias(texto):
    achados = sorted(list(_RE_NUM_TITULO.finditer(texto)) + list(_RE_NUM_ITEM.finditer(texto)),
                     key=lambda m: m.start())
    return achados or list(_RE_NUM_BARRA.finditer(texto)) or list(_RE_NUMERO.finditer(texto))


_UNID = (r"(?:GABINETE|SECRETARIA|SUBSECRETARIA|DEPARTAMENTO|DIRETORIA|COORDENAÇÃO|CONSELHO|"
         r"COMANDO|INSTITUTO|AGÊNCIA|FUNDAÇÃO|UNIVERSIDADE|PROCURADORIA|CORREGEDORIA|ESCRITÓRIO)")
_P_MIN = (r"(?:((?:MINISTÉRIO|PRESIDÊNCIA DA REPÚBLICA|VICE-PRESIDÊNCIA DA REPÚBLICA|CASA CIVIL|"
          r"CONTROLADORIA-GERAL DA UNIÃO|ADVOCACIA-GERAL DA UNIÃO|BANCO CENTRAL DO BRASIL)[ \t]*[A-ZÀ-Ý \-/]{0,70}?)[ \t]*$"
          r"|((?:Ministério)[ \t][^\n,.]{3,70}|Presidência da República)[ \t]*$"
          r"(?=\n[ \t]*(?:PORTARIA|" + _UNID + r")))")
_P_UNI = r"(" + _UNID + r"\b[A-ZÀ-Ý \-/]{0,60})[ \t]*$"
_RE_MINISTERIO = re.compile(r"(?m)^[ \t]*" + _P_MIN)
_RE_UNIDADE = re.compile(r"(?m)^[ \t]*" + _P_UNI)
_RE_CORTE = re.compile(r"(?m)^[ \t]*(?:" + _P_MIN + "|" + _P_UNI + ")")
_RE_DATA_DOU = re.compile(
    r"(?:(?:segunda|terça|quarta|quinta|sexta)-feira|sábado|domingo),\s*"
    r"(\d{1,2}\s+de\s+[A-Za-zçÇ]+\s+de\s+\d{4})", re.I)
_MINUSC = {"de", "do", "da", "dos", "das", "e"}
_RE_TITULO = re.compile(
    r"(?im)^\s*PORTARIAS?\b[^\n]*?\bN\s*[º°.]?\s*([\d]+(?:\.[\d]+)*)"
    r"\s*,?\s*DE\s+([^\n]+)"
)
_CAMPOS_UTEIS = ("tipo_ato", "nome", "cpf", "siape", "cargo", "codigos_cargo", "data_efeito")


def _por_posicao(itens, pos, primeiro_se_nenhum=False):
    if not itens:
        return None
    i = bisect_right([p for p, _ in itens], pos) - 1
    if i < 0:
        return itens[0][1] if primeiro_se_nenhum else None
    return itens[i][1]


def _data_na_abertura(bloco):
    m = re.search(r"\bDE\s+(" + _DATA_TITULO + r")", bloco[:200], re.I)
    return normalizar_data(m.group(1)) if m else None


def _ultimo(itens, pos):
    i = bisect_right([p for p, _ in itens], pos) - 1
    return itens[i] if i >= 0 else (-1, None)


def _titulo(txt):
    if not txt or not txt.isupper():
        return txt
    pal = txt.lower().split()
    return " ".join(
        p if (k and p in _MINUSC) else "-".join(x.capitalize() for x in p.split("-"))
        for k, p in enumerate(pal)
    )


_RE_EMISSOR = re.compile(
    r"\bD[AO]\s+([A-ZÀ-Ý][A-ZÀ-Ý \-]{3,80}?)\s*,\s*nos?\s+uso\b")


def _emissor(bloco):
    m = _RE_EMISSOR.search(bloco[:600])
    return _titulo(limpar(m.group(1))) if m else None


def pertence_ao_ministerio_esporte(base, bloco):
    sigla = _sem_acento(base.get("sigla_portaria") or "").upper()
    ministerio = _sem_acento(base.get("ministerio") or "").upper()
    orgao = _sem_acento(base.get("orgao") or "").upper()
    texto = _sem_acento(bloco).upper()

    if sigla == "MESP":
        return True

    if "MINISTERIO DO ESPORTE" in ministerio:
        return True

    if "MINISTERIO DO ESPORTE" in orgao:
        return True

    if "MINISTRO DE ESTADO DO ESPORTE" in texto:
        return True

    if "SECRETARIO-EXECUTIVO DO MINISTERIO DO ESPORTE" in texto:
        return True

    if (
        "CASA CIVIL" in texto
        and "MINISTERIO DO ESPORTE" in texto
    ):
        return True

    return False



def _ministerio_do_orgao(orgao):
    return limpar(orgao.split("/")[0]) if orgao else None


def _registros_do_bloco(base, bloco, corpo):
    data_bloco = extrair_data_efeito(corpo)
    processo = extrair_processo(bloco)
    saida = []
    for ato in dividir_atos(corpo):
        tipo, acao = identificar_acao(ato)
        ref, trecho = None, ato
        if tipo == "Tornar sem efeito" and acao:
            r = RE_PORTARIA_REF.search(ato, acao.end())
            ref = limpar(" ".join(filter(None, r.groups()))) if r else None
            passado = RE_PASSADO.search(ato, acao.end())
            if passado:
                acao, trecho = passado, ato[passado.end():]
        if not ref:
            rev = re.search(r"\brevogad[ao]\s+(?:a\s+)?", ato, re.I)
            if rev:
                r = RE_PORTARIA_REF.search(ato, rev.end())
                ref = limpar(" ".join(filter(None, r.groups()))) if r else None
        cargo = extrair_cargo(trecho)
        cpf = extrair_cpf(ato)
        siape = extrair_siape(ato)
        encargo = None
        if cargo and re.match(r"substitut[oa]\s+eventual\b", cargo, re.I):
            encargo = "Substituto eventual"
            cargo = extrair_cargo(cargo) or cargo
        efeito = extrair_data_efeito(ato) or data_bloco
        if not efeito and RE_VIGOR.search(corpo):
            efeito = base["data_publicacao"]
        registro = {
            **base,
            "tipo_ato": tipo,
            "nome": extrair_nome_depois_acao(ato, acao),
            "cpf": cpf,
            "siape": siape,
            "cargo": cargo,
            "encargo": encargo,
            "codigos_cargo": extrair_codigo(trecho),
            "data_efeito": efeito,
            "portaria_referida": ref,
            "texto_original_ato": limpar(ato),
        }
        m_cs = _RE_CARGO_APOS_NOME.search(ato)
        if m_cs:
            registro["cargo_servidor"] = limpar(m_cs.group(1))

        extras = []
        if encargo:
            for n, nome_sub, siape_sub in extrair_ordem_substituicao(ato):
                if _sem_acento(nome_sub) == _sem_acento(registro["nome"] or ""):
                    registro["ordem_substituicao"] = n
                else:
                    extras.append({
                        **registro,
                        "nome": nome_sub,
                        "siape": siape_sub,
                        "cpf": None,
                        "cargo_servidor": None,
                        "ordem_substituicao": n,
                    })

        if tipo == "Transferência":
            registro["destino"] = extrair_destino(ato)
        saida.append(registro)
        saida.extend(extras)
    return [
        r for r in saida
        if r.get("tipo_ato") or r.get("texto_original_ato")
]


_RE_DESPACHO = re.compile(r"(?m)^\s*DESPACHO\s*$")
_RE_AFASTAMENTO = re.compile(
    r"autoriza\s*o\s*afastamento\s*do\s*Pa[ií]s\s*d[eo]\s*"
    r"(?P<nome>(?-i:" + _NOME + r"))\s*,\s*(?P<cargo>[^,]{3,150}?)\s*,\s*para\s*"
    r"(?P<motivo>.{1,500}?)\s*,\s*no\s*per[ií]odo\s*de\s*(?P<periodo>[^,]{3,80}?)\s*,\s*com\s*[ôo]nus",
    re.I | re.S,
)


def extrair_despachos(texto, base):
    saida = []
    for a in _RE_AFASTAMENTO.finditer(texto):
        saida.append({
            **base,
            "cpf": None,
            "siape": None,
            "encargo": None,
            "codigos_cargo": "",
            "portaria_referida": None,
            "tipo_ato": "Afastamento do País",
            "nome": limpar(a["nome"]),
            "cargo": limpar(a["cargo"]),
            "data_efeito": limpar(a["periodo"]),
            "destino": limpar(a["motivo"]),
            "processo": extrair_processo(texto[a.end():a.end() + 120]),
            "texto_original_ato": limpar(a[0]),
        })
    return saida


def _limpar_registros(registros):
    vistos, saida = set(), []
    for r in registros:
        if not r.get("nome") and not r.get("tipo_ato"):
            continue  # resíduo de sumário/cabeçalho
        chave = (
            r.get("numero_portaria"),
            _sem_acento(r.get("nome") or "") or r.get("texto_original_ato"),
            r.get("siape"),
            r.get("tipo_ato"),
            r.get("ordem_substituicao"),
            r.get("data_efeito"),
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(r)
    return saida


def extrair_informacoes(texto):
    cab = _RE_DATA_DOU.search(texto)
    texto = normalizar_texto(texto)

    pub = _RE_PUBLICACAO.search(texto)
    org = _RE_ORGAO.search(texto)
    publicacao = pub.group(1) if pub else (normalizar_data(cab.group(1)) if cab else None)
    orgao_global = limpar(org.group(1)) if org else None

    datas = [(m.start(), normalizar_data(m.group(1))) for m in _RE_DATA_CAB.finditer(texto)]
    ministerios = [(m.start(), _titulo(limpar(m.group(1) or m.group(2))))
                   for m in _RE_MINISTERIO.finditer(texto)]
    unidades = [(m.start(), _titulo(limpar(m.group(1)))) for m in _RE_UNIDADE.finditer(texto)]
    ocorrencias = _achar_ocorrencias(texto)

    registros = []
    for i, oc in enumerate(ocorrencias):
        inicio = oc.start()
        fim = ocorrencias[i + 1].start() if i + 1 < len(ocorrencias) else len(texto)
        bloco = texto[inicio:fim]
        corte = _RE_CORTE.search(bloco)
        if corte:
            bloco = bloco[:corte.start()]
        desp = _RE_DESPACHO.search(bloco)    
        if desp:
            bloco = bloco[:desp.start()]
        corpo = bloco[oc.end() - inicio:]

        pos_min, ministerio = _ultimo(ministerios, inicio)
        pos_uni, unidade = _ultimo(unidades, inicio)
        if unidade and pos_uni < pos_min:
            unidade = None
        emissor = _emissor(bloco)
        if oc.re is _RE_NUM_ITEM: 
            ministerio = ministerio or emissor
        else:                         
            ministerio = emissor or ministerio
        ministerio = ministerio or _ministerio_do_orgao(orgao_global)
        orgao = orgao_global or (f"{ministerio}/{unidade}" if ministerio and unidade else ministerio)

        base = {
            "numero_portaria": oc.group("num"),
            "sigla_portaria": limpar(oc.group("sigla")),
            "data_portaria": (_por_posicao(datas, inicio, primeiro_se_nenhum=True)
                              or _data_na_abertura(bloco)),
            "data_publicacao": publicacao,
            "orgao": orgao,
            "ministerio": ministerio,
            "processo": extrair_processo(bloco),
        }

        if not pertence_ao_ministerio_esporte(base, bloco):
            continue

        registros += _registros_do_bloco(base, bloco, corpo)

    registros += extrair_despachos(texto, {
        "numero_portaria": None,
        "sigla_portaria": None,
        "data_portaria": None,
        "data_publicacao": publicacao,
        "orgao": orgao_global,
        "ministerio": _ministerio_do_orgao(orgao_global),
    })

    if not registros:
        t = _RE_TITULO.search(texto)
        if t:
            base = {
                "numero_portaria": t.group(1),
                "sigla_portaria": None,
                "data_portaria": normalizar_data(t.group(2)),
                "data_publicacao": publicacao,
                "orgao": orgao_global,
                "ministerio": _ministerio_do_orgao(orgao_global),
            }
            registros = _registros_do_bloco(base, texto, texto[t.end():])

    if not registros and RE_ACAO.search(texto):
        base = {
            "numero_portaria": None,
            "sigla_portaria": None,
            "data_portaria": None,
            "data_publicacao": publicacao,
            "orgao": orgao_global,
            "ministerio": _ministerio_do_orgao(orgao_global),
        }
        registros = _registros_do_bloco(base, texto, texto)    
    return _limpar_registros(registros)


def ler_pdf(caminho):
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError("instale com: pip install pdfplumber") from e
    partes = []
    with pdfplumber.open(caminho) as pdf:
        for pag in pdf.pages:
            x0, topo, x1, base = pag.bbox
            meio = (x0 + x1) / 2
            palavras = pag.extract_words()
            cruzam = sum(1 for w in palavras if w["x0"] < meio - 2 and w["x1"] > meio + 2)
            if palavras and cruzam / len(palavras) < 0.02:
                for caixa in ((x0, topo, meio, base), (meio, topo, x1, base)):
                    partes.append(pag.crop(caixa).extract_text() or "")
            else:
                partes.append(pag.extract_text() or "")
    return "\n".join(partes)


def diagnosticar_sem_cargo(registros, janela=220):
    for r in registros:
        if r.get("cargo"):
            continue
        txt = r.get("texto_original_ato") or ""
        m = re.search(r"cargo|função|código|CCE|FCE|DAS|FG", txt, re.I)
        ini = max((m.start() if m else 0) - 60, 0)
        print(f"[{r.get('numero_portaria')}] {r.get('nome')}\n   ...{txt[ini:ini + janela]}...\n")