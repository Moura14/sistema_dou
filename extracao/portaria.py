import re
import unicodedata
from bisect import bisect_right

import config.limpeza_texto as lt
from .config import regex_atos as ra


def _juntar_verbo(m):
    return m.group(1) + re.sub(r"\s+", "", m.group(2))


def normalizar_texto(texto):
    texto = lt._RE_LIXO.sub("", texto)
    texto = lt._RE_SUMARIO.sub("", texto)
    texto = ra._RE_VERBO_ESPACADO.sub(_juntar_verbo, texto)
    texto = texto.replace("\xa0", " ").replace("\u00ad", "")
    texto = re.sub(r"(\w)-\n(?=[a-zà-ú])", r"\1", texto)
    texto = re.sub(r"(?<=[a-zà-ú])(?=[A-ZÀ-Ý]{2})", " ", texto)
    texto = re.sub(r"(\bArt\.?\s*\d+\s*[º°]?)(?=[A-Za-zÀ-ú])", r"\1 ", texto)
    texto = re.sub(r"(?<=[.;])[ \t]+(?=N[º°]\s*\d[\d.]*\s*[-–—]\s)", "\n", texto)
    linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in texto.splitlines()]
    return "\n".join(l for l in linhas if l)

def _sem_acento(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii").lower()


def limpar(texto):
    if not texto:
        return None
    return re.sub(r"\s+", " ", texto).strip(" ,;:-") or None


def extrair_grupo(texto, padrao, grupo=1):
    match = padrao.search(texto)
    if not match:
        return None
    return limpar(match.group(grupo))


def normalizar_data(txt):
    if not txt:
        return None
    t = _sem_acento(txt)
    m = re.search(r"(\d{1,2})\s*o?\s+(?:de\s+)?([a-z]+)\s+de\s+(\d{4})", t)
    if m and m.group(2) in ra._NUM_MES:
        return f"{int(m.group(1)):02d}/{ra._NUM_MES[m.group(2)]:02d}/{m.group(3)}"
    m = re.search(r"(\d{1,2})o?[/.](\d{1,2})[/.](\d{4})", t)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    return limpar(txt)


def _tipo_do_verbo(verbo):
    v = verbo.lower()
    return next((tipo for raiz, tipo in ra._RAIZES if v.startswith(raiz)), None)


def _inicio_dispositivo(texto):
    m = ra._RE_RESOLVE.search(texto)
    return m.end() if m else 0


def identificar_acao(texto):
    m = ra._RE_ACAO.search(texto, _inicio_dispositivo(texto)) or ra._RE_ACAO.search(texto)
    if not m:
        return None, None
    return _tipo_do_verbo(m.group(1)), m


def identificar_ato(texto):
    tipo, _ = identificar_acao(texto)
    return tipo


def dividir_atos(corpo):
    ini = _inicio_dispositivo(corpo)
    marcas = [m.start() for m in ra._RE_INFINITIVO.finditer(corpo, ini)]
    if not marcas and ini:
        ini = 0
        marcas = [m.start() for m in ra._RE_INFINITIVO.finditer(corpo)]
    if len(marcas) <= 1:
        return [corpo[ini:]] if ini else [corpo]
    marcas.append(len(corpo))
    return [corpo[a:b] for a, b in zip(marcas, marcas[1:])]


def _nome_valido(nome):
    if not nome:
        return None
    palavras = nome.split()
    if not 2 <= len(palavras) <= 10 or any(c.isdigit() for c in nome):
        return None
    if any(_sem_acento(p) in ra._NAO_NOME for p in palavras):
        return None
    return nome


def _aparar_nome(nome):
    if not nome:
        return nome
    palavras = nome.split()
    if not palavras[0].isupper():
        return nome
    saida = []
    for i, p in enumerate(palavras):
        conector = p.lower() in ra._MINUSC and i + 1 < len(palavras) and palavras[i + 1].isupper()
        if p.isupper() or conector:
            saida.append(p)
        else:
            break
    return " ".join(saida)


def _nome_fallback(resto):
    for m in re.finditer(ra._MAIUSC_NOME, resto):
        nome = limpar(m.group(0))
        palavras = [_sem_acento(p) for p in nome.split()]
        if any(p in ra._NAO_NOME_EXTRA for p in palavras):
            continue
        if _nome_valido(nome):
            return nome
    return None


def extrair_nome_depois_acao(texto, resultado_acao):
    if not resultado_acao:
        return None
    resto = texto[resultado_acao.end():]
    m = ra._RE_NOME.search(resto[:250])
    if m:
        return _nome_valido(_aparar_nome(limpar(m.group(1))))
    for padrao in (ra._RE_NOME_SERVIDOR, ra._RE_NOME_ANTES_MATRICULA):
        m = padrao.search(resto[:1500])
        if m and _nome_valido(limpar(m.group(1))):
            return _nome_valido(limpar(m.group(1)))
    for padrao in (ra._RE_NOME_PASSIVO, ra._RE_NOME_SOLTO):
        m = padrao.search(resto[:400])
        if m and _nome_valido(limpar(m.group(1))):
            return _nome_valido(limpar(m.group(1)))
    return _nome_fallback(resto[:300])


def extrair_cargo(bloco):
    m = (ra._RE_CARGO.search(bloco) or ra._RE_CARGO_APOS_CPF.search(bloco)
         or ra._RE_CARGO_APOS_NOME.search(bloco))
    return limpar(m.group(1)) if m else None


def extrair_codigo(bloco):
    codigos = [f"{s.upper()}{n}" for s, n in ra._RE_CODIGO.findall(bloco)]
    if not codigos:
        letra = ra._RE_LETRA.search(r'\bLetra\s+["“”]?([A-Z])["“”]?', bloco)
        if letra:
            codigos = [f"Letra {letra.group(1)}"]
    return ", ".join(dict.fromkeys(codigos))


def extrair_cpf(bloco):
    return extrair_grupo(bloco, ra._RE_CPF)


def extrair_siape(bloco):
    return extrair_grupo(bloco, ra._RE_SIAPE)


def extrair_processo(bloco):
    return extrair_grupo(bloco, ra._RE_PROCESSO)


def extrair_data_efeito(bloco):
    m = ra._RE_EFEITO.search(bloco)
    return normalizar_data(m.group(1)) if m else None


def extrair_destino(bloco):
    m = ra._RE_DESTINO.search(bloco)
    return limpar(m.group(1)) if m else None


def extrair_ordem_substituicao(ato):
    return [
        (i + 1, limpar(m.group(2)), m.group(3).rstrip("."))
        for i, m in enumerate(ra._RE_ITEM_SUBST.finditer(ato))
    ]
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
    for campo, todas, qualquer, excluir in ra._REGRAS:
        if (campo in campos_disponiveis
                and todas <= palavras
                and (not qualquer or qualquer & palavras)
                and not excluir & palavras):
            return campo
    return None


def _achar_ocorrencias(texto):
    achados = sorted(list(ra._RE_NUM_TITULO.finditer(texto)) + list(ra._RE_NUM_ITEM.finditer(texto)),
                     key=lambda m: m.start())
    return achados or list(ra._RE_NUM_BARRA.finditer(texto)) or list(ra._RE_NUMERO.finditer(texto))


def _por_posicao(itens, pos, primeiro_se_nenhum=False):
    if not itens:
        return None
    i = bisect_right([p for p, _ in itens], pos) - 1
    if i < 0:
        return itens[0][1] if primeiro_se_nenhum else None
    return itens[i][1]


def _data_na_abertura(bloco):
    m = ra._RE_DATA_ABERTURA.search(bloco[:200])
    return normalizar_data(m.group(1)) if m else None


def _ultimo(itens, pos):
    i = bisect_right([p for p, _ in itens], pos) - 1
    return itens[i] if i >= 0 else (-1, None)


def _titulo(txt):
    if not txt or not txt.isupper():
        return txt
    pal = txt.lower().split()
    return " ".join(
        p if (k and p in ra._MINUSC) else "-".join(x.capitalize() for x in p.split("-"))
        for k, p in enumerate(pal)
    )


def _emissor(bloco):
    m = lt._RE_EMISSOR.search(bloco[:600])
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
            r = ra._RE_PORTARIA_REF.search(ato, acao.end())
            ref = limpar(" ".join(filter(None, r.groups()))) if r else None
            passado = ra._RE_PASSADO.search(ato, acao.end())
            if passado:
                acao, trecho = passado, ato[passado.end():]
        if not ref:
            rev = re.search(r"\brevogad[ao]\s+(?:a\s+)?", ato, re.I)
            if rev:
                r = ra._RE_PORTARIA_REF.search(ato, rev.end())
                ref = limpar(" ".join(filter(None, r.groups()))) if r else None
        cargo = extrair_cargo(trecho)
        cpf = extrair_cpf(ato)
        siape = extrair_siape(ato)
        encargo = None
        if cargo and re.match(r"substitut[oa]\s+eventual\b", cargo, re.I):
            encargo = "Substituto eventual"
            cargo = extrair_cargo(cargo) or cargo
        efeito = extrair_data_efeito(ato) or data_bloco
        if not efeito and ra._RE_VIGOR.search(corpo):
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
        m_cs = lt._RE_CARGO_APOS_NOME.search(ato)
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

def extrair_despachos(texto, base):
    saida = []
    for a in lt._RE_AFASTAMENTO.finditer(texto):
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
            continue  
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
    cab = lt._RE_DATA_DOU.search(texto)
    texto = normalizar_texto(texto)
    pub = lt._RE_PUBLICACAO.search(texto)
    org = lt._RE_ORGAO.search(texto)
    publicacao = pub.group(1) if pub else (normalizar_data(cab.group(1)) if cab else None)
    orgao_global = limpar(org.group(1)) if org else None
    datas = [(m.start(), normalizar_data(m.group(1))) for m in lt._RE_DATA_CAB.finditer(texto)]
    ministerios = [(m.start(), _titulo(limpar(m.group(1) or m.group(2))))
                   for m in lt._RE_MINISTERIO.finditer(texto)]
    unidades = [(m.start(), _titulo(limpar(m.group(1)))) for m in lt._RE_UNIDADE.finditer(texto)]
    ocorrencias = _achar_ocorrencias(texto)
    registros = []
    for i, oc in enumerate(ocorrencias):
        inicio = oc.start()
        fim = ocorrencias[i + 1].start() if i + 1 < len(ocorrencias) else len(texto)
        bloco = texto[inicio:fim]
        corte = lt._RE_CORTE.search(bloco)
        if corte:
            bloco = bloco[:corte.start()]
        desp = lt._RE_DESPACHO.search(bloco)
        if desp:
            bloco = bloco[:desp.start()]
        corpo = bloco[oc.end() - inicio:]
        pos_min, ministerio = _ultimo(ministerios, inicio)
        pos_uni, unidade = _ultimo(unidades, inicio)
        if unidade and pos_uni < pos_min:
            unidade = None
        emissor = _emissor(bloco)
        if oc.re is lt._RE_NUM_ITEM:
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
        t = lt._RE_TITULO.search(texto)
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
    if not registros and ra._RE_ACAO.search(texto):
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
