from datetime import datetime
from functools import partial
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
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
PALETA = ["#4F8BF9", "#7C5CFC", "#2FBF9B", "#F5A524", "#F0527A",
          "#38BDF8", "#A3E635", "#FB923C", "#94A3B8"]
COR_SITUACAO = {"Ocupado": "#2FBF9B", "Vago": "#F0527A"}
INTERVALO_ATUALIZACAO = 30  # segundos

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
        background: linear-gradient(120deg, #1f4e9c 0%, #4F8BF9 60%, #7C5CFC 100%);
        color: white; padding: 22px 28px; border-radius: 16px;
        margin-bottom: 18px;
        box-shadow: 0 6px 18px rgba(79,139,249,.25);
    }
    .hero h1 {margin: 0; font-size: 1.9rem; color: white;}
    .hero p {margin: 6px 0 0 0; opacity: .92;}
    .chip {
        display: inline-block; background: rgba(255,255,255,.18);
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


def grafico_categoria(df, col, tipo, topn, height=300):
    cont = contagem_com_outros(df[col], col, topn)

    if tipo == "Pizza":
        fig = px.pie(cont, names="Rótulo", values="Quantidade", hole=0.58,
                     hover_data={col: True}, color_discrete_sequence=PALETA)
        fig.update_traces(textinfo="percent", textposition="inside",
                          hovertemplate="%{label}: <b>%{value}</b> (%{percent})<extra></extra>")
        fig.add_annotation(text=f"<b>{int(cont['Quantidade'].sum())}</b>",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=24))
        fig.update_layout(legend=dict(orientation="h", y=-0.05, font=dict(size=11)))
    elif tipo == "Treemap":
        fig = px.treemap(cont, path=["Rótulo"], values="Quantidade",
                         hover_data={col: True})
        fig.update_traces(textinfo="label+value")
        fig.update_layout(treemapcolorway=PALETA)
    else:
        fig = px.bar(cont, x="Quantidade", y="Rótulo", orientation="h",
                     text="Quantidade", hover_data={col: True, "Rótulo": False})
        fig.update_traces(marker_color=COR, textposition="outside",
                          cliponaxis=False,
                          hovertemplate="%{customdata[0]}: <b>%{x}</b><extra></extra>")
        fig.update_layout(
            yaxis={"categoryorder": "total ascending", "title": None},
            xaxis={"title": None, "showgrid": False},
        )

    fig.update_layout(height=height, margin=dict(l=0, r=10, t=10, b=0))
    return fig


def grafico_empilhado(df, col, topn, height=380):
    """Barras empilhadas: ocupados x vagos por categoria."""
    top = df[col].dropna().astype(str).value_counts().head(topn).index
    base = df[df[col].astype(str).isin(top)].copy()
    base[col] = base[col].astype(str)
    base["Rótulo"] = base[col].map(encurtar)
    cont = base.groupby(["Rótulo", "Situação"]).size().reset_index(name="Quantidade")
    fig = px.bar(cont, x="Quantidade", y="Rótulo", color="Situação",
                 orientation="h", color_discrete_map=COR_SITUACAO, barmode="stack",
                 text="Quantidade")
    fig.update_traces(hovertemplate="%{y} · %{fullData.name}: <b>%{x}</b><extra></extra>")
    fig.update_layout(
        height=height, margin=dict(l=0, r=10, t=10, b=0),
        yaxis={"categoryorder": "total ascending", "title": None},
        xaxis={"title": None, "showgrid": False},
        legend=dict(orientation="h", y=1.08, title=None),
    )
    return fig


def _clique(col: str, key: str):
    """Callback do on_select: copia a seleção do gráfico para o filtro da sidebar."""
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


def mostrar_grafico(df, col, tipo, topn, key, height=300):
    fig = grafico_categoria(df, col, tipo, topn, height=height)
    if tipo == "Barras":
        st.plotly_chart(
            fig, use_container_width=True, key=key,
            on_select=partial(_clique, col, key), selection_mode="points",
        )
    else:
        st.plotly_chart(fig, use_container_width=True, key=key)


def limpar_filtros():
    for k in list(st.session_state.keys()):
        if k.startswith(("f_", "g_")) or k == "busca":
            del st.session_state[k]



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
        and relevante(c)  # ignora Observações, Nome etc.
        and 2 <= base[c].nunique() <= MAX_CATEGORIAS
    ]
   
    cols_graf = [c for c in categoricas if c != "Situação"] or categoricas
    principais = [c for c in cols_graf if c != "Tipo de função"] or cols_graf


    df = base
    total_bruto = len(base)
    with st.sidebar:
        st.header("🔎 Filtros")
        st.text_input("Buscar em qualquer coluna", key="busca", placeholder="Ex.: nome, cargo…")

        def filtro(c):
            nonlocal df
            # opções vêm da base completa, para a seleção nunca ficar inválida
            opcoes = sorted(base[c].dropna().astype(str).unique())
            escolha = st.multiselect(c, opcoes, key=f"f_{c}", placeholder="Todos")
            if escolha:
                df = df[df[c].astype(str).isin(escolha)]

        if categoricas:
            st.markdown("**Filtrar por categoria**")
            for c in categoricas[:4]:
                filtro(c)
            if len(categoricas) > 4:
                with st.expander(f"Mais filtros ({len(categoricas) - 4})"):
                    for c in categoricas[4:]:
                        filtro(c)

    busca = st.session_state.get("busca", "")
    if busca:
        mask = df.astype(str).apply(
            lambda col: col.str.contains(busca, case=False, na=False, regex=False)
        ).any(axis=1)
        df = df[mask]

    with st.sidebar:
        st.divider()
        st.button("🧹 Limpar todos os filtros", on_click=limpar_filtros,
                  use_container_width=True)
        st.caption(f"**{len(df)}** de **{total_bruto}** linhas exibidas")
        st.caption(f"🔄 Atualização automática a cada {INTERVALO_ATUALIZACAO}s")

    if df.empty:
        st.warning("Nenhuma linha com os filtros atuais. Use o botão **Limpar todos os filtros** na barra lateral.")
        return

    ocup = df[df["Situação"] == "Ocupado"] if "Situação" in df.columns else df
    rel = [c for c in df.columns if relevante(c)]
    vagos = len(df) - len(ocup)

    k1, k2, k3, k4 = st.columns(4)
    with k1, st.container(border=True):
        st.metric("Cargos e funções", len(df))
    with k2, st.container(border=True):
        st.metric("Ocupados", len(ocup),
                  delta=f"{len(ocup) / len(df):.0%} do total", delta_color="off")
    with k3, st.container(border=True):
        st.metric("Vagos", vagos,
                  delta=f"{vagos / len(df):.0%} do total", delta_color="off")
    with k4, st.container(border=True):
        st.metric(
            "Dados completos (ocupados)",
            f"{ocup[rel].notna().mean().mean():.0%}" if rel and len(ocup) else "—",
            help="Média do preenchimento das colunas relevantes entre os cargos ocupados.",
        )

    st.write("")
    tab1, tab2, tab3 = st.tabs(["📈 Visão geral", "🗓️ Linha do tempo", "📋 Dados"])

    with tab1:
        if not cols_graf:
            st.info("Não há colunas categóricas suficientes para gráficos.")
        else:
            col_principal = principais[0]
            if "Tipo de função" in cols_graf and col_principal != "Tipo de função":
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
                    mostrar_grafico(df, col_secundaria, "Rosca", 8, "g_secundaria")
                else:
                    st.info("Poucas colunas para exibir gráficos secundários.")
            with g3, st.container(border=True):
                if "Situação" in df.columns:
                    st.markdown("**Status: Ocupação**")
                    mostrar_grafico(df, "Situação", "Rosca", 2, "g_status")
                elif "Tipo de função" in df.columns:
                    st.markdown("**Tipo de função**")
                    mostrar_grafico(df, "Tipo de função", "Rosca", 5, "g_tipo")
                else:
                    st.info("Sem dados de status.")

            st.markdown("### 🧭 Explorar")
            with st.container(border=True):
                e1, e2, e3 = st.columns([2, 2, 1])
                col = e1.selectbox("Analisar por", cols_graf, key="g_exp_col")
                opcoes_tipo = ["Barras", "Rosca", "Treemap"]
                if "Situação" in df.columns:
                    opcoes_tipo.append("Ocupação (empilhado)")
                tipo = e2.radio("Tipo de gráfico", opcoes_tipo, horizontal=True, key="g_exp_tipo")
                topn = e3.slider("Top N", 3, 20, 10, key="g_exp_topn")
                if tipo == "Ocupação (empilhado)":
                    st.plotly_chart(grafico_empilhado(df, col, topn), use_container_width=True,
                                    key="g_exp_emp")
                else:
                    mostrar_grafico(df, col, tipo, topn, f"g_exp_{tipo}", height=380)

    with tab2:
        datas = [c for c in base.columns if pd.api.types.is_datetime64_any_dtype(base[c])
                 and base[c].notna().any()]
        if not datas:
            st.info("Esta aba não possui colunas de data reconhecidas.")
        else:
            t1, t2, t3 = st.columns([2, 1, 1])
            col_data = t1.selectbox("Coluna de data", datas, key="f_col_data")
            gran = t2.radio("Agrupar por", ["Mês", "Ano"], horizontal=True, key="f_gran")
            acum = t3.toggle("Acumulado", key="f_acum")

            lo = base[col_data].min().date()
            hi = base[col_data].max().date()
            if lo < hi:
                ini, fim = st.slider("Período", lo, hi, (lo, hi),
                                     format="DD/MM/YYYY", key=f"f_periodo_{col_data}")
            else:
                ini, fim = lo, hi

            s = df[col_data].dropna()
            s = s[(s.dt.date >= ini) & (s.dt.date <= fim)]
            if s.empty:
                st.warning("Nenhum registro no período selecionado.")
            else:
                freq = "M" if gran == "Mês" else "Y"
                serie = (s.dt.to_period(freq).dt.to_timestamp().value_counts()
                         .sort_index().rename_axis("Período").reset_index(name="Quantidade"))
                if acum:
                    serie["Quantidade"] = serie["Quantidade"].cumsum()

                m1, m2, m3 = st.columns(3)
                m1.metric("Registros no período", len(s))
                m2.metric("Primeiro", f"{s.min():%d/%m/%Y}")
                m3.metric("Mais recente", f"{s.max():%d/%m/%Y}")

                with st.container(border=True):
                    fig = px.area(serie, x="Período", y="Quantidade", markers=True,
                                  color_discrete_sequence=[COR])
                    fig.update_traces(
                        line_shape="spline" if len(serie) > 2 else "linear",
                        hovertemplate=("%{x|%b/%Y}" if gran == "Mês" else "%{x|%Y}")
                        + ": <b>%{y}</b><extra></extra>",
                    )
                    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0),
                                      xaxis_title=None, yaxis_title=None,
                                      xaxis=dict(rangeslider=dict(visible=True)))
                    st.plotly_chart(fig, use_container_width=True, key="g_timeline")

    with tab3:
        escolhidas = st.multiselect(
            "Colunas exibidas", list(df.columns), default=list(df.columns),
            key=f"g_cols_{aba}",
        )
        vis = df[escolhidas] if escolhidas else df
        config = {
            c: st.column_config.DateColumn(c, format="DD/MM/YYYY")
            for c in vis.columns if pd.api.types.is_datetime64_any_dtype(vis[c])
        }
        st.dataframe(vis, use_container_width=True, height=480, column_config=config)
        st.download_button(
            "⬇️ Baixar dados filtrados (CSV)",
            vis.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"dados_filtrados_{aba}.csv",
            mime="text/csv",
        )


painel()