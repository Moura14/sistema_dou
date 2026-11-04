
from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st

from services.leitor_pdf import extrair_texto_pdf
from extracao.portaria import (
    extrair_informacoes,
    sugerir_campo_para_cabecalho,
)

from planilhas.gravador_excel import (
    enviar_para_planilha_em_memoria,
    listar_abas,
    obter_cabecalhos,
)

from planilhas.gravador_agentes import (
    CAMPOS_ORIGEM,
    MAPEAMENTO_PADRAO,
    adicionar_linhas,
    listar_abas_com_blocos,
    listar_blocos,
    listar_colunas,
    registro_para_linha,
    sugerir_bloco,
)


st.set_page_config(
    page_title="Extração de Portarias",
    page_icon="📄",
    layout="wide"
)

st.title("Extração de informações de portarias")

st.write(
    "Envie um PDF do Diário Oficial da União para identificar informações relevantes."
)


arquivos = st.file_uploader(
    "Selecione uma ou mais portarias em PDF",
    type=["pdf"],
    accept_multiple_files=True
)

arquivo_excel = st.file_uploader(
    "Anexe a planilha que deseja atualizar",
    type=["xlsx"],
    key="planilha"
)


if arquivos:
    resultados = []

    for arquivo in arquivos:
        st.divider()
        st.subheader(arquivo.name)

        try:
            paginas = extrair_texto_pdf(arquivo.getvalue())

            texto_completo = "\n".join(
                p["texto"] for p in paginas
            )

            if not texto_completo.strip():
                st.warning(
                    "Não foi possível extrair texto deste PDF. "
                    "Ele pode precisar de OCR."
                )
                continue

            registros = extrair_informacoes(texto_completo)

            if isinstance(registros, dict):
                registros = [registros]

            if not registros:
                st.warning("Nenhuma portaria foi identificada.")
                continue

            for registro in registros:
                registro["arquivo"] = arquivo.name
                resultados.append(registro)

            with st.expander("Conferir texto original extraído"):
                st.text(texto_completo)

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

    if resultados and arquivo_excel is not None:
        st.divider()
        st.subheader("Enviar para a planilha")

        bytes_excel = arquivo_excel.getvalue()

        modo = st.radio(
            "Tipo de planilha",
            [
                "Relação dos Agentes Responsáveis (blocos por cargo)",
                "Tabela simples (cabeçalho na linha 1)"
            ]
        )

        if modo.startswith("Relação"):

            abas_ag, abas_com_blocos = listar_abas_com_blocos(
                bytes_excel
            )

            aba_ag = st.selectbox(
                "Aba da planilha",
                abas_ag,
                index=abas_ag.index(abas_com_blocos[0])
                if abas_com_blocos else 0,
                key="aba_ag",
            )

            cargos = listar_blocos(bytes_excel, aba_ag)

            if not cargos:
                st.error(
                    f"Não encontrei blocos com o cabeçalho 'CARGO' "
                    f"na aba '{aba_ag}'. Escolha outra aba ou confira "
                    "se é a planilha da Relação dos Agentes."
                )

            else:
                colunas = listar_colunas(bytes_excel, aba_ag)

                rotulos = dict(colunas)

                opcoes_col = [0] + list(rotulos)

                nome_col = lambda n: (
                    "— não enviar —" if n == 0 else rotulos[n]
                )

                with st.expander(
                    "Mapeamento de colunas",
                    expanded=True
                ):

                    st.caption(
                        "Escolha em qual coluna da planilha cada "
                        "informação extraída será gravada."
                    )

                    mapeamento = {}

                    ui = st.columns(2)

                    for k, (campo, rotulo) in enumerate(
                        CAMPOS_ORIGEM.items()
                    ):

                        padrao = MAPEAMENTO_PADRAO.get(campo, 0)

                        if padrao not in opcoes_col:
                            padrao = 0

                        escolha = ui[k % 2].selectbox(
                            rotulo,
                            opcoes_col,
                            index=opcoes_col.index(padrao),
                            format_func=nome_col,
                            key=f"mp_{campo}",
                        )

                        if escolha:
                            mapeamento[campo] = escolha

                    repetidas = [
                        rotulos[n]
                        for n, q in Counter(
                            mapeamento.values()
                        ).items()
                        if q > 1
                    ]

                    if repetidas:
                        st.warning(
                            "Mais de um campo vai para a mesma coluna: "
                            + "; ".join(repetidas)
                            + ". O último com valor prevalece."
                        )

                st.caption(
                    "Confira, para cada portaria, o cargo (bloco) "
                    "e a titularidade."
                )

                itens = []

                for i, reg in enumerate(resultados):

                    c1, c2, c3, c4 = st.columns([1, 3, 3, 2])

                    enviar = c1.checkbox(
                        "Enviar",
                        value=True,
                        key=f"ag_env_{i}"
                    )

                    c2.markdown(
                        f"**{reg.get('nome') or '(nome não identificado)'}**  \n"
                        f"{reg.get('tipo_ato') or '?'} · "
                        f"Portaria {reg.get('numero_portaria')}"
                    )

                    sugestao = (
                        sugerir_bloco(reg.get("cargo"), cargos)
                        or cargos[0]
                    )

                    cargo = c3.selectbox(
                        "Bloco/cargo",
                        cargos,
                        index=cargos.index(sugestao),
                        key=f"ag_cargo_{i}"
                    )

                    tit = c4.selectbox(
                        "Titularidade",
                        ["Titular", "Substituto", "Substituta"],
                        key=f"ag_tit_{i}"
                    )

                    if enviar:
                        itens.append({
                            "cargo": cargo,
                            "linha": registro_para_linha(reg, tit)
                        })

                if itens and mapeamento:

                    previa = []

                    for it in itens:

                        linha = {
                            "Bloco": it["cargo"]
                        }

                        for campo, n in mapeamento.items():

                            v = it["linha"].get(campo)

                            linha[rotulos[n]] = (
                                v.strftime("%d/%m/%Y")
                                if isinstance(v, datetime)
                                else v
                            )

                        previa.append(linha)

                    st.caption("Prévia do que será gravado")

                    st.dataframe(
                        pd.DataFrame(previa),
                        width="stretch"
                    )

                if st.button(
                    "Adicionar à planilha",
                    disabled=not (itens and mapeamento)
                ):

                    try:
                        st.session_state["resultado_agentes"] = {
                            **adicionar_linhas(
                                bytes_excel,
                                itens,
                                aba=aba_ag,
                                mapeamento=mapeamento
                            ),
                            "nome": arquivo_excel.name.rsplit(".", 1)[0],
                        }

                    except Exception as erro:
                        st.session_state.pop(
                            "resultado_agentes",
                            None
                        )

                        st.error(
                            f"Erro ao atualizar a planilha: {erro}"
                        )

                res = st.session_state.get("resultado_agentes")

                if res:

                    st.success(
                        f"{len(res['inseridos'])} linha(s) adicionada(s); "
                        f"{len(res['ignorados'])} já existia(m) "
                        "e foi(ram) ignorada(s)."
                    )

                    for cargo, linha, nome in res["inseridos"]:
                        st.write(
                            f"• linha {linha} — {cargo}: {nome}"
                        )

                    st.download_button(
                        "Baixar planilha atualizada",
                        data=res["arquivo"],
                        file_name=f"{res['nome']}_atualizada.xlsx",
                        mime=(
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet"
                        ),
                    )
        else:

            abas = listar_abas(bytes_excel)

            aba = st.selectbox(
                "Aba da planilha",
                abas
            )

            cabecalhos = obter_cabecalhos(
                bytes_excel,
                aba=aba
            )

            campos_extraidos = list(dict.fromkeys(
                campo
                for registro in resultados
                for campo in registro
            ))

            nenhum = "— não enviar —"

            opcoes = [nenhum] + campos_extraidos

            st.caption(
                "Os campos exibidos abaixo são definidos pelos "
                "cabeçalhos da planilha. Confira as sugestões e "
                "escolha qual informação extraída preencherá cada campo."
            )

            mapeamento = {}

            colunas_ui = st.columns(3)

            for i, cabecalho in enumerate(cabecalhos):

                sugestao = sugerir_campo_para_cabecalho(
                    cabecalho,
                    campos_extraidos,
                )
                indice_inicial = (
                    opcoes.index(sugestao)
                    if sugestao in opcoes
                    else 0
                )

                escolha = colunas_ui[i % 3].selectbox(
                    cabecalho,
                    opcoes,
                    index=indice_inicial,
                    key=f"map_{i}_{cabecalho}"
                )

                if escolha != nenhum:
                    mapeamento[cabecalho] = escolha

            evitar_duplicatas = st.checkbox(
                "Pular portarias que já estão na planilha "
                "(pelo número da portaria)",
                value=True,
                disabled="numero_portaria" not in mapeamento.values(),
            )

            if st.button(
                "Enviar para a planilha",
                disabled=not mapeamento
            ):

                try:
                    st.session_state["resultado_planilha"] = {
                        **enviar_para_planilha_em_memoria(
                            arquivo_excel=bytes_excel,
                            dados=resultados,
                            mapeamento=mapeamento,
                            aba=aba,
                            chave=(
                                "numero_portaria"
                                if evitar_duplicatas
                                else None
                            ),
                        ),
                        "nome": arquivo_excel.name.rsplit(".", 1)[0],
                    }

                except Exception as erro:
                    st.session_state.pop(
                        "resultado_planilha",
                        None
                    )

                    st.error(
                        f"Erro ao enviar para a planilha: {erro}"
                    )

            res = st.session_state.get("resultado_planilha")

            if res:

                st.success(
                    f"{res['inseridos']} linha(s) adicionada(s) "
                    f"a partir da linha {res['primeira_linha']}; "
                    f"{res['ignorados']} duplicada(s) ignorada(s)."
                )

                st.download_button(
                    "Baixar planilha atualizada",
                    data=res["arquivo"],
                    file_name=f"{res['nome']}_atualizada.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
