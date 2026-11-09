
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
    "Tornar sem efeito": "TORNAR SEM EFEITO",
}

_RAIZES = (
    ("nomea", "Nomeação"), ("exoner", "Exoneração"), ("dispens", "Dispensa"),
    ("design", "Designação"), ("aposent", "Aposentadoria"), ("ced", "Cessão"),
    ("revog", "Revogação"), ("recondu", "Recondução"),
    ("redistribu", "Redistribuição"), ("tornar", "Tornar sem efeito"),
    ("tornad", "Tornar sem efeito"),
)
_INF = (r"tornar\s+sem\s+efeito|nomear|exonerar|dispensar|designar|aposentar|ceder|revogar|"
        r"reconduzir|redistribuir")
_PART = (r"tornad[oa]s?\s+sem\s+efeito|nomead[oa]s?|exonerad[oa]s?|dispensad[oa]s?|designad[oa]s?|"
         r"aposentad[oa]s?|cedid[oa]s?|revogad[oa]s?|reconduzid[oa]s?|"
         r"redistribuíd[oa]s?")
RE_INFINITIVO = re.compile(rf"\b(?:{_INF})\b", re.I)
RE_ACAO = re.compile(rf"\b({_INF}|{_PART})\b", re.I)
RE_PASSADO = re.compile(
    r"\bque\s+(?:nomeou|exonerou|dispensou|designou|aposentou|cedeu|revogou|"
    r"reconduziu|redistribuiu)\b", re.I)
RE_PORTARIA_REF = re.compile(r"\bPortaria\s+n\s*[º°o.]?\s*(\d+(?:\.\d+)*)", re.I)
RE_VIGOR = re.compile(r"entra\s+em\s+vigor\s+na\s+data\s+de\s+sua\s+publicação", re.I)
RE_RESOLVE = re.compile(r"\bresolve(?:m)?\s*:?", re.I)

MESES = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")
_NUM_MES = {m: i for i, m in enumerate(MESES, 1)}
_MESES_RE = "|".join(MESES).replace("marco", "mar[cç]o").upper()


def _sem_acento(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii").lower()


def normalizar_texto(texto):
    texto = texto.replace("\xa0", " ").replace("\u00ad", "")
    texto = re.sub(r"(\w)-\n(?=[a-zà-ú])", r"\1", texto)  # hifenização de PDF
    # "... FCE 1.15. Nº 1.105 - DESIGNAR ..." na mesma linha -> quebra antes do "Nº"
    texto = re.sub(r"(?<=[.;])[ \t]+(?=N[º°]\s*\d[\d.]*\s*[-–—]\s)", "\n", texto)
    linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in texto.splitlines()]
    return "\n".join(l for l in linhas if l)


def limpar(texto):
    if not texto:
        return None
    return re.sub(r"\s+", " ", texto).strip(" ,;:-") or None


def normalizar_data(txt):
    """'1º de novembro de 2026' / '05/11/2026' -> '01/11/2026'."""
    if not txt:
        return None
    t = _sem_acento(txt)
    m = re.search(r"(\d{1,2})\s*o?\s+de\s+([a-z]+)\s+de\s+(\d{4})", t)
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
    """Posição logo após 'resolve:' (evita verbos do preâmbulo)."""
    m = RE_RESOLVE.search(texto)
    return m.end() if m else 0


def identificar_acao(texto):
    m = RE_ACAO.search(texto, _inicio_dispositivo(texto)) or RE_ACAO.search(texto)
    if not m:
        return None, None
    return _tipo_do_verbo(m.group(1)), m


def dividir_atos(corpo):
    """'Exonerar X ... e nomear Y ...' -> dois trechos, um por verbo."""
    marcas = [m.start() for m in RE_INFINITIVO.finditer(corpo, _inicio_dispositivo(corpo))]
    if len(marcas) <= 1:
        return [corpo]
    marcas.append(len(corpo))
    return [corpo[a:b] for a, b in zip(marcas, marcas[1:])]




_PAL = r"[A-ZÀ-Ý][A-ZÀ-Ýa-zà-ÿ'’\-]*"
_NOME = _PAL + r"(?:\s+(?:d[aeo]s?\s+|e\s+)?" + _PAL + r"){1,8}"
_RE_NOME = re.compile(
    r"^[\s,:;\-]*"
    r"(?:(?:a\s+pedido|de\s+ofício)\s*,?\s*)?"
    r"(?:(?:o|a)\s+)?"
    r"(?:(?:Senhor|Senhora|Sr|Sra)\.?\s+)?"
    r"(" + _NOME + r")"
    r"(?=\s*[,(;]|\s+(?:para|do|da|no|na|CPF|matrícula|SIAPE|ocupante)\b)"
)
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


def extrair_nome_depois_acao(texto, resultado_acao):
    if not resultado_acao:
        return None
    janela = texto[resultado_acao.end(): resultado_acao.end() + 250]
    m = _RE_NOME.search(janela)
    return _nome_valido(limpar(m.group(1))) if m else None




_PARADA_CARGO = (
    r"(?=\s*[,;:]"
    r"|\s+(?:código|(?-i:CCE|FCE|FCPE|DAS|FG|CD|NE))\b"
    r"|\.(?:\s|$)|\s+a\s+partir\b|\s+ficando\b|\s+e\s*$|$)"
)

_RE_CARGO = re.compile(
    r"\b(?:cargo|função|emprego)"
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
_RE_CODIGO = re.compile(
    r"\b(CCE|FCE|FCPE|DAS|FG|CD|CGE|FUC|FST|NE)[\s\-]*(\d+(?:[.,]\d+)*)\b"
)


def extrair_cargo(bloco):
    m = _RE_CARGO.search(bloco) or _RE_CARGO_APOS_CPF.search(bloco)
    return limpar(m.group(1)) if m else None


def extrair_codigo(bloco):
    codigos = (f"{s}{n}" for s, n in _RE_CODIGO.findall(bloco))
    return ", ".join(dict.fromkeys(codigos))




_DATA = (r"\d{1,2}\s*[º°o]?\s+de\s+[A-Za-zçÇ]+\s+de\s+\d{4}"
         r"|\d{1,2}[º°]?/\d{1,2}/\d{4}")
_RE_EFEITO = re.compile(
    r"(?:a\s+partir\s+d[eoa]|a\s+contar\s+d[eoa]|com\s+efeitos?\s+(?:a\s+partir\s+)?d[eoa])"
    r"\s+(" + _DATA + r")",
    re.I,
)


def extrair_data_efeito(bloco):
    m = _RE_EFEITO.search(bloco)
    return normalizar_data(m.group(1)) if m else None




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
    ("cargo", set(), {"cargo", "funcao"}, set()),
    ("orgao", {"orgao"}, set(), set()),
    ("ministerio", {"ministerio"}, set(), set()),
    ("arquivo", set(), {"arquivo", "documento"}, set()),
    ("numero_portaria", {"portaria"}, set(), set()),
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
_RE_DATA_CAB = re.compile(
    r"(?m)^\s*PORTARIAS?\b[^\n]*?\bDE\s+(\d{1,2}\s*[º°]?\s+DE\s+(?:"
    + _MESES_RE + r")\s+DE\s+\d{4})"
)
_RE_NUMERO = re.compile(
    r"(?m)^\s*(?:PORTARIAS?\b[^\n]*?)?"
    r"\bN\s*[º°.]?\s*([\d]+(?:\.[\d]+)*)"
    r"\s*(?=(?:[-–—]\s*|,?\s+DE\b))"
)
_RE_MINISTERIO = re.compile(r"(?m)^\s*(MINISTÉRIO[^\n]{0,100})$")
_RE_CORTE = re.compile(r"(?m)^\s*(?:MINISTÉRIO|PRESIDÊNCIA DA REPÚBLICA)\b")
_RE_TITULO = re.compile(
    r"(?m)^\s*PORTARIAS?\b[^\n]*?\bN\s*[º°.]?\s*([\d]+(?:\.[\d]+)*)"
    r"\s*,?\s*DE\s+([^\n]+)"
)
_CAMPOS_UTEIS = ("tipo_ato", "nome", "cargo", "codigos_cargo", "data_efeito")


def _por_posicao(itens, pos, primeiro_se_nenhum=False):
    """Último item (posição, valor) que começa antes de `pos`."""
    if not itens:
        return None
    i = bisect_right([p for p, _ in itens], pos) - 1
    if i < 0:
        return itens[0][1] if primeiro_se_nenhum else None
    return itens[i][1]


def _ministerio_do_orgao(orgao):
    return limpar(orgao.split("/")[0]) if orgao else None


def _registros_do_bloco(base, bloco, corpo):
    data_bloco = extrair_data_efeito(corpo)
    saida = []
    for ato in dividir_atos(corpo):
        tipo, acao = identificar_acao(ato)
        ref, trecho = None, ato
        if tipo == "Tornar sem efeito" and acao:
            r = RE_PORTARIA_REF.search(ato, acao.end())
            ref = r.group(1) if r else None
            passado = RE_PASSADO.search(ato, acao.end())   
            if passado:                                    
                acao, trecho = passado, ato[passado.end():]
        efeito = extrair_data_efeito(ato) or data_bloco
        if not efeito and RE_VIGOR.search(corpo):
            efeito = base["data_publicacao"]
        saida.append({
            **base,
            "tipo_ato": tipo,
            "nome": extrair_nome_depois_acao(ato, acao),
            "cargo": extrair_cargo(trecho),
            "codigos_cargo": extrair_codigo(trecho),
            "data_efeito": efeito,
            "portaria_referida": ref,
            "texto_original_ato": limpar(bloco),
        })
    return [r for r in saida if any(r[c] for c in _CAMPOS_UTEIS)]


def extrair_informacoes(texto):
    texto = normalizar_texto(texto)

    pub = _RE_PUBLICACAO.search(texto)
    org = _RE_ORGAO.search(texto)
    comum = {
        "data_publicacao": pub.group(1) if pub else None,
        "orgao": limpar(org.group(1)) if org else None,
    }
    datas = [(m.start(), normalizar_data(m.group(1))) for m in _RE_DATA_CAB.finditer(texto)]
    ministerios = [(m.start(), limpar(m.group(1))) for m in _RE_MINISTERIO.finditer(texto)]
    ocorrencias = list(_RE_NUMERO.finditer(texto))

    registros = []
    for i, oc in enumerate(ocorrencias):
        inicio = oc.start()
        fim = ocorrencias[i + 1].start() if i + 1 < len(ocorrencias) else len(texto)
        bloco = texto[inicio:fim]
        corte = _RE_CORTE.search(bloco)         
        if corte:
            bloco = bloco[:corte.start()]
        corpo = bloco[oc.end() - inicio:]
        base = {
            "numero_portaria": oc.group(1),
            "data_portaria": _por_posicao(datas, inicio, primeiro_se_nenhum=True),
            "data_publicacao": comum["data_publicacao"],
            "orgao": comum["orgao"],
            "ministerio": _por_posicao(ministerios, inicio) or _ministerio_do_orgao(comum["orgao"]),
        }
        registros += _registros_do_bloco(base, bloco, corpo)

    if not registros:                         
        t = _RE_TITULO.search(texto)
        if t:
            base = {
                "numero_portaria": t.group(1),
                "data_portaria": normalizar_data(t.group(2)),
                **comum,
                "ministerio": _ministerio_do_orgao(comum["orgao"]),
            }
            registros = _registros_do_bloco(base, texto, texto[t.end():])
    return registros


def diagnosticar_sem_cargo(registros, janela=220):
    for r in registros:
        if r.get("cargo"):
            continue
        txt = r.get("texto_original_ato") or ""
        m = re.search(r"cargo|função|código|CCE|FCE|DAS|FG", txt, re.I)
        ini = max((m.start() if m else 0) - 60, 0)
        print(f"[{r.get('numero_portaria')}] {r.get('nome')}\n   ...{txt[ini:ini + janela]}...\n")