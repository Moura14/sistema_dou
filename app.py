import hashlib
import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from services.leitor_pdf import extrair_texto_pdf
from extracao.portaria import (
    extrair_informacoes,
    sugerir_campo_para_cabecalho,
)
from extracao.por_esquema import (
    extrair_com_ia,
    ia_disponivel,
    resolver_por_regra,
)
from planilhas import esquma as esq


st.set_page_config(
    page_title="Extração de Portarias",
    page_icon="📄",
    layout="wide",
)

st.title("Extração de informações de portarias")
st.write(
    "Envie PDFs do Diário Oficial da União e a planilha a atualizar. "
    "Os campos são definidos pelos cabeçalhos da própria planilha."
)

XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@st.cache_data(show_spinner="Lendo PDF...")
def processar_pdf(conteudo: bytes):
    paginas = extrair_texto_pdf(conteudo)
    texto = "\n".join(p["texto"] for p in paginas)
    registros = extrair_informacoes(texto) if texto.strip() else []
    if isinstance(registros, dict):
        registros = [registros]
    return texto, registros or []


@st.cache_data(show_spinner=False)
def carregar_planilha(conteudo: bytes, aba: str, linha_cab):
    return esq.ler_planilha(conteudo, aba, linha_cab)


@st.cache_data(show_spinner="Consultando a IA nos campos sem correspondência...")
def consultar_ia(texto: str, registro_json: str, pendentes_json: str):
    return extrair_com_ia(
        texto, json.loads(registro_json), json.loads(pendentes_json)
    )


def rotulo(reg: dict, i: int) -> str:
    return (
        f"{reg.get('nome') or '(nome não identificado)'} · "
        f"{reg.get('tipo_ato') or '?'} · "
        f"Portaria {reg.get('numero_portaria') or '?'}"
    )


def hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(df.to_csv(index=False).encode("utf-8")).hexdigest()[:10]


def sincronizar_alteracoes(chave_editor: str, tabela: dict) -> None:
    df = st.session_state["alt_df"]
    edicoes = st.session_state.get(chave_editor, {}).get("edited_rows", {})

    for pos, mudancas in edicoes.items():
        for coluna, valor in mudancas.items():
            df.at[int(pos), coluna] = valor

    for pos in df.index:
        linha = int(df.at[pos, "_linha"])
        if linha == 0:  # linha nova: não há valor atual
            continue
        atual = esq.texto_exibicao(
            tabela.get(linha, {}).get(df.at[pos, "Coluna"])
        )
        df.at[pos, "Atual"] = atual
        df.at[pos, "Tipo"] = "alterar" if atual else "preencher"

    st.session_state["alt_df"] = df
    st.session_state["alt_ver"] += 1


def fluxo_planilha(resultados, textos, arquivo_excel):
    st.divider()
    st.subheader("Atualizar a planilha")

    conteudo = arquivo_excel.getvalue()

    c1, c2 = st.columns([3, 1])
    aba = c1.selectbox("Aba da planilha", esq.listar_abas(conteudo))
    detectada = carregar_planilha(conteudo, aba, None)["linha_cab"]
    linha_cab = int(
        c2.number_input(
            "Linha do cabeçalho",
            min_value=1,
            value=detectada,
            step=1,
            key=f"linha_cab_{aba}",
            help="Detectada automaticamente; corrija se estiver errada.",
        )
    )

    plan = carregar_planilha(conteudo, aba, linha_cab)
    colunas = list(plan["colunas"])
    if not colunas:
        st.error(
            f"Não encontrei cabeçalhos na linha {linha_cab} da aba '{aba}'."
        )
        return

    chave_cfg = esq.chave_planilha(colunas)
    cfg = esq.carregar_config(chave_cfg)

    with st.expander("Campos encontrados na planilha"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Campo": n,
                        "Tipo": plan["tipos"][n],
                        "Exemplos": " | ".join(
                            esq.texto_exibicao(v) for v in plan["exemplos"][n]
                        ),
                    }
                    for n in colunas
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    padrao_chave = [
        c for c in cfg.get("colunas_chave", []) if c in colunas
    ] or esq.sugerir_colunas_chave(colunas)

    colunas_chave = st.multiselect(
        "Como encontrar a linha existente? (coluna-chave)",
        colunas,
        default=padrao_chave,
        key=f"chave_{chave_cfg}",
        help="A portaria atualiza a linha em que estas colunas coincidem.",
    )

    o1, o2 = st.columns(2)
    sobrescrever = o1.toggle(
        "Sobrescrever células já preenchidas",
        value=False,
        help="Desligado: só preenche células vazias. Alterações em células "
        "preenchidas aparecem desmarcadas na revisão.",
    )
    usar_ia = o2.toggle(
        "Usar IA nos campos sem correspondência automática",
        value=ia_disponivel(),
        disabled=not ia_disponivel(),
    )
    if not ia_disponivel():
        st.caption(
            "IA desativada. Para ativar: `pip install anthropic` e defina "
            "a variável de ambiente ANTHROPIC_API_KEY."
        )

    if not colunas_chave:
        st.info("Escolha ao menos uma coluna-chave para continuar.")
        return


    valores_por_reg = []
    for i, reg in enumerate(resultados):
        valores, pendentes = resolver_por_regra(
            reg, colunas, sugerir_campo_para_cabecalho
        )

        if usar_ia and pendentes:
            try:
                ia = consultar_ia(
                    textos[i],
                    json.dumps(reg, ensure_ascii=False, default=str),
                    json.dumps(
                        [
                            {
                                "campo": c,
                                "exemplos": [
                                    esq.texto_exibicao(v)
                                    for v in plan["exemplos"][c]
                                ],
                            }
                            for c in pendentes
                        ],
                        ensure_ascii=False,
                    ),
                )
                for cab, v in ia.items():
                    if v not in (None, ""):
                        valores[cab] = (v, "IA")
            except Exception as erro:
                st.warning(
                    f"IA indisponível para {rotulo(reg, i)}: {erro}"
                )

        valores_por_reg.append(
            {
                cab: (esq.converter_valor(v, plan["tipos"][cab]), origem)
                for cab, (v, origem) in valores.items()
            }
        )

    linhas_match = []
    for i, reg in enumerate(resultados):
        chave_vals = {
            c: valores_por_reg[i].get(c, (None, None))[0]
            for c in colunas_chave
        }
        linha, score, empates = esq.localizar_linha(
            plan["tabela"], colunas_chave, chave_vals
        )
        confianca = f"{score:.0%}" if linha else "não encontrada"
        if linha and empates > 1:
            confianca += f" · {empates} linhas iguais"
        linhas_match.append(
            {
                "_i": i,
                "Portaria": rotulo(reg, i),
                "Linha na planilha": linha,
                "Confiança": confianca,
                "Ação": "Atualizar" if linha else "Ignorar",
            }
        )

    df_match = pd.DataFrame(linhas_match)
    df_match["Linha na planilha"] = df_match["Linha na planilha"].astype(
        "Int64"
    )

    st.markdown("**1. Qual linha cada portaria atualiza**")
    st.caption(
        "Corrija o número da linha se a correspondência estiver errada. "
        "Se a pessoa não existe na planilha, mude a ação para "
        "'Adicionar nova'."
    )
    ed1 = st.data_editor(
        df_match,
        hide_index=True,
        width="stretch",
        key=f"match_{chave_cfg}_{hash_df(df_match)}",
        disabled=["Portaria", "Confiança"],
        column_config={
            "_i": None,
            "Linha na planilha": st.column_config.NumberColumn(
                min_value=linha_cab + 1, step=1, format="%d"
            ),
            "Ação": st.column_config.SelectboxColumn(
                options=["Atualizar", "Adicionar nova", "Ignorar"],
                required=True,
            ),
        },
    )


    alteracoes = []
    for _, m in ed1.iterrows():
        i = int(m["_i"])
        reg = resultados[i]
        valores = valores_por_reg[i]

        if m["Ação"] == "Atualizar" and pd.notna(m["Linha na planilha"]):
            linha = int(m["Linha na planilha"])
            atuais = plan["tabela"].get(linha, {})
            for a in esq.calcular_alteracoes(
                atuais, valores, excluir=colunas_chave
            ):
                alteracoes.append(
                    {
                        "Aplicar": a["tipo"] == "preencher" or sobrescrever,
                        "_i": i,
                        "_linha": linha,
                        "Portaria": rotulo(reg, i),
                        "Linha": str(linha),
                        "Coluna": a["coluna"],
                        "_coluna_orig": a["coluna"],
                        "Atual": esq.texto_exibicao(a["atual"]),
                        "Novo": esq.texto_exibicao(a["novo"]),
                        "Tipo": a["tipo"],
                        "Origem": a["origem"],
                    }
                )

        elif m["Ação"] == "Adicionar nova":
            for cab, (v, origem) in valores.items():
                if v in (None, ""):
                    continue
                alteracoes.append(
                    {
                        "Aplicar": True,
                        "_i": i,
                        "_linha": 0,
                        "Portaria": rotulo(reg, i),
                        "Linha": "nova",
                        "Coluna": cab,
                        "_coluna_orig": cab,
                        "Atual": "",
                        "Novo": esq.texto_exibicao(v),
                        "Tipo": "nova linha",
                        "Origem": origem,
                    }
                )

    st.markdown("**2. O que vai mudar na planilha**")

    if not alteracoes:
        st.info(
            "Nada a alterar: as células já estão iguais, as portarias "
            "foram ignoradas ou nenhum campo da planilha foi reconhecido."
        )
        return

    df_alt = pd.DataFrame(alteracoes)

    assinatura = f"{chave_cfg}_{hash_df(df_alt)}_{int(sobrescrever)}"
    if st.session_state.get("alt_assinatura") != assinatura:
        st.session_state["alt_assinatura"] = assinatura
        st.session_state["alt_df"] = df_alt
        st.session_state["alt_ver"] = 0
    chave_editor = f"alt_{assinatura}_{st.session_state['alt_ver']}"


    opcoes_novo = []
    for reg in resultados:
        for campo, v in reg.items():
            if campo == "arquivo" or v in (None, ""):
                continue
            if isinstance(v, (str, int, float, date, datetime)):
                opcoes_novo.append(esq.texto_exibicao(v).strip())
    opcoes_novo += [v for v in df_alt["Novo"] if v]
    opcoes_novo = [o for o in dict.fromkeys(opcoes_novo) if o]

    st.caption(
        "Desmarque o que não quiser gravar. Em 'Coluna' você escolhe, entre "
        "todas as colunas da planilha, onde a informação será gravada, e em "
        "'Novo', qual informação extraída das portarias será gravada ali. "
        "'Origem' mostra se o valor veio das regras ou da IA (confira os "
        "da IA com mais atenção)."
    )
    ed2 = st.data_editor(
        st.session_state["alt_df"],
        hide_index=True,
        width="stretch",
        key=chave_editor,
        on_change=sincronizar_alteracoes,
        args=(chave_editor, plan["tabela"]),
        disabled=["Portaria", "Linha", "Atual", "Tipo", "Origem"],
        column_config={
            "_i": None,
            "_linha": None,
            "_coluna_orig": None,
            "Coluna": st.column_config.SelectboxColumn(
                options=colunas, required=True
            ),
            "Novo": st.column_config.SelectboxColumn(
                options=opcoes_novo, required=True
            ),
        },
    )

    selecionadas = int(ed2["Aplicar"].sum())
    st.caption(f"{selecionadas} de {len(ed2)} alteração(ões) selecionada(s).")

    sel = ed2[ed2["Aplicar"]]

    dup = sel.duplicated(subset=["_i", "_linha", "Coluna"], keep=False)
    if dup.any():
        st.warning(
            "Mais de uma informação vai para a mesma coluna da mesma "
            "portaria: "
            + "; ".join(sorted(set(sel[dup]["Coluna"])))
            + ". A última da lista prevalece."
        )

    if st.button(
        "Aplicar à planilha",
        type="primary",
        disabled=selecionadas == 0,
    ):
        atualizacoes, novas = [], {}
        for _, a in ed2[ed2["Aplicar"]].iterrows():
            valor = esq.converter_valor(a["Novo"], plan["tipos"][a["Coluna"]])
            if valor is None:
                continue
            if int(a["_linha"]) == 0:
                novas.setdefault(int(a["_i"]), {})[a["Coluna"]] = valor
            else:
                atualizacoes.append(
                    (int(a["_linha"]), a["Coluna"], valor)
                )

        try:
            res = esq.aplicar_alteracoes(
                conteudo,
                aba,
                plan,
                atualizacoes,
                [novas[k] for k in sorted(novas)],
            )
            res["nome"] = arquivo_excel.name.rsplit(".", 1)[0]
            res["origem"] = arquivo_excel.name
            st.session_state["res_esquema"] = res
            esq.salvar_config(chave_cfg, {"colunas_chave": colunas_chave})
        except Exception as erro:
            st.session_state.pop("res_esquema", None)
            st.error(f"Erro ao atualizar a planilha: {erro}")

    res = st.session_state.get("res_esquema")
    if res and res.get("origem") == arquivo_excel.name:
        msg = f"{res['celulas']} célula(s) gravada(s)"
        if res["linhas_novas"]:
            msg += (
                f"; {len(res['linhas_novas'])} linha(s) nova(s) "
                f"({', '.join(map(str, res['linhas_novas']))})"
            )
        st.success(msg + ".")
        for falha in res["falhas"]:
            st.warning(f"Não gravado: {falha}")

        st.download_button(
            "Baixar planilha atualizada",
            data=res["arquivo"],
            file_name=f"{res['nome']}_atualizada.xlsx",
            mime=XLSX_MIME,
        )

arquivos = st.file_uploader(
    "Selecione uma ou mais portarias em PDF",
    type=["pdf"],
    accept_multiple_files=True,
)

arquivo_excel = st.file_uploader(
    "Anexe a planilha que deseja atualizar",
    type=["xlsx"],
    key="planilha",
)

if arquivos:
    resultados, textos = [], []

    for arquivo in arquivos:
        st.divider()
        st.subheader(arquivo.name)

        try:
            texto, registros = processar_pdf(arquivo.getvalue())

            if not texto.strip():
                st.warning(
                    "Não foi possível extrair texto deste PDF. "
                    "Ele pode precisar de OCR."
                )
                continue

            with st.expander("Conferir texto original extraído"):
                st.text(texto)

            if not registros:
                st.warning("Nenhuma portaria foi identificada.")
                continue

            for registro in registros:
                registro["arquivo"] = arquivo.name
                resultados.append(registro)
                textos.append(texto)

        except Exception as erro:
            st.error(f"Erro ao processar {arquivo.name}: {erro}")

    if resultados:
        st.divider()
        st.subheader("Resumo dos documentos")

        df = pd.DataFrame(resultados)
        st.dataframe(df, width="stretch")

        st.download_button(
            "Baixar resultado em CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="informacoes_portarias.csv",
            mime="text/csv",
        )

        if arquivo_excel is not None:
            fluxo_planilha(resultados, textos, arquivo_excel)