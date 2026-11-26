import re

W = r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ'’]+"
CONECT = r"(?:DE|DA|DO|DOS|DAS|E)"
RE_NOME = re.compile(rf"\b{W}(?:\s+(?:{W}|{CONECT}))+\b")
NAO_NOME = {
    "CPF", "SIAPE", "FCE", "CCE", "DAS", "MINISTRO", "MINISTÉRIO", "SECRETARIA",
    "SECRETÁRIA", "PROCURADOR", "PROCURADORIA", "PORTARIA", "DIÁRIO", "OFICIAL",
    "UNIÃO", "POLÍCIA", "FEDERAL", "BRASIL", "LEI", "SEI", "FAZENDA", "NACIONAL",
}

RE_VERBO = re.compile(
    r"(?i)\b(dispens\w+|design\w+|nomea\w*|nomear|exoner\w+|revert\w+|"
    r"autoriz\w+|afast\w+|reconduz\w+)\b"
)

TIPO = {"dispens": "dispensa", "design": "designação", "nome": "nomeação",
        "exoner": "exoneração", "revert": "reversão", "autoriz": "autorização",
        "afast": "afastamento", "reconduz": "recondução"}

_INICIO = (
    r"(?:PORTARIAS?\b|DESPACHO\b|RETIFICA[ÇC][ÃA]O\b|"
    r"Nº\s*\d{1,5}\s*(?:[-–]|(?=Designar|Dispensar|Nomear|Exonerar|Autorizar|"
    r"Declarar|Reverter|Art|Fica|Ficam|Conceder|Tornar|D\s*ES\b|N\s*O\s*M)))"
)

RE_MARCA = re.compile(r"(?m)^\s*(?=" + _INICIO + ")")

RE_INICIO = re.compile(r"\s*" + _INICIO)

P_SIAPE = re.compile(r"(?i)siape(?:cad)?\s*n?[º°o]?\s*(\d{6,9})")

P_CPF = re.compile(r"CPF\s*([\d\.\*\-]{10,16})")

P_COD = re.compile(r"(?<![A-ZÁ-Ú])((?:FCE|CCE|FG|DAS|FCPE)[\s\-]?\d+(?:\.\d+)?)")

P_CARGO = re.compile(
    r"(?:Fun[çc][ãa]o|Cargo)\s+Comissionad[ao]\s+Executiv[ao]\s+de\s+"
    r"(.+?),?\s*(?:c[óo]digo\s*)?(?:FCE|CCE)\s*\d"
)
P_CARGO2 = re.compile(r"(?i)fun[çc][ãa]o\s+de\s+(.+?),\s*c[óo]digo\s*(?:FCE|CCE)")

VERBOS_CAPS = {"DESIGNAR", "NOMEAR", "DISPENSAR", "EXONERAR", "AUTORIZAR", "REVERTER", "RECONDUZIR"}
RE_LETRAS = re.compile(r"\b(?:[A-ZÁ-Ú]{1,2}\s){3,}[A-ZÁ-Ú]{1,2}\b")

RE_PONTILHADO = re.compile(r"(?m)^.*\.{4,}.*$")

P_CARGO_GEN = re.compile(
    r"(?i)(?<!en)(?:cargo|fun[çc][ãa]o)\s*de\s*(.+?)\s*,?\s*c[óo]digo\s*(?:FCE|CCE)"

)
P_CARGO_SIMPLES = re.compile(r"(?i)(?<!en)(?:cargo|fun[çc][ãa]o)\s*de\s*([^,.;]+?)\s*(?:,|\.|;|$)")

P_CARGO3 = re.compile(
    r"(?i)encargo\s+de\s+substitut\w+\s+(?:eventu\w+\s+)?"
    r"(?!(?:d[aoe]s?\s+)?(?:Cargo|Fun[çc][ãa]o)\s+Comissionad)"
    r"(?:d[aoe]s?\s+)?(.+?),\s*c[óo]digo\s*(?:FCE|CCE)"
)

P_EFET_A = re.compile(r"^\s*,\s*([^,]+?)\s*,\s*(?:matr[íi]cula|siape)", re.I)

P_EFET_B = re.compile(
    r"(?i)siape(?:cad)?\s*n?[º°o]?\s*\d{6,9}\s*,\s*(?:no\s+cargo\s+de\s+)?(ambos\s+|ambas\s+)?([^,]+?)\s*,"
)

RUIM_EFET = re.compile(r"(?i)^(?:da|do|das|dos|para|ficando|a partir|lotad|no|na|exercer|e)\b|\d|fun[çc][ãa]o|c[óo]digo")

P_PROC = re.compile(r"(?i)processo\s+(?:SEI\s+)?(?:n[º°o]\s*)?(\d[\d\.\/\-]+\d)")

P_REF = re.compile(
    r"(?i)(?:revog\w+|retific\w+|altera\w*)\s+a\s+portaria\s+([^,]*?n[º°o]\s*[\d\.]+"
    r"(?:,\s*de\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4})?)"
)
P_REF2 = re.compile(
    r"(?i)\b(?:na|à)\s+portaria\s+([^,]*?n[º°o]\s*[\d\.]+(?:,\s*de\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4})?)"
)
P_FG = re.compile(r"(?i)(fun[çc][ãa]o\s+gratificada)")

P_EFET_C = re.compile(r"^\s*,\s*([^,]+?)\s*,\s*(?:para|no\s+per[íi]odo|em)\b", re.I)

P_EFET_ANTES = re.compile(
    r"\b((?:Auditor|Analista|Procurador|T[ée]cnico|Agente|Assistente|M[ée]dic|Engenheir|Professor|Servidor)"
    r"[^,.;]{0,80}?)\s*$"
)

P_EFEITO = re.compile(r"(?i)a partir de\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})")


def _tipo(verbo: str):
    v = verbo.lower()
    return next((t for k, t in TIPO.items() if v.startswith(k)), None)


def _tirar_assinatura(seg: str) -> str:
    linhas, saida, anterior = seg.split("\n"), [], ""
    for ln in linhas:
        s = ln.strip()
        if (s and anterior.endswith((".", ")")) and s == s.upper()
                and re.search(r"[A-ZÁ-Ú]", s) and len(saida) > 1):
            break
        saida.append(ln)
        if s:
            anterior = s
    return "\n".join(saida)


def _limpar(t: str) -> str:
    t = re.sub(r"-\n(?=\S)", "-", t)
    return re.sub(r"\s+", " ", t).strip()


def _nomes(corpo: str):
    achados = []
    for m in RE_NOME.finditer(corpo):
        ini, txt = m.start(), m.group()
        while True:
            primeiro = txt.split(None, 1)
            if len(primeiro) == 2 and primeiro[0] in VERBOS_CAPS:
                ini += len(txt) - len(primeiro[1])
                txt = primeiro[1]
            else:
                break
        toks = re.split(r"[\s\-]", txt)
        reais = [x for x in toks if x not in {"DE", "DA", "DO", "DOS", "DAS", "E"}]
        if len(reais) < 2 or any(x in NAO_NOME for x in reais):
            continue
        achados.append((ini, m.end(), txt))
    for m in re.finditer(r"\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{12,})\s*,", corpo):
        if m.group(1) in NAO_NOME or any(a <= m.start(1) < b for a, b, _ in achados):
            continue
        achados.append((m.start(1), m.end(1), m.group(1)))
    return sorted(achados)


def _coletar(corpo: str):
    cargos, spans = [], []
    for rx in (P_CARGO, P_CARGO_GEN, P_CARGO2, P_CARGO3, P_FG):
        for m in rx.finditer(corpo):
            val = m.group(1).strip()
            if rx is P_CARGO3 and re.match(
                r"(?i)(?:eventu\w+\s+)?(?:d[aoe]s?\s+)?(?:Cargo|Fun[çc][ãa]o)\b", val
            ):
                continue
            cargos.append((m.start(), val))
            spans.append((m.start(), m.end()))
    for m in P_CARGO_SIMPLES.finditer(corpo):
        if not any(a <= m.start() < b for a, b in spans):
            cargos.append((m.start(), m.group(1).strip()))
    codigos = [(m.start(), m.group(1)) for m in P_COD.finditer(corpo)]
    return sorted(cargos), sorted(codigos)


def _escolher(itens, ini, fim, prox):
    for pos, val in itens:
        if fim <= pos < prox:
            return val
    for pos, val in itens:
        if pos >= fim:
            return val
    anteriores = [val for pos, val in itens if pos < ini]
    return anteriores[-1] if anteriores else None


def _cargo_efetivo(fatia: str):
    m = P_EFET_A.search(fatia)
    if m and not RUIM_EFET.search(m.group(1)):
        return m.group(1).strip(), False
    m = P_EFET_B.search(fatia)
    if m and not RUIM_EFET.search(m.group(2)):
        return m.group(2).strip(), bool(m.group(1))
    m = P_EFET_C.search(fatia)
    if m and not RUIM_EFET.search(m.group(1)):
        return m.group(1).strip(), False
    return None, False


def _primeiro(rx, txt, grupo=1):
    m = rx.search(txt)
    return m.group(grupo).strip() if m else None


def extrair_generico(texto: str) -> list[dict]:
    texto = RE_PONTILHADO.sub("", texto)     
    texto = re.sub(r"(?im)^.*edi[çc][ãa]o é composta.*$", "", texto)
    texto = RE_LETRAS.sub(lambda m: re.sub(r"\s", "", m.group()), texto) 
    pedacos = [p for p in RE_MARCA.split(texto) if p.strip()]
    registros, herdado_proc, herdada_data = [], None, None
    for ped in pedacos:
        if not RE_INICIO.match(ped):
            continue                               
        ped = _tirar_assinatura(ped)
        cab = _limpar(ped[:220])
        t = _limpar(ped)
        proc_ato = _primeiro(P_PROC, t)
        if re.search(r"(?i)resolve:\s*$", t):
            herdado_proc = proc_ato
            mh = re.search(r"(?i)\bde\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", cab)
            herdada_data = mh.group(1).lower() if mh else None
            continue
        if re.search(r"(?i)resolve:", t):
            corpo = re.split(r"(?i)resolve:", t, maxsplit=1)[-1]
        else:
            corpo = re.sub(r"^(?:DESPACHO|RETIFICA[ÇC][ÃA]O|PORTARIAS?)[^a-z]*?(?:\d{4})?\s*", "", t)
            corpo = re.sub(r"^[A-ZÁ-Ú][A-ZÁ-Ú\s\-/]{8,}?,\s*", "", corpo)
        m_num = re.search(r"N[º°o]\s*(\d{1,5})", cab) if re.match(r"\s*(?:PORTARIAS?\b|Nº)", ped) else None
        m_data = re.search(r"(?i)\bde\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", cab)
        em_grupo = bool(re.match(r"\s*Nº", ped))
        if not em_grupo:
            herdado_proc = herdada_data = None
        ato = {
            "numero_portaria": m_num.group(1) if m_num else None,
            "data_portaria": m_data.group(1).lower() if m_data else herdada_data,
            "processo": proc_ato or herdado_proc,
            "portaria_referida": _primeiro(P_REF, corpo) or (
                _primeiro(P_REF2, corpo) if re.match(r"\s*RETIFICA", ped) else None
            ),
            "data_efeito": _primeiro(P_EFEITO, corpo),
            "codigos_cargo": _primeiro(P_COD, corpo),
            "cargo": _primeiro(P_CARGO, corpo) or _primeiro(P_CARGO2, corpo),
            "cpf": None, "siape": None,
        }
        nomes = _nomes(corpo)
        titulo = re.match(r"\s*(PORTARIAS?|DESPACHO|RETIFICA[ÇC][ÃA]O|Nº)", ped)
        tipo_titulo = {"PORTARIA": "portaria", "PORTARIAS": "portaria", "DESPACHO": "despacho",
                       "Nº": "portaria"}.get((titulo.group(1) if titulo else "").upper().replace("Ç", "Ç"), None)
        if titulo and titulo.group(1).upper().startswith("RETIFICA"):
            tipo_titulo = "retificação"
        if tipo_titulo == "retificação":
            pass
        elif re.search(r"(?i)afastamento do pa[íi]s", corpo):
            tipo_titulo = "afastamento do país"
        elif re.search(r"(?i)declarar\s+vag", corpo):
            tipo_titulo = "declaração de vaga"
        if not nomes:
            continue
        cargos, codigos = _coletar(corpo)
        do_ato = []
        for k, (ini, fim, nome) in enumerate(nomes):
            prox = nomes[k + 1][0] if k + 1 < len(nomes) else len(corpo)
            fatia = corpo[fim:prox]
            antes = corpo[:ini]
            verbos = RE_VERBO.findall(antes)
            reg = {k2: v for k2, v in ato.items()}
            reg.update({
                "nome": nome.title().replace(" De ", " de ").replace(" Da ", " da ")
                .replace(" Do ", " do ").replace(" E ", " e ").replace(" Dos ", " dos ").replace(" Das ", " das "),
                "tipo_ato": (
                    tipo_titulo if tipo_titulo in ("afastamento do país", "declaração de vaga", "retificação")
                    else (_tipo(verbos[-1]) if verbos else tipo_titulo)
                ),
                "cpf": _primeiro(P_CPF, fatia) or ato["cpf"],
                "siape": _primeiro(P_SIAPE, fatia),
                "codigos_cargo": _escolher(codigos, ini, fim, prox),
                "cargo": _escolher(cargos, ini, fim, prox),
                "encargo": "substituto eventual"
                if re.search(r"(?i)encargo de substitut", antes[-120:] + fatia[:400]) else None,
                "texto_original_ato": t,
            })
            reg["cargo_efetivo"], comum = _cargo_efetivo(fatia)
            if not reg["cargo_efetivo"]:
                m_antes = P_EFET_ANTES.search(antes[-110:])
                reg["cargo_efetivo"] = m_antes.group(1).strip() if m_antes else None
            if comum:  
                for outro in do_ato:
                    outro["cargo_efetivo"] = outro["cargo_efetivo"] or reg["cargo_efetivo"]
            do_ato.append(reg)
            registros.append(reg)
    return registros