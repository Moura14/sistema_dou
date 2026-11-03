
import streamlit as st
import pandas as pd

from services.leitor_pdf import extrair_texto_pdf
from extracao.portaria import extrair_informacoes
from planilhas.gravador_excel import enviar_para_planilha_em_memoria


st.set_page_config(
    page_title="Extração de Portarias",
    page_icon="📄",
    layout="wide"
)

st.title("Extração de informações de portarias")
st.write(
    "Envie um PDF do Diário Oficial da União "
    "para identificar informações relevantes."
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
                pagina["texto"] for pagina in paginas
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
                st.warning(
                    "Nenhuma portaria foi identificada."
                )
                continue

            for registro in registros:
                registro["arquivo"] = arquivo.name
                resultados.append(registro)

            st.json(registros)

            with st.expander("Conferir texto original extraído"):
                st.text(texto_completo)

        except Exception as erro:
            st.error(
                f"Erro ao processar {arquivo.name}: {erro}"
            )

    if resultados:
        st.divider()
        st.subheader("Resumo dos documentos")

        df = pd.DataFrame(resultados)
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "Baixar resultado em CSV",
            data=csv,
            file_name="informacoes_portarias.csv",
            mime="text/csv"
        )

    if resultados and arquivo_excel is not None:
        if st.button("Enviar para a planilha"):
            try:
                mapeamento = {
                    campo: campo
                    for campo in resultados[0]
                }

                primeira_linha, planilha_atualizada = (
                    enviar_para_planilha_em_memoria(
                        arquivo_excel=arquivo_excel.getvalue(),
                        dados=resultados,
                        mapeamento=mapeamento
                    )
                )

                st.success("Dados enviados para a planilha!")

                nome_saida = arquivo_excel.name.rsplit(".", 1)[0]

                st.download_button(
                    "Baixar planilha atualizada",
                    data=planilha_atualizada,
                    file_name=f"{nome_saida}_atualizada.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as erro:
                st.error(f"Erro ao enviar para a planilha: {erro}")
