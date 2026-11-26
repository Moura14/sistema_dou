from datetime import datetime
from functools import partial
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from planilhas.leitura import listar_abas, ler_planilha


st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

ARQ = (
    Path(__file__).resolve().parent.parent
    / "dados_compartilhados"
    / "planilha_atual.xlsx"
)

MAX_CATEGORIAS = 25
COR = "#4F8BF9"
COR_OUTROS = "#A9B0BC"
COR_OCUPADO = "#20A39E"
COR_VAGO = "#EF6461"
PALETA = ["#4F8BF9", "#7C5CFC", "#20A39E", "#F59E0B", "#EF6461",
          "#36B37E", "#FF7A59", "#5C9EAD", "#8C6BB1", "#E39A2D"]
INTERVALO_ATUALIZACAO = 30
JANELA_RECENTES = 90

SEM_INTERESSE_CONTEM = ("siorg", "uorg", "sigla", "logradouro",
                        "complemento", "munic", "telefone", "mail")
SEM_INTERESSE_EXATAS = {"uf", "cep"}
OPCIONAL_CONTEM = ("observ", "substituto", "processo.1", "processo (2)", "processo_2")
OPCIONAL_EXATAS = {"nome"}
COLUNAS_DATA = ("nomea", "data", "posse")

FAIXAS_TEMPO = ["Até 6 meses", "6 meses a 1 ano", "1 a 2 anos",
                "2 a 4 anos", "Mais de 4 anos"]

ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")




def sem_interesse(c: str) -> bool:
    lc = c.lower()
    return lc in SEM_INTERESSE_EXATAS or any(k in lc for k in SEM_INTERESSE_CONTEM)


def relevante(c: str) -> bool:
    lc = c.lower()
    return (not sem_interesse(c) and lc not in OPCIONAL_EXATAS
            and not any(k in lc for k in OPCIONAL_CONTEM))


def limpar_texto(v):
    """Remove caracteres invisíveis, tabs, quebras de linha e espaços duplicados."""
    if not isinstance(v, str):
        return v
    v = ZERO_WIDTH.sub("", v).replace("\xa0", " ")
    v = re.sub(r"\s+", " ", v).strip()
    return v if v else pd.NA


def parse_data(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return pd.NaT
    if isinstance(v, datetime):
        ts = pd.Timestamp(v)
    else:
        s = str(v).strip()
        ts = pd.NaT
        m_iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
        try:
            if m_iso:
                a, mo, d = map(int, m_iso.groups())
                ts = pd.Timestamp(a, mo, d)
            elif m:
                d, mo, a = map(int, m.groups())
                ts = pd.Timestamp(a, mo, d)
            elif re.fullmatch(r"\d{5}(\.0+)?", s):
                ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(s)))
        except ValueError:
            return pd.NaT
    if pd.notna(ts) and not (1990 <= ts.year <= 2100):
        return pd.NaT
    return ts


def _achar(df: pd.DataFrame, pred) -> str | None:
    return next((c for c in df.columns if pred(c.lower())), None)


def achar_col_servidor(df):
    return _achar(df, lambda lc: lc.startswith("servidor"))


def achar_col_unidade(df):
    return _achar(df, lambda lc: "denomina" in lc and "unidade" in lc
                  and "superior" not in lc)


def achar_col_superior(df):
    return _achar(df, lambda lc: "denomina" in lc and "unidade" in lc
                  and "superior" in lc)


def achar_col_cargo(df):
    return _achar(df, lambda lc: "denomina" in lc and "unidade" not in lc
                  and any(k in lc for k in ("cargo", "funç", "func")))


def achar_col_codigo(df):
    return _achar(df, lambda lc: "fce" in lc and "cce" in lc)


def achar_col_macro(df):
    return _achar(df, lambda lc: lc.startswith("macro"))


def achar_col_nomeacao(df):
    return _achar(df, lambda lc: lc.startswith("nomea"))


def achar_col_siape(df):
    return _achar(df, lambda lc: lc == "siape")


def achar_col_processo(df):
    return _achar(df, lambda lc: lc == "processo")


def achar_col_obs(df):
    return _achar(df, lambda lc: lc.startswith("observ"))


def achar_col_municipio(df):
    return _achar(df, lambda lc: lc.startswith("munic"))


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    df = df.dropna(axis=1, how="all")
    for c in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].map(limpar_texto)

    invalidas = {}
    for c in df.columns:
        if any(k in c.lower() for k in COLUNAS_DATA):
            bruto = df[c]
            conv = bruto.map(parse_data)
            if conv.notna().sum() >= 0.5 * bruto.notna().sum():
                mask = conv.isna() & bruto.notna()
                if mask.any():
                    invalidas[c] = bruto[mask]
                df[c] = pd.to_datetime(conv)

    col_serv = achar_col_servidor(df)
    if col_serv:
        df["Situação"] = (
            df[col_serv].astype(str).str.strip().str.upper().eq("VAGO")
            .map({True: "Vago", False: "Ocupado"})
        )
    col_cod = achar_col_codigo(df)
    if col_cod:
        cod = df[col_cod].astype(str)
        df["Tipo de função"] = cod.str.extract(r"^\s*(CCE|FCE)", flags=re.I)[0].str.upper()
        nivel = cod.str.extract(r"\.(\d{1,2})\s*$")[0]
        df["Nível"] = nivel.map(lambda n: f"Nível {int(n):02d}" if pd.notna(n) else pd.NA)

    df.attrs["datas_invalidas"] = invalidas
    return df


st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem;}
    div[data-testid="stSidebarContent"] {padding-top: 6rem;}
    .hero {
        background: transparent;
        color: inherit; padding: 0;
        margin-bottom: 18px;
        box-shadow: none;
    }
    .hero h1 {margin: 0; font-size: 1.9rem; color: inherit;}
    .hero p {margin: 6px 0 0 0; opacity: .92;}
    .chip {
        display: inline-block; background: rgba(128,128,128,.18);
        padding: 2px 12px; border-radius: 999px; margin-right: 8px;
        font-size: .85rem;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(128,128,128,.04);
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform .15s ease, box-shadow .15s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(0,0,0,0.10);
    }
    div[data-testid="stMetric"] {background: transparent; border: none; padding: 0;}
    div[data-testid="stMetricValue"] {font-size: 1.8rem;}
    button[data-baseweb="tab"] {font-weight: 600;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def carregar(mtime: float, aba: str) -> pd.DataFrame:
    plan = ler_planilha(ARQ.read_bytes(), aba, None)
    df = pd.DataFrame.from_dict(plan["tabela"], orient="index")
    df = df.reindex(columns=plan["colunas"])
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    df.index.name = "Linha"
    return df


def encurtar(txt: str, n: int = 28) -> str:
    return txt if len(txt) <= n else txt[: n - 1] + "…"


def contagem_com_outros(serie: pd.Series, col: str, topn: int) -> pd.DataFrame:
    cont = serie.dropna().astype(str).value_counts()
    top = cont.head(topn)
    resto = cont.iloc[topn:].sum()
    if resto > 0:
        top = pd.concat([top, pd.Series({"Outros": resto})])
    out = top.rename_axis(col).reset_index(name="Quantidade")
    out["Rótulo"] = out[col].map(encurtar)
    return out


def _cores_com_outros(rotulos: pd.Series) -> list:
    cores = [PALETA[i % len(PALETA)] for i in range(len(rotulos))]
    return [COR_OUTROS if r == "Outros" else cores[i]
            for i, r in enumerate(rotulos)]


def grafico_barras(cont, col, height=300):
    cores = _cores_com_outros(cont["Rótulo"])
    fig = px.bar(cont, x="Quantidade", y="Rótulo", orientation="h",
                 text="Quantidade", hover_data={col: True, "Rótulo": False})
    fig.update_traces(marker_color=cores, textposition="outside",
                      cliponaxis=False,
                      hovertemplate="%{customdata[0]}: <b>%{x}</b><extra></extra>")
    fig.update_layout(
        height=height, margin=dict(l=0, r=10, t=10, b=0),
        yaxis={"categoryorder": "total ascending", "title": None},
        xaxis={"title": None, "showgrid": False},
    )
    return fig


def grafico_pizza(cont, col, height=300):
    cores = _cores_com_outros(cont["Rótulo"])
    fig = px.pie(cont, names="Rótulo", values="Quantidade", hole=0.58,
                 hover_data={col: True}, color_discrete_sequence=cores)
    fig.update_traces(textinfo="percent", textposition="inside",
                      hovertemplate="%{label}: <b>%{value}</b> (%{percent})<extra></extra>")
    fig.add_annotation(text=f"<b>{int(cont['Quantidade'].sum())}</b>",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=24))
    fig.update_layout(
        height=height, margin=dict(l=0, r=10, t=10, b=0),
        legend=dict(orientation="h", y=-0.05, font=dict(size=11)),
    )
    return fig


def grafico_treemap(cont, col, height=300):
    fig = px.treemap(cont, path=["Rótulo"], values="Quantidade",
                     hover_data={col: True})
    fig.update_traces(textinfo="label+value")
    fig.update_layout(
        height=height, margin=dict(l=0, r=10, t=10, b=0),
        treemapcolorway=PALETA,
    )
    return fig


def grafico_lollipop(cont, col, height=300):
    cont = cont.sort_values("Quantidade")
    cores = _cores_com_outros(cont["Rótulo"])
    fig = go.Figure(go.Scatter(
        x=cont["Quantidade"],
        y=cont["Rótulo"],
        mode="markers+lines",
        line=dict(color=COR, width=2),
        marker=dict(size=10, color=cores),
        text=cont["Quantidade"],
        textposition="middle right",
        hovertemplate="%{customdata}: <b>%{x}</b><extra></extra>",
        customdata=cont[col],
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=10, t=10, b=0),
        yaxis={"categoryorder": "total ascending", "title": None},
        xaxis={"title": None, "showgrid": False},
    )
    return fig


def grafico_empilhado(df, eixo, cor, height=420):
    """Barras horizontais empilhadas: contagem de `cor` dentro de cada `eixo`."""
    t = (df.dropna(subset=[eixo, cor]).groupby([eixo, cor]).size()
         .reset_index(name="Quantidade"))
    t[eixo] = t[eixo].astype(str)
    ordem = t.groupby(eixo)["Quantidade"].sum().sort_values().index.tolist()
    mapa = {"Ocupado": COR_OCUPADO, "Vago": COR_VAGO} if cor == "Situação" else None
    fig = px.bar(t, x="Quantidade", y=eixo, color=cor, orientation="h",
                 text="Quantidade", category_orders={eixo: ordem},
                 color_discrete_map=mapa, color_discrete_sequence=PALETA)
    fig.update_traces(textposition="inside",
                      hovertemplate="%{y} · %{fullData.name}: <b>%{x}</b><extra></extra>")
    fig.update_layout(
        height=max(height, 26 * len(ordem) + 90),
        margin=dict(l=0, r=10, t=10, b=0), barmode="stack",
        yaxis={"title": None}, xaxis={"title": None, "showgrid": False},
        legend=dict(orientation="h", y=1.08, title=None),
    )
    return fig


def grafico_categoria(df, col, tipo, topn, height=300):
    cont = contagem_com_outros(df[col], col, topn)

    if tipo == "Pizza (auto)" or tipo == "Automático":
        tipo = "Pizza"

    if tipo == "Pizza":
        return grafico_pizza(cont, col, height)
    if tipo == "Treemap":
        return grafico_treemap(cont, col, height)
    if tipo == "Lollipop":
        return grafico_lollipop(cont, col, height)
    return grafico_barras(cont, col, height)


def _clique(col: str, key: str):
    ev = st.session_state.get(key)
    try:
        pontos = ev["selection"]["points"] if ev else []
    except (KeyError, TypeError):
        pontos = []
    valores = []
    for p in pontos:
        cd = p.get("customdata")
        v = cd[0] if isinstance(cd, (list, tuple)) and cd else cd
        if v is not None and str(v) != "Outros":
            valores.append(str(v))
    st.session_state[f"f_{col}"] = sorted(set(valores))


def mostrar_grafico(df, col, tipo, topn, key, height=300, permitir_clique=True):
    fig = grafico_categoria(df, col, tipo, topn, height=height)
    if permitir_clique and tipo in ("Barras", "Lollipop", "Pizza (auto)", "Automático"):
        st.plotly_chart(
            fig, use_container_width=True, key=key,
            on_select=partial(_clique, col, key), selection_mode="points",
        )
    else:
        st.plotly_chart(fig, use_container_width=True, key=key)


def limpar_filtros():
    for k in list(st.session_state.keys()):
        if k.startswith(("f_", "g_")):
            del st.session_state[k]



def formatar_dias(dias: int) -> str:
    if dias < 0:
        return "data futura"
    anos, resto = divmod(int(dias), 365)
    meses = resto // 30
    if anos:
        txt = f"{anos} ano{'s' if anos > 1 else ''}"
        if meses:
            txt += f" e {meses} {'meses' if meses > 1 else 'mês'}"
        return txt
    if meses:
        return f"{meses} {'meses' if meses > 1 else 'mês'}"
    return f"{int(dias)} dia{'s' if dias != 1 else ''}"


def tempo_desde(data: pd.Timestamp) -> str:
    return formatar_dias((pd.Timestamp.now().normalize() - data).days)


def dias_desde(serie: pd.Series) -> pd.Series:
    return (pd.Timestamp.now().normalize() - serie).dt.days


def faixa_tempo(dias: pd.Series) -> pd.Series:
    return pd.cut(
        dias, bins=[-10**9, 182, 365, 730, 1461, 10**9],
        labels=FAIXAS_TEMPO,
    )


def ficha_servidor(base: pd.DataFrame, col_serv: str, nomes: list, datas: list):
    chave = base[col_serv].astype(str).str.strip()
    for nome in nomes:
        regs = base[chave == nome]
        with st.container(border=True):
            st.markdown(f"#### 👤 {nome}")
            if regs.empty:
                st.caption("Nenhum registro encontrado para este servidor.")
                continue
            if len(regs) > 1:
                st.caption(f"Este servidor aparece em {len(regs)} cargos/funções.")

            for i, (linha, reg) in enumerate(regs.iterrows(), start=1):
                if len(regs) > 1:
                    st.markdown(f"**Cargo/função {i}** · linha {linha} da planilha")
                else:
                    st.caption(f"Linha {linha} da planilha")

                datas_reg = [c for c in datas if pd.notna(reg[c])]
                for k in range(0, len(datas_reg), 4):
                    cs = st.columns(4)
                    for j, c in enumerate(datas_reg[k:k + 4]):
                        cs[j].metric(c, f"{reg[c]:%d/%m/%Y}")
                        if "nomea" in c.lower():
                            t = tempo_desde(reg[c])
                            cs[j].caption(f"⏱️ {t}" if t == "data futura" else f"⏱️ há {t}")

                outros = [
                    (c, v) for c, v in reg.items()
                    if c != col_serv and c not in datas and c != "Situação" and pd.notna(v)
                ]
                if outros:
                    meio = (len(outros) + 1) // 2
                    ca, cb = st.columns(2)
                    for coluna, itens in ((ca, outros[:meio]), (cb, outros[meio:])):
                        for campo, valor in itens:
                            coluna.markdown(f"**{campo}:** {valor}")
                if i < len(regs):
                    st.divider()


def checagens(base: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    """Devolve [(título, explicação, linhas)] só com os problemas que existem."""
    col_serv = achar_col_servidor(base)
    col_nom = achar_col_nomeacao(base)
    col_siape = achar_col_siape(base)
    col_proc = achar_col_processo(base)
    col_mun = achar_col_municipio(base)
    col_obs = achar_col_obs(base)
    col_cargo = achar_col_cargo(base)
    col_cod = achar_col_codigo(base)
    col_unid = achar_col_unidade(base)

    ocup = base[base["Situação"] == "Ocupado"] if "Situação" in base.columns else base
    base_cols = [c for c in (col_serv, col_cargo, col_cod, col_unid) if c]
    achados = []

    def add(titulo, expl, linhas, extra=()):
        if len(linhas):
            cols = base_cols + [c for c in extra if c and c not in base_cols]
            achados.append((titulo, expl, linhas[cols]))

    if col_nom and pd.api.types.is_datetime64_any_dtype(base[col_nom]):
        ja_listadas = base.attrs.get("datas_invalidas", {}).get(col_nom)
        sem_data = ocup[ocup[col_nom].isna()]
        if ja_listadas is not None:
            sem_data = sem_data[~sem_data.index.isin(ja_listadas.index)]
        add("Ocupados sem data de nomeação",
            "Cargo ocupado, mas a coluna de nomeação está vazia.",
            sem_data, (col_nom,))
        hoje = pd.Timestamp.now().normalize()
        add("Nomeação com data futura",
            "Possível erro de digitação no dia, mês ou ano.",
            ocup[ocup[col_nom] > hoje], (col_nom,))

    for c, bruto in base.attrs.get("datas_invalidas", {}).items():
        linhas = base.loc[bruto.index, [x for x in base_cols]].copy()
        linhas[f"{c} (texto original)"] = bruto
        if len(linhas):
            achados.append((f"Datas não reconhecidas em “{c}”",
                            "O texto não pôde ser lido como data (ou o ano é absurdo).",
                            linhas))

    if col_siape:
        add("Ocupados sem SIAPE", "Cargo ocupado sem matrícula SIAPE.",
            ocup[ocup[col_siape].isna()])
    if col_proc:
        add("Ocupados sem nº de processo", "Falta o processo da nomeação.",
            ocup[ocup[col_proc].isna()], (col_proc,))
    if col_mun:
        txt = base[col_mun].astype("string")
        add("Município com valor suspeito",
            "O campo tem só números (parece telefone/CPF no lugar errado).",
            base[txt.str.fullmatch(r"[\d.\-/ ]+", na=False)], (col_mun,))
    if col_serv:
        nomes = base.loc[base["Situação"] == "Ocupado", col_serv] \
            if "Situação" in base.columns else base[col_serv]
        dup = nomes[nomes.str.upper().duplicated(keep=False)].index
        add("Servidores em mais de um cargo",
            "Não é necessariamente erro (acúmulo de funções), mas vale conferir.",
            base.loc[dup].sort_values(col_serv))
    if col_obs and "Situação" in base.columns:
        v = base[(base["Situação"] == "Vago") & base[col_obs].notna()]
        add("Vagas com observação",
            "Vagas que têm alguma anotação (ex.: quem vai entrar).",
            v, (col_obs,))
    return achados


@st.fragment(run_every=INTERVALO_ATUALIZACAO)
def painel():
    if not ARQ.exists():
        st.info("Ainda não há planilha publicada.")
        return

    mtime = ARQ.stat().st_mtime
    try:
        abas = listar_abas(ARQ.read_bytes())
    except Exception:
        st.error("Não foi possível ler o arquivo da planilha. Verifique se ele está íntegro.")
        return

    aba = st.sidebar.selectbox("Aba", abas, key="aba") if len(abas) > 1 else abas[0]

    try:
        base = preparar(carregar(mtime, aba).copy())
    except Exception:
        st.error("Não foi possível carregar os dados desta aba. Tente outra aba.")
        return

    if base.empty:
        st.warning("A aba selecionada não tem dados.")
        return

    atualizado = pd.Timestamp(mtime, unit="s", tz="UTC").tz_convert("America/Sao_Paulo")
    st.markdown(
        f"""<div class="hero"><h1>📊 Painel da planilha</h1>
        <p><span class="chip">Aba <b>{aba}</b></span>
        <span class="chip">{len(base)} linhas</span>
        <span class="chip">Atualizada em {atualizado:%d/%m/%Y às %H:%M:%S}</span></p></div>""",
        unsafe_allow_html=True,
    )

    categoricas = [
        c for c in base.columns
        if not pd.api.types.is_datetime64_any_dtype(base[c])
        and relevante(c)
        and 2 <= base[c].nunique() <= MAX_CATEGORIAS
    ]

    cols_graf = [c for c in categoricas if c != "Situação"] or categoricas
    col_unidade = achar_col_unidade(base)
    col_cargo = achar_col_cargo(base)
    col_macro = achar_col_macro(base)
    col_superior = achar_col_superior(base)
    col_cod = achar_col_codigo(base)
    col_obs = achar_col_obs(base)
    reservadas = {"Tipo de função", "Nível", col_unidade, col_cargo}
    principais = [c for c in cols_graf if c not in reservadas] or cols_graf

    cols_explorar = list(cols_graf)
    for c in (col_unidade, col_cargo, col_superior):
        if c and c not in cols_explorar:
            cols_explorar.append(c)

    datas = [c for c in base.columns if pd.api.types.is_datetime64_any_dtype(base[c])
             and base[c].notna().any()]
    col_nom = next((c for c in datas if c.lower().startswith("nomea")), None)

    col_serv = achar_col_servidor(base)
    nomes_serv = []
    if col_serv:
        nomes_serv = sorted({
            str(v).strip() for v in base[col_serv].dropna()
            if str(v).strip() and str(v).strip().upper() != "VAGO"
        })
        if "f_servidor" in st.session_state:
            st.session_state["f_servidor"] = [
                n for n in st.session_state["f_servidor"] if n in nomes_serv
            ]

    df = base
    total_bruto = len(base)
    with st.sidebar:
        st.header("🔎 Filtros")
        st.markdown('<div style="height: 1.25rem;"></div>', unsafe_allow_html=True)
        if nomes_serv:
            st.markdown("**👤 Procurar um servidor**")
            st.multiselect(
                "Nome do servidor", nomes_serv, key="f_servidor",
                placeholder="Digite o nome…", max_selections=5,
                help="Comece a digitar para encontrar o nome (até 5 servidores). "
                     "A ficha com a data de nomeação e demais informações aparece "
                     "no topo da página. Os gráficos e números não mudam.",
            )
            st.divider()

        def filtro(c):
            nonlocal df
            opcoes = sorted(base[c].dropna().astype(str).unique())
            chave = f"f_{c}"
            if chave in st.session_state:
                st.session_state[chave] = [v for v in st.session_state[chave]
                                           if v in opcoes]
            escolha = st.multiselect(c, opcoes, key=chave, placeholder="Todos")
            if escolha:
                df = df[df[c].astype(str).isin(escolha)]

        if categoricas:
            st.markdown("**Filtrar por categoria**")
            for c in categoricas:
                filtro(c)

    with st.sidebar:
        st.divider()
        st.button("🧹 Limpar todos os filtros", on_click=limpar_filtros,
                  use_container_width=True)
        st.caption(f"**{len(df)}** de **{total_bruto}** linhas exibidas")
        st.caption(f"🔄 Atualização automática a cada {INTERVALO_ATUALIZACAO}s")

    sel_serv = st.session_state.get("f_servidor") or []
    if sel_serv and col_serv:
        ficha_servidor(base, col_serv, sel_serv, datas)

    if df.empty:
        st.warning("Nenhuma linha com os filtros atuais. Use o botão **Limpar todos os filtros** na barra lateral.")
        return

    tem_situacao = "Situação" in df.columns
    ocup = df[df["Situação"] == "Ocupado"] if tem_situacao else df
    vagos = len(df) - len(ocup)

    # ── KPIs ──
    kpis = [("Cargos e funções", len(df), None),
            ("Ocupados", len(ocup), f"{len(ocup) / len(df):.0%} do total"),
            ("Vagos", vagos, f"{vagos / len(df):.0%} do total")]
    if col_nom:
        hoje = pd.Timestamp.now().normalize()
        dn = ocup[col_nom].dropna()
        recentes = int(((dn >= hoje - pd.Timedelta(days=JANELA_RECENTES)) & (dn <= hoje)).sum())
        kpis.append((f"Nomeações em {JANELA_RECENTES} dias", recentes, None))

    for coluna, (rotulo, valor, delta) in zip(st.columns(len(kpis)), kpis):
        with coluna, st.container(border=True):
            if delta:
                st.metric(rotulo, valor, delta=delta, delta_color="off")
            else:
                st.metric(rotulo, valor)

    st.write("")
    tab1, tab_est, tab_perm = st.tabs([
        "📈 Visão geral", "🏛️ Estrutura e vacância", "⏱️ Permanência",
    ])

    with tab1:
        if not cols_graf:
            st.info("Não há colunas categóricas suficientes para gráficos.")
        else:
            col_principal = principais[0]
            if col_unidade and col_unidade != col_principal:
                col_secundaria = col_unidade
            elif "Tipo de função" in cols_graf and col_principal != "Tipo de função":
                col_secundaria = "Tipo de função"
            else:
                col_secundaria = principais[1] if len(principais) > 1 else None

            g1, g2, g3 = st.columns([1.5, 1.5, 1])
            with g1, st.container(border=True):
                st.markdown(f"**Distribuição: {col_principal}**")
                mostrar_grafico(df, col_principal, "Barras", 8, "g_principal")
                st.caption("💡 Clique em uma barra para filtrar todo o painel.")
            with g2, st.container(border=True):
                if col_secundaria:
                    st.markdown(f"**Distribuição: {col_secundaria}**")
                    mostrar_grafico(df, col_secundaria, "Barras", 8, "g_secundaria")
                else:
                    st.info("Poucas colunas para exibir gráficos secundários.")
            with g3, st.container(border=True):
                if col_cargo:
                    st.markdown(f"**{col_cargo}**")
                    mostrar_grafico(df, col_cargo, "Pizza (auto)", 8, "g_cargo")
                elif tem_situacao:
                    st.markdown("**Status: Ocupação**")
                    mostrar_grafico(df, "Situação", "Pizza", 2, "g_status")
                elif "Tipo de função" in df.columns:
                    st.markdown("**Tipo de função**")
                    mostrar_grafico(df, "Tipo de função", "Pizza (auto)", 5, "g_tipo")
                else:
                    st.info("Sem dados de status.")

            st.markdown('<div style="height: 2rem;"></div>', unsafe_allow_html=True)
            st.markdown("### 🧭 Explorar")
            with st.container(border=True):
                e1, e2, e3 = st.columns([2, 2, 1])
                col = e1.selectbox("Analisar por", cols_explorar, key="g_exp_col")
                opcoes_tipo = ["Barras", "Lollipop", "Pizza", "Treemap"]
                if st.session_state.get("g_exp_tipo") not in opcoes_tipo:
                    st.session_state["g_exp_tipo"] = opcoes_tipo[0]
                tipo = e2.radio("Tipo de gráfico", opcoes_tipo, horizontal=True, key="g_exp_tipo")
                topn = e3.slider("Top N", 3, 20, 10, key="g_exp_topn")
                mostrar_grafico(df, col, tipo, topn, f"g_exp_{tipo}", height=380)

    with tab_est:
        if not (col_macro and col_macro in df.columns):
            st.info("Esta aba não tem uma coluna de macro unidade para comparar.")
        else:
            c1, c2 = st.columns(2)
            if tem_situacao:
                with c1, st.container(border=True):
                    st.markdown(f"**Ocupação por {col_macro}**")
                    st.plotly_chart(grafico_empilhado(df, col_macro, "Situação"),
                                    use_container_width=True, key="g_est_sit")
            if "Tipo de função" in df.columns:
                with c2, st.container(border=True):
                    st.markdown(f"**CCE × FCE por {col_macro}**")
                    st.plotly_chart(grafico_empilhado(df, col_macro, "Tipo de função"),
                                    use_container_width=True, key="g_est_tipo")

            n1, n2 = st.columns([1, 2])
            if "Nível" in df.columns:
                with n1, st.container(border=True):
                    st.markdown("**Cargos por nível**")
                    niv = df["Nível"].dropna().value_counts().sort_index() \
                        .rename_axis("Nível").reset_index(name="Quantidade")
                    fig = px.bar(niv, x="Nível", y="Quantidade", text="Quantidade",
                                 color_discrete_sequence=[COR])
                    fig.update_traces(textposition="outside", cliponaxis=False)
                    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0),
                                      xaxis_title=None, yaxis_title=None,
                                      yaxis=dict(showgrid=False))
                    st.plotly_chart(fig, use_container_width=True, key="g_est_nivel")

    with tab_perm:
        if not col_nom or not tem_situacao:
            st.info("É preciso ter uma coluna de nomeação e a situação (ocupado/vago) para esta análise.")
        else:
            o = ocup[ocup[col_nom].notna()].copy()
            o["_dias"] = dias_desde(o[col_nom])
            futuras = int((o["_dias"] < 0).sum())
            o = o[o["_dias"] >= 0]
            if o.empty:
                st.info("Não há nomeações com data válida com os filtros atuais.")
            else:
                st.caption(
                    f"Base: {len(o)} de {len(ocup)} ocupados com data de nomeação válida"
                    + (f" · {futuras} com data futura ignorados." if futuras else ".")
                )
                m1, m2, m3 = st.columns(3)
                m1.metric("Tempo mediano no cargo", formatar_dias(int(o["_dias"].median())))
                m2.metric("Tempo médio no cargo", formatar_dias(int(o["_dias"].mean())))
                m3.metric("Há mais de 4 anos no cargo", int((o["_dias"] > 1461).sum()))

                p1, p2 = st.columns(2)
                with p1, st.container(border=True):
                    st.markdown("**Quanto tempo no cargo**")
                    o["Faixa"] = faixa_tempo(o["_dias"])
                    f = (o["Faixa"].value_counts().reindex(FAIXAS_TEMPO).fillna(0)
                         .astype(int).rename_axis("Faixa").reset_index(name="Pessoas"))
                    fig = px.bar(f, x="Faixa", y="Pessoas", text="Pessoas",
                                 category_orders={"Faixa": FAIXAS_TEMPO},
                                 color_discrete_sequence=[COR])
                    fig.update_traces(textposition="outside", cliponaxis=False)
                    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0),
                                      xaxis_title=None, yaxis_title=None,
                                      yaxis=dict(showgrid=False))
                    st.plotly_chart(fig, use_container_width=True, key="g_perm_faixa")
                with p2, st.container(border=True):
                    if col_macro and col_macro in o.columns:
                        st.markdown(f"**Tempo mediano (anos) por {col_macro}**")
                        t = (o.groupby(col_macro)["_dias"].agg(["median", "size"])
                             .rename(columns={"median": "Anos", "size": "Pessoas"})
                             .reset_index())
                        t["Anos"] = (t["Anos"] / 365.25).round(1)
                        fig = px.bar(t.sort_values("Anos"), x="Anos", y=col_macro,
                                     orientation="h", text="Anos", hover_data=["Pessoas"],
                                     color_discrete_sequence=[COR])
                        fig.update_traces(textposition="outside", cliponaxis=False)
                        fig.update_layout(height=340, margin=dict(l=0, r=10, t=10, b=0),
                                          xaxis_title=None, yaxis_title=None,
                                          xaxis=dict(showgrid=False))
                        st.plotly_chart(fig, use_container_width=True, key="g_perm_macro")
                    else:
                        st.info("Sem coluna de macro unidade.")

                cols_t = [c for c in (col_serv, col_cargo, col_cod, col_unidade, col_nom) if c]
                cfg = {col_nom: st.column_config.DateColumn(col_nom, format="DD/MM/YYYY")}
                r1, r2 = st.columns(2)
                with r1:
                    st.markdown("**🆕 Nomeações mais recentes**")
                    st.dataframe(o.sort_values(col_nom, ascending=False).head(15)[cols_t],
                                 use_container_width=True, column_config=cfg)
                with r2:
                    st.markdown("**🏅 Há mais tempo no cargo**")
                    st.dataframe(o.sort_values(col_nom).head(15)[cols_t],
                                 use_container_width=True, column_config=cfg)

painel()