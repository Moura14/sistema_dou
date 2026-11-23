from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import re
from datetime import datetime
import hashlib

from planilhas.leitura import listar_abas, ler_planilha

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

ARQ = (
    Path(__file__).resolve().parent.parent
    / "dados_compartilhados"
    / "planilha_atual.xlsx"
)

MAX_CATEGORIAS = 25
COR = "#4F8BF9"

SEM_INTERESSE_CONTEM = ("siorg", "uorg", "sigla", "logradouro",
                        "complemento", "munic", "telefone", "mail")
SEM_INTERESSE_EXATAS = {"uf", "cep"}
OPCIONAL_CONTEM = ("observ", "substituto", "processo.1", "processo (2)", "processo_2")
OPCIONAL_EXATAS = {"nome"}
COLUNAS_DATA = ("nomea", "data", "posse")


def sem_interesse(c: str) -> bool:
    lc = c.lower()
    return lc in SEM_INTERESSE_EXATAS or any(k in lc for k in SEM_INTERESSE_CONTEM)


def relevante(c: str) -> bool:
    lc = c.lower()
    return (not sem_interesse(c) and lc not in OPCIONAL_EXATAS
            and not any(k in lc for k in OPCIONAL_CONTEM))


def parse_data(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return pd.NaT
    if isinstance(v, datetime):
        return pd.Timestamp(v)
    s = str(v).strip()
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:
        d, mo, a = map(int, m.groups())
        try:
            return pd.Timestamp(a, mo, d)
        except ValueError:
            return pd.NaT
    if re.fullmatch(r"\d{5}(\.0+)?", s):
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(s)))
    return pd.NaT


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    df = df.dropna(axis=1, how="all")

    for c in df.columns:
        if any(k in c.lower() for k in COLUNAS_DATA):
            conv = df[c].map(parse_data)
            if conv.notna().sum() >= 0.5 * df[c].notna().sum():
                df[c] = pd.to_datetime(conv)

    col_serv = next((c for c in df.columns if c.lower().startswith("servidor")), None)
    if col_serv:
        df["Situação"] = (
            df[col_serv].astype(str).str.strip().str.upper().eq("VAGO")
            .map({True: "Vago", False: "Ocupado"})
        )
    col_cod = next((c for c in df.columns
                    if "fce" in c.lower() and "cce" in c.lower()), None)
    if col_cod:
        df["Tipo de função"] = (
            df[col_cod].astype(str).str.extract(r"^\s*(CCE|FCE)", flags=re.I)[0]
            .str.upper()
        )
    return df


st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem;}
    .hero {
        background: linear-gradient(120deg, #1f4e9c 0%, #4F8BF9 100%);
        color: white; padding: 22px 28px; border-radius: 16px;
        margin-bottom: 18px;
    }
    .hero h1 {margin: 0; font-size: 1.9rem; color: white;}
    .hero p {margin: 4px 0 0 0; opacity: .9;}
    /* Estilo para os cartões do dashboard */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(128,128,128,.04);
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetric"] {
        background: transparent;
        border: none;
        padding: 0;
    }
    div[data-testid="stMetricValue"] {font-size: 1.8rem;}
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


def grafico_categoria(df, col, tipo, topn, height=280):
    cont = contagem_com_outros(df[col], col, topn)

    if tipo == "Rosca":
        fig = px.pie(cont, names="Rótulo", values="Quantidade", hole=0.55,
                     hover_data={col: True})
        fig.update_traces(textinfo="percent", textposition="inside")
    elif tipo == "Treemap":
        fig = px.treemap(cont, path=["Rótulo"], values="Quantidade",
                         hover_data={col: True})
        fig.update_traces(textinfo="label+value")
    else:
        fig = px.bar(cont, x="Quantidade", y="Rótulo", orientation="h",
                     text="Quantidade", hover_data={col: True, "Rótulo": False})
        fig.update_traces(marker_color=COR, textposition="outside",
                          cliponaxis=False)
        fig.update_layout(
            yaxis={"categoryorder": "total ascending", "title": None},
            xaxis={"title": None, "showgrid": False},
        )

    fig.update_layout(height=height, margin=dict(l=0, r=10, t=10, b=0))
    return fig


def limpar_filtros():
    for k in list(st.session_state.keys()):
        if k.startswith("f_") or k in {"busca", "col_data", "periodo"}:
            del st.session_state[k]


@st.fragment(run_every=10)
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

    aba = st.sidebar.selectbox("Aba", abas) if len(abas) > 1 else abas[0]

    try:
        df = carregar(mtime, aba).copy()
        df = preparar(df)
    except Exception:
        st.error("Não foi possível carregar os dados desta aba. Tente outra aba.")
        return

    if df.empty:
        st.warning("A aba selecionada não tem dados.")
        return

    atualizado = pd.Timestamp(mtime, unit="s", tz="UTC").tz_convert("America/Sao_Paulo")
    st.markdown(
        f"""<div class="hero"><h1>📊 Painel da planilha</h1>
        <p>Aba <b>{aba}</b> · atualizada em {atualizado:%d/%m/%Y às %H:%M:%S}</p></div>""",
        unsafe_allow_html=True,
    )

   
    categoricas = [
        c for c in df.columns
        if not pd.api.types.is_datetime64_any_dtype(df[c]) 
        and not sem_interesse(c)
        and 2 <= df[c].nunique() <= MAX_CATEGORIAS
    ]


    total_bruto = len(df)
    with st.sidebar:
        st.header("🔎 Filtros")
        st.text_input("Buscar em qualquer coluna", key="busca", placeholder="Ex.: nome, cargo…")

        if categoricas:
            st.markdown("**Filtrar por categoria**")
            for c in categoricas[:4]:
                opcoes = sorted(df[c].dropna().astype(str).unique())
                escolha = st.multiselect(c, opcoes, key=f"f_{c}", placeholder="Todos")
                if escolha:
                    df = df[df[c].astype(str).isin(escolha)]
            if len(categoricas) > 4:
                with st.expander(f"Mais filtros ({len(categoricas) - 4})"):
                    for c in categoricas[4:]:
                        opcoes = sorted(df[c].dropna().astype(str).unique())
                        escolha = st.multiselect(c, opcoes, key=f"f_{c}", placeholder="Todos")
                        if escolha:
                            df = df[df[c].astype(str).isin(escolha)]

        st.divider()
        st.button("🧹 Limpar todos os filtros", on_click=limpar_filtros, use_container_width=True)
        st.caption(f"**{len(df)}** de **{total_bruto}** linhas exibidas")

    busca = st.session_state.get("busca", "")
    if busca:
        mask = df.astype(str).apply(lambda col: col.str.contains(busca, case=False, na=False)).any(axis=1)
        df = df[mask]
        st.caption(f"{len(df)} linha(s) encontrada(s) para “{busca}”.")

    if df.empty:
        st.warning("Nenhuma linha com os filtros atuais. Use o botão **Limpar todos os filtros** na barra lateral.")
        return

    ocup = df[df["Situação"] == "Ocupado"] if "Situação" in df.columns else df
    rel = [c for c in df.columns if relevante(c)]

   

    st.markdown("### Resumo Geral")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        with st.container(border=True):
            st.metric("Cargos e funções", len(df))
    with k2:
        with st.container(border=True):
            st.metric("Ocupados", len(ocup))
    with k3:
        with st.container(border=True):
            st.metric("Vagos", len(df) - len(ocup))
    with k4:
        with st.container(border=True):
            st.metric(
                "Dados completos (ocupados)",
                f"{ocup[rel].notna().mean().mean():.0%}" if rel and len(ocup) else "—",
                help="Média do preenchimento das colunas relevantes entre os cargos ocupados.",
            )

    st.markdown("---")

   
    if categoricas:
        col_principal = categoricas[0]
        col_secundaria = categoricas[1] if len(categoricas) > 1 else None
        
        g1, g2, g3 = st.columns([1.5, 1.5, 1])
        
        with g1:
            with st.container(border=True):
                st.markdown(f"**Distribuição: {col_principal}**")
                st.plotly_chart(
                    grafico_categoria(df, col_principal, "Barras", 8, height=300), 
                    use_container_width=True
                )
        
        with g2:
            with st.container(border=True):
                if col_secundaria:
                    st.markdown(f"**Distribuição: {col_secundaria}**")
                    st.plotly_chart(
                        grafico_categoria(df, col_secundaria, "Rosca", 8, height=300), 
                        use_container_width=True
                    )
                else:
                    st.info("Poucas colunas para exibir gráficos secundários.")

        with g3:
            with st.container(border=True):
                if "Situação" in df.columns:
                    st.markdown("**Status: Ocupação**")
                    st.plotly_chart(
                        grafico_categoria(df, "Situação", "Rosca", 2, height=300), 
                        use_container_width=True
                    )
                elif "Tipo de função" in df.columns:
                    st.markdown("**Tipo de função**")
                    st.plotly_chart(
                        grafico_categoria(df, "Tipo de função", "Rosca", 5, height=300), 
                        use_container_width=True
                    )
                else:
                    st.info("Sem dados de status.")

painel()