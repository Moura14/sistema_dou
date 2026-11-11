import hashlib
import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from services.leitor_pdf import extrair_texto_pdf
from planilhas.esquema import (
    texto_exibicao,
    normalizar,
    converter_valor,
    valor_vazio,
)
from extracao.portaria import (
    extrair_informacoes,
    sugerir_campo_para_cabecalho,
)
from extracao.por_esquema import (
    extrair_com_ia,
    ia_disponivel,
    resolver_por_regra,
)
from planilhas.leitura import (
    listar_abas,
    ler_planilha,
)

from planilhas.correspondencia import (
    sugerir_colunas_chave,
    localizar_linha,
)

from planilhas.alteracoes import (
    aplicar_alteracoes,
)

from planilhas.configuracoes import (
    chave_planilha,
    carregar_config,
    salvar_config,
)


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
def carregar_planilha(conteudo, aba, linha_cab):
    return ler_planilha(conteudo, aba, linha_cab)


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


def sincronizar_alteracoes(
    chave_editor: str, tabela: dict, indices: list[int]
) -> None:
    df = st.session_state["alt_df"]
    edicoes = st.session_state.get(chave_editor, {}).get("edited_rows", {})

    for pos, mudancas in edicoes.items():
        indice_df = indices[int(pos)]
        for coluna, valor in mudancas.items():
            df.at[indice_df, coluna] = valor

        if "Novo" in mudancas or "Novo manual" in mudancas:
            manual = df.at[indice_df, "Novo manual"]
            novo = (
                manual
                if not valor_vazio(manual)
                else df.at[indice_df, "Novo"]
            )
            df.at[indice_df, "Aplicar"] = not valor_vazio(novo)

    for pos in df.index:
        linha = int(df.at[pos, "_linha"])
        manual = df.at[pos, "Novo manual"]
        novo = manual if not valor_vazio(manual) else df.at[pos, "Novo"]
        if linha == 0:  # linha nova: não há valor atual
            df.at[pos, "Tipo"] = (
                "nova linha" if not valor_vazio(novo) else "sem informação"
            )
            continue
        atual = texto_exibicao(
            tabela.get(linha, {}).get(df.at[pos, "Coluna"])
        )
        novo = texto_exibicao(novo)
        df.at[pos, "Atual"] = atual
        if not novo:
            df.at[pos, "Tipo"] = "sem informação"
        elif normalizar(atual) == normalizar(novo):
            df.at[pos, "Tipo"] = "sem alteração"
        else:
            df.at[pos, "Tipo"] = "alterar" if atual else "preencher"

    st.session_state["alt_df"] = df
    st.session_state["alt_ver"] += 1


def fluxo_planilha(resultados, textos, arquivo_excel):
    st.divider()
    st.subheader("Atualizar a planilha")

    conteudo = arquivo_excel.getvalue()

    aba = st.selectbox("Aba da planilha", listar_abas(conteudo))
    plan = carregar_planilha(conteudo, aba, None)
    linha_cab = plan["linha_cab"]
    colunas = list(plan["colunas"])
    if not colunas:
        st.error(
            f"Não encontrei cabeçalhos na linha {linha_cab} da aba '{aba}'."
        )
        return

    chave_cfg = chave_planilha(colunas)
    cfg = carregar_config(chave_cfg)

    with st.expander("Campos encontrados na planilha"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Campo": n,
                        "Tipo": plan["tipos"][n],
                        "Exemplos": " | ".join(
                            texto_exibicao(v) for v in plan["exemplos"][n]
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
    ] or sugerir_colunas_chave(colunas)
    colunas_chave = padrao_chave


    valores_por_reg = []
    for i, reg in enumerate(resultados):
        valores, pendentes = resolver_por_regra(
            reg, colunas, sugerir_campo_para_cabecalho
        )

        valores_por_reg.append(
            {
                cab: (converter_valor(v, plan["tipos"][cab]), origem)
                for cab, (v, origem) in valores.items()
            }
        )

    linhas_match = []
    for i, reg in enumerate(resultados):
        chave_vals = {
            c: valores_por_reg[i].get(c, (None, None))[0]
            for c in colunas_chave
        }
        linha, score, empates = localizar_linha(
            plan["tabela"], colunas_chave, chave_vals
        )
        linhas_match.append(
            {
                "_i": i,
                "Portaria": rotulo(reg, i),
                "Linha na planilha": linha,
                "Ação": "Atualizar" if linha else "Ignorar",
            }
        )

    df_match = pd.DataFrame(linhas_match)
    df_match["Linha na planilha"] = df_match["Linha na planilha"].astype(
        "Int64"
    )

    st.markdown("**1. Qual linha cada portaria atualiza**")
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

        if m["Ação"] == "Atualizar" and pd.notna(m["Linha na planilha"]):
            linha = int(m["Linha na planilha"])
            atuais = plan["tabela"].get(linha, {})
            for cab in colunas:
                alteracoes.append(
                    {
                        "Aplicar": False,
                        "_i": i,
                        "_linha": linha,
                        "Portaria": rotulo(reg, i),
                        "Linha": str(linha),
                        "Coluna": cab,
                        "_coluna_orig": cab,
                        "Atual": texto_exibicao(atuais.get(cab)),
                        "Novo": "",
                        "Novo manual": "",
                        "Tipo": (
                            "chave"
                            if cab in colunas_chave
                            else "sem informação"
                        ),
                    }
                )
        elif m["Ação"] == "Adicionar nova":
            for cab in colunas:
                alteracoes.append(
                    {
                        "Aplicar": False,
                        "_i": i,
                        "_linha": 0,
                        "Portaria": rotulo(reg, i),
                        "Linha": "nova",
                        "Coluna": cab,
                        "_coluna_orig": cab,
                        "Atual": "",
                        "Novo": "",
                        "Novo manual": "",
                        "Tipo": "sem informação",
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

    assinatura = f"{chave_cfg}_{hash_df(df_alt)}"
    if st.session_state.get("alt_assinatura") != assinatura:
        st.session_state["alt_assinatura"] = assinatura
        st.session_state["alt_df"] = df_alt
        st.session_state["alt_ver"] = 0
    portarias_alteracoes = list(
        st.session_state["alt_df"]["Portaria"].drop_duplicates()
    )
    portaria_selecionada = st.selectbox(
        "Portaria para editar",
        portarias_alteracoes,
        key=f"filtro_alteracoes_{assinatura}",
    )
    df_completo = st.session_state["alt_df"]
    indices = list(
        df_completo.index[
            df_completo["Portaria"] == portaria_selecionada
        ]
    )
    df_portaria = df_completo.loc[indices]
    registros_portaria = [
        resultados[int(i)]
        for i in df_portaria["_i"].drop_duplicates()
    ]

    opcoes_novo = []
    for reg in registros_portaria:
        for campo, v in reg.items():
            if campo == "arquivo" or valor_vazio(v):
                continue
            if isinstance(v, (str, int, float, date, datetime)):
                opcoes_novo.append(texto_exibicao(v).strip())
    opcoes_novo += [
        v for v in df_portaria["Novo"] if not valor_vazio(v)
    ]
    opcoes_novo = [""] + [
        o for o in dict.fromkeys(opcoes_novo) if o
    ]

    chave_editor_base = (
        f"alt_{assinatura}_{st.session_state['alt_ver']}_"
        f"{hashlib.md5(portaria_selecionada.encode('utf-8')).hexdigest()[:8]}"
    )

    editores = []
    linhas_existentes = df_portaria[df_portaria["_linha"] != 0]
    indices_existentes = list(linhas_existentes.index)
    if not linhas_existentes.empty:
        st.markdown("**Atualizar linha existente**")
        chave_editor = f"{chave_editor_base}_atualizar"
        editores.append(
            st.data_editor(
                linhas_existentes.reset_index(drop=True),
                hide_index=True,
                width="stretch",
                key=chave_editor,
                on_change=sincronizar_alteracoes,
                args=(chave_editor, plan["tabela"], indices_existentes),
                disabled=[
                    "Portaria",
                    "Linha",
                    "Coluna",
                    "Atual",
                    "Tipo",
                    "_i",
                    "_linha",
                    "_coluna_orig",
                ],
                column_config={
                    "_i": None,
                    "_linha": None,
                    "_coluna_orig": None,
                    "Tipo": None,
                    "Novo": st.column_config.SelectboxColumn(
                        options=opcoes_novo, required=False, width=250
                    ),
                    "Novo manual": st.column_config.TextColumn(
                        help=(
                            "Digite aqui um valor personalizado. "
                            "Se preenchido, ele substitui a opção do dropdown."
                        )
                    ),
                },
            ),
        )

    linhas_novas = df_portaria[df_portaria["_linha"] == 0].drop(
        columns=["Atual"]
    )
    indices_novas = list(linhas_novas.index)
    if not linhas_novas.empty:
        st.markdown("**Adicionar nova linha**")
        chave_editor = f"{chave_editor_base}_nova"
        editores.append(
            st.data_editor(
                linhas_novas.reset_index(drop=True),
                hide_index=True,
                width="stretch",
                key=chave_editor,
                on_change=sincronizar_alteracoes,
                args=(chave_editor, plan["tabela"], indices_novas),
                disabled=[
                    "Portaria",
                    "Linha",
                    "Coluna",
                    "Tipo",
                    "_i",
                    "_linha",
                    "_coluna_orig",
                ],
                column_config={
                    "_i": None,
                    "_linha": None,
                    "_coluna_orig": None,
                    "Tipo": None,
                    "Novo": st.column_config.SelectboxColumn(
                        options=opcoes_novo, required=False, width=250
                    ),
                    "Novo manual": st.column_config.TextColumn(
                        help=(
                            "Digite aqui um valor personalizado. "
                            "Se preenchido, ele substitui a opção do dropdown."
                        )
                    ),
                },
            )
        )

    ed2 = pd.concat(editores, ignore_index=True)

    selecionadas = int(ed2["Aplicar"].sum())
    st.caption(
        f"{selecionadas} de {len(ed2)} alteração(ões) selecionada(s). "
        "Se preencher “Novo manual”, esse valor será usado no lugar do dropdown."
    )

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
            if (
                int(a["_linha"]) != 0
                and a["Coluna"] in colunas_chave
            ):
                continue
            valor_digitado = a["Novo manual"]
            valor_escolhido = (
                valor_digitado
                if not valor_vazio(valor_digitado)
                else a["Novo"]
            )
            valor = converter_valor(
                valor_escolhido, plan["tipos"][a["Coluna"]]
            )
            if valor is None:
                continue
            if int(a["_linha"]) == 0:
                novas.setdefault(int(a["_i"]), {})[a["Coluna"]] = valor
            else:
                atualizacoes.append(
                    (int(a["_linha"]), a["Coluna"], valor)
                )

        try:
            res = aplicar_alteracoes(
                conteudo,
                aba,
                plan,
                atualizacoes,
                [novas[k] for k in sorted(novas)],
            )
            res["nome"] = arquivo_excel.name.rsplit(".", 1)[0]
            res["origem"] = arquivo_excel.name
            st.session_state["res_esquema"] = res
            salvar_config(chave_cfg, {"colunas_chave": colunas_chave})
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


def exibir_resumo_documentos(resultados):
    st.divider()
    st.subheader("Resumo dos documentos")

    documentos = {}

    for registro in resultados:
        arquivo = registro.get("arquivo", "Documento sem nome")
        documentos.setdefault(arquivo, []).append(registro)

    total_registros = len(resultados)
    total_documentos = len(documentos)

    registros_incompletos = sum(
        1 for r in resultados
        if valor_vazio(r.get("nome"))
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Documentos processados", total_documentos)
    c2.metric("Registros extraídos", total_registros)
    c3.metric("Registros sem nome", registros_incompletos)

    st.divider()


    col1, col2 = st.columns([2, 1])
    busca = col1.text_input(
        "Pesquisar servidor",
        placeholder="Digite o nome do servidor...",
    )


    tipos_disponiveis = sorted({
        str(r.get("tipo_ato"))
        for r in resultados
        if not valor_vazio(r.get("tipo_ato"))
    })

    filtro_tipo = col2.selectbox(
        "Tipo de ato",
        ["Todos"] + tipos_disponiveis
    )


    resultados_filtrados = []

    for registro in resultados:
        nome = str(registro.get("nome") or "").lower()
        tipo = str(registro.get("tipo_ato") or "")

        if busca and busca.lower() not in nome:
            continue

        if filtro_tipo != "Todos" and tipo != filtro_tipo:
            continue

        resultados_filtrados.append(registro)

    st.caption(
        f"Exibindo {len(resultados_filtrados)} de "
        f"{total_registros} registros."
    )

  
    for arquivo, registros in documentos.items():

        registros_doc = [
            r for r in resultados_filtrados
            if r.get("arquivo", "Documento sem nome") == arquivo
        ]

        if not registros_doc:
            continue

        with st.expander(
            f"📄 {arquivo} · {len(registros_doc)} registro(s)",
            expanded=True
        ):
            st.markdown("**Registros identificados**")

            for indice, registro in enumerate(registros_doc, start=1):

                nome = registro.get("nome") or "Nome não identificado"
                tipo = registro.get("tipo_ato") or "Tipo não identificado"

                with st.container(border=True):

    
                    col_nome, col_tipo = st.columns([3, 1])

                    col_nome.markdown(f"**{nome}**")
                    col_tipo.caption(tipo)

                    st.divider()

                    campos = [
                        ("Novo cargo", "novo_cargo"),
                        ("Cargo / função", "cargo"),
                        ("Encargo", "encargo"),
                        ("Código CCE/FCE", "codigos_cargo"),
                        ("Data de efeito", "data_efeito"),
                        ("Portaria referida", "portaria_referida"),
                        ("CPF", "cpf"),
                        ("Matrícula SIAPE", "siape"),
                    ]

                    campos_exibidos = []

                    for rotulo, chave in campos:
                        valor = registro.get(chave)

                        if not valor_vazio(valor):
                            campos_exibidos.append(
                                (rotulo, texto_exibicao(valor))
                            )

                    if not campos_exibidos:
                        st.caption("Nenhum detalhe adicional identificado.")
                    else:
                        colunas = st.columns(2)

                        for i, (rotulo, valor) in enumerate(campos_exibidos):
                            with colunas[i % 2]:
                                st.caption(rotulo)
                                st.write(valor)

                
                    campos_principais = {
                        "arquivo",
                        "nome",
                        "cpf",
                        "orgao",
                        "ministerio",
                        "tipo_ato",
                        "novo_cargo",
                        "cargo",
                        "encargo",
                        "codigos_cargo",
                        "data_efeito",
                        "portaria_referida",
                        "data_publicacao",
                    }

                    outros = {
                        chave: texto_exibicao(valor)
                        for chave, valor in registro.items()
                        if chave not in campos_principais
                        and not valor_vazio(valor)
                    }

                    if outros:
                        with st.expander("Ver outras informações"):
                            for chave, valor in outros.items():
                                st.markdown(
                                    f"**{chave.replace('_', ' ').title()}:** "
                                    f"{valor}"
                                )

            with st.expander("Visualizar registros em tabela"):
                df_doc = pd.DataFrame(registros_doc).drop(
                    columns=[
                        "arquivo",
                        "data_publicacao",
                        "orgao",
                        "ministerio",
                    ],
                    errors="ignore"
                )

                df_doc = df_doc.rename(
                    columns={"codigos_cargo": "Código CCE/FCE"}
                )

                st.dataframe(
                    df_doc,
                    width="stretch",
                    hide_index=True
                )


resultados, textos = [], []

if arquivos:

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
    exibir_resumo_documentos(resultados)

    if arquivo_excel is not None:
        fluxo_planilha(resultados, textos, arquivo_excel)