
import posixpath
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from copy import copy
from datetime import datetime
from difflib import SequenceMatcher
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ABA_PADRAO = "Principal"
ATOS_DE_ENTRADA = {"Nomeação", "Designação", "Recondução", "Redistribuição"}
MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_DRAWING = NS_R + "/drawing"
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"
CT_IMAGENS = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "emf": "image/x-emf", "wmf": "image/x-wmf",
}



def _norm(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def _sem_acento(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", _norm(texto).casefold())
        if unicodedata.category(c) != "Mn"
    )


def parse_data(texto):
    """'9 de abril de 2026' ou '09/04/2026' -> datetime (ou None)."""
    if not texto:
        return None
    texto = _norm(texto)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto)
    if m:
        d, mes, a = map(int, m.groups())
    else:
        m = re.search(r"(\d{1,2})º?\s+de\s+(\w+)\s+de\s+(\d{4})", texto, re.I)
        if not m or m.group(2).casefold() not in MESES:
            return None
        d, mes, a = int(m.group(1)), MESES[m.group(2).casefold()], int(m.group(3))
    try:
        return datetime(a, mes, d)
    except ValueError:
        return None



CAMPOS_ORIGEM = {
    "titularidade": "Titularidade (escolhida na tela)",
    "nome": "Nome",
    "motivo": "Tipo do ato (Nomeação, Exoneração…)",
    "inicio": "Data de início (só nomeação/designação)",
    "fim": "Data de fim (só exoneração/dispensa)",
    "data_efeito": "Data de efeito (qualquer ato)",
    "ato": "Ato (ex.: PORTARIA Nº 49, DE 9 DE ABRIL DE 2026)",
    "ato_designacao": "Ato — só se nomeação/designação",
    "ato_afastamento": "Ato — só se exoneração/dispensa",
    "numero_portaria": "Número da portaria",
    "data_portaria": "Data da portaria",
    "data_publicacao": "Data de publicação",
    "cargo": "Cargo/função (texto extraído)",
    "codigos_cargo": "Códigos do cargo (FCE/CCE)",
    "ministerio": "Ministério",
    "orgao": "Órgão",
    "arquivo": "Nome do PDF",
    "texto_original_ato": "Texto original do ato",
}


def registro_para_linha(registro, titularidade="Titular"):
    """Converte um registro extraído da portaria em um dict com todos os campos enviáveis."""
    tipo = registro.get("tipo_ato")
    entrada = tipo in ATOS_DE_ENTRADA
    ato = None
    if registro.get("numero_portaria"):
        ato = f"PORTARIA Nº {registro['numero_portaria']}"
        if registro.get("data_portaria"):
            ato += f", DE {_norm(registro['data_portaria']).upper()}"
    texto_efeito = registro.get("data_efeito")
    data = parse_data(texto_efeito)
    publicacao = registro.get("data_publicacao")
    codigos = registro.get("codigos_cargo")
    return {
        "titularidade": titularidade,
        "nome": registro.get("nome"),
        "cpf": registro.get("cpf"),
        "motivo": tipo,
        "inicio": data if entrada else None,
        "fim": None if entrada else data,
        "data_efeito": data or texto_efeito,
        "ato": ato,
        "ato_designacao": ato if entrada else None,
        "ato_afastamento": None if entrada else ato,
        "numero_portaria": registro.get("numero_portaria"),
        "data_portaria": (_norm(registro["data_portaria"]).upper()
                          if registro.get("data_portaria") else None),
        "data_publicacao": parse_data(publicacao) or publicacao,
        "cargo": registro.get("cargo"),
        "codigos_cargo": ", ".join(codigos) if isinstance(codigos, list) else codigos,
        "ministerio": registro.get("ministerio"),
        "orgao": registro.get("orgao"),
        "arquivo": registro.get("arquivo"),
        "texto_original_ato": registro.get("texto_original_ato"),
    }



COLUNAS = {
    "titularidade": 2, "nome": 3, "cpf": 4, "inicio": 5, "fim": 6,
    "motivo": 7, "ato_designacao": 8, "ato_afastamento": 9,
}
MAPEAMENTO_PADRAO = COLUNAS



def _linha_tem_dados(ws, linha, ncols=9):
    return any(ws.cell(linha, c).value not in (None, "") for c in range(2, ncols + 1))


def _merge_coluna_a(ws, linha_inicio):
    return next(
        (m for m in ws.merged_cells.ranges
         if m.min_col == 1 and m.max_col == 1 and m.min_row == linha_inicio),
        None,
    )


def detectar_blocos(ws):
    blocos = []
    for r in range(1, ws.max_row + 1):
        if _norm(ws.cell(r, 1).value).upper() == "CARGO":
            inicio = r + 2  
            merge = _merge_coluna_a(ws, inicio)
            fim = merge.max_row if merge else inicio
            blocos.append({
                "cargo": _norm(ws.cell(inicio, 1).value),
                "cabecalho": r, "inicio": inicio, "fim": fim,
            })
    return blocos


def _ultima_linha_com_dados(ws, bloco, ncols=9):
    ult = bloco["inicio"] - 1
    for r in range(bloco["inicio"], bloco["fim"] + 1):
        if _linha_tem_dados(ws, r, ncols):
            ult = r
    return ult


def listar_blocos(arquivo_excel, aba=ABA_PADRAO):
    wb = load_workbook(BytesIO(arquivo_excel))
    try:
        ws = wb[aba]
        return [b["cargo"] for b in detectar_blocos(ws)]
    finally:
        wb.close()


def listar_colunas(arquivo_excel, aba=ABA_PADRAO):
    """[(nº da coluna, 'E – PERÍODO DE GESTÃO › Data Início'), ...] lidos do 1º cabeçalho."""
    wb = load_workbook(BytesIO(arquivo_excel))
    try:
        ws = wb[aba]
        blocos = detectar_blocos(ws)
        if not blocos:
            return []
        topo = blocos[0]["cabecalho"]

        def rotulo(linha, col):
            valor = ws.cell(linha, col).value
            if valor in (None, ""):         
                for m in ws.merged_cells.ranges:
                    if m.min_row <= linha <= m.max_row and m.min_col <= col <= m.max_col:
                        valor = ws.cell(m.min_row, m.min_col).value
                        break
            return _norm(valor)

        colunas = []
        for c in range(2, ws.max_column + 1):
            sup, inf = rotulo(topo, c), rotulo(topo + 1, c)
            if not sup and not inf:
                continue
            texto = sup if (not inf or inf == sup) else (f"{sup} › {inf}" if sup else inf)
            colunas.append((c, f"{get_column_letter(c)} – {texto}"))
        return colunas
    finally:
        wb.close()


def sugerir_bloco(texto, cargos):
    """Cargo mais parecido com `texto` (ou None se nada se parece)."""
    if not texto:
        return None
    alvo = _sem_acento(texto)
    pontos = [(SequenceMatcher(None, alvo, _sem_acento(c)).ratio(), c) for c in cargos]
    melhor = max(pontos, default=(0, None))
    return melhor[1] if melhor[0] >= 0.45 else None



def _abrir_linha_no_fim_do_bloco(ws, bloco, blocos, ncols=9):
    """Insere uma linha logo após o bloco, deslocando o que vem abaixo."""
    idx = bloco["fim"] + 1
    merge_a = _merge_coluna_a(ws, bloco["inicio"])
    abaixo = [m for m in list(ws.merged_cells.ranges) if m.min_row >= idx]
    alturas = {r: d.height for r, d in ws.row_dimensions.items()
               if r >= idx and d.height is not None}
    altura_modelo = ws.row_dimensions[bloco["fim"]].height

    if merge_a is not None:
        ws.unmerge_cells(merge_a.coord)
    for m in abaixo:                     
        ws.merged_cells.ranges.discard(m)

    ws.insert_rows(idx)

    for m in abaixo:
        m.shift(row_shift=1)
        ws.merged_cells.ranges.add(m)
    for r in sorted(alturas, reverse=True):
        ws.row_dimensions[r + 1].height = alturas[r]
    ws.row_dimensions[idx].height = altura_modelo
    for celula in list(ws._cells.values()):   
        link = getattr(celula, "hyperlink", None)
        if link is not None:
            link.ref = celula.coordinate


    for col in range(2, ncols + 1):
        ws.cell(idx, col)._style = copy(ws.cell(bloco["fim"], col)._style)

    bloco["fim"] = idx
    ws.merge_cells(start_row=bloco["inicio"], start_column=1,
                   end_row=idx, end_column=1)
    for outro in blocos:
        if outro is not bloco and outro["cabecalho"] > bloco["cabecalho"]:
            for k in ("cabecalho", "inicio", "fim"):
                outro[k] += 1
    return idx


def _ja_existe(ws, bloco, linha, mapeamento, ncols):
    col_nome = mapeamento.get("nome")
    col_ato = (mapeamento.get("ato_designacao") if linha.get("ato_designacao")
               else mapeamento.get("ato_afastamento")) or mapeamento.get("ato")
    chave = (_sem_acento(linha.get("nome")), _sem_acento(linha.get("ato")))
    if not (col_nome and col_ato and chave[0] and chave[1]):
        return False
    return any(
        _linha_tem_dados(ws, r, ncols)
        and (_sem_acento(ws.cell(r, col_nome).value), _sem_acento(ws.cell(r, col_ato).value)) == chave
        for r in range(bloco["inicio"], bloco["fim"] + 1)
    )


def adicionar_linhas(arquivo_excel, itens, aba=ABA_PADRAO, mapeamento=None):
    wb = load_workbook(BytesIO(arquivo_excel))
    try:
        ws = wb[aba]
        mapeamento = {c: int(n) for c, n in (mapeamento or MAPEAMENTO_PADRAO).items() if n}
        ncols = max([9, *mapeamento.values()])
        blocos = detectar_blocos(ws)
        por_cargo = {b["cargo"]: b for b in blocos}
        inseridos, ignorados = [], []

        for item in itens:
            bloco = por_cargo.get(item["cargo"])
            if bloco is None:
                raise ValueError(f"Bloco não encontrado na planilha: {item['cargo']!r}")
            linha = item["linha"]

            if _ja_existe(ws, bloco, linha, mapeamento, ncols):
                ignorados.append((item["cargo"], linha.get("nome")))
                continue

            ult = _ultima_linha_com_dados(ws, bloco, ncols)
            if ult + 1 <= bloco["fim"]:
                alvo = ult + 1                       
            else:
                alvo = _abrir_linha_no_fim_do_bloco(ws, bloco, blocos, ncols)

            for campo, col in mapeamento.items():
                valor = linha.get(campo)
                if valor not in (None, ""):
                    celula = ws.cell(alvo, col, value=valor)
                    if isinstance(valor, datetime):
                        celula.number_format = "dd/mm/yyyy;@"
            inseridos.append((item["cargo"], alvo, linha.get("nome")))

        saida = BytesIO()
        wb.save(saida)
    finally:
        wb.close()

    return {
        "arquivo": _reinjetar_desenhos(arquivo_excel, saida.getvalue()),
        "inseridos": inseridos,
        "ignorados": ignorados,
    }


def _caminhos_das_abas(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    alvo = {r.get("Id"): r.get("Target") for r in rels}
    mapa = {}
    for aba in wb.find(f"{{{NS_MAIN}}}sheets"):
        destino = alvo[aba.get(f"{{{NS_R}}}id")].lstrip("/")
        mapa[aba.get("name")] = destino if destino.startswith("xl/") else "xl/" + destino
    return mapa


def _caminho_rels(parte):
    return posixpath.join(posixpath.dirname(parte), "_rels", posixpath.basename(parte) + ".rels")


def _reinjetar_desenhos(original, novo):
    """Copia formas/imagens (drawings) do arquivo original para o salvo pelo openpyxl."""
    zo = zipfile.ZipFile(BytesIO(original))
    zn = zipfile.ZipFile(BytesIO(novo))
    nomes_o = set(zo.namelist())
    abas_o, abas_n = _caminhos_das_abas(zo), _caminhos_das_abas(zn)
    partes = {n: zn.read(n) for n in zn.namelist()}
    ordem = list(zn.namelist())
    contador = 0

    for aba, parte_o in abas_o.items():
        rels_o = _caminho_rels(parte_o)
        if rels_o not in nomes_o or aba not in abas_n:
            continue
        rel = next((r for r in ET.fromstring(zo.read(rels_o))
                    if r.get("Type") == REL_DRAWING), None)
        parte_n = abas_n[aba]
        if rel is None or b"<drawing " in partes[parte_n]:
            continue

        contador += 1
        desenho_o = posixpath.normpath(
            posixpath.join(posixpath.dirname(parte_o), rel.get("Target")))
        desenho_n = f"xl/drawings/drawing_orig{contador}.xml"
        partes[desenho_n] = zo.read(desenho_o)
        ordem.append(desenho_n)

        content_types = partes["[Content_Types].xml"].decode("utf8")
        extra = f'<Override PartName="/{desenho_n}" ContentType="{CT_DRAWING}"/>'

        rels_desenho = _caminho_rels(desenho_o)
        if rels_desenho in nomes_o:
            novo_rels = f"xl/drawings/_rels/drawing_orig{contador}.xml.rels"
            partes[novo_rels] = zo.read(rels_desenho)
            ordem.append(novo_rels)
            for r in ET.fromstring(zo.read(rels_desenho)):
                midia = posixpath.normpath(
                    posixpath.join(posixpath.dirname(desenho_o), r.get("Target")))
                if midia in nomes_o and midia not in partes:
                    partes[midia] = zo.read(midia)
                    ordem.append(midia)
                    ext = midia.rsplit(".", 1)[-1].lower()
                    if ext in CT_IMAGENS and f'Extension="{ext}"' not in content_types:
                        extra += f'<Default Extension="{ext}" ContentType="{CT_IMAGENS[ext]}"/>'
        partes["[Content_Types].xml"] = content_types.replace(
            "</Types>", extra + "</Types>").encode("utf8")

        id_rel = f"rIdDrawOrig{contador}"
        nova_rel = (f'<Relationship Id="{id_rel}" Type="{REL_DRAWING}" '
                    f'Target="../drawings/drawing_orig{contador}.xml"/>')
        rels_n = _caminho_rels(parte_n)
        if rels_n in partes:
            partes[rels_n] = partes[rels_n].decode("utf8").replace(
                "</Relationships>", nova_rel + "</Relationships>").encode("utf8")
        else:
            partes[rels_n] = (f'<?xml version="1.0" encoding="UTF-8"?>'
                              f'<Relationships xmlns="{NS_PKG_REL}">{nova_rel}</Relationships>'
                              ).encode("utf8")
            ordem.append(rels_n)

        xml = partes[parte_n].decode("utf8")
        tag = f'<drawing xmlns:r="{NS_R}" r:id="{id_rel}"/>'
        pos = min((xml.find(t) for t in ("<legacyDrawing", "<picture", "<oleObjects",
                                          "<controls", "<tableParts", "<extLst")
                   if t in xml), default=xml.rfind("</worksheet>"))
        partes[parte_n] = (xml[:pos] + tag + xml[pos:]).encode("utf8")

    saida = BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in ordem:
            z.writestr(nome, partes[nome])
    return saida.getvalue()