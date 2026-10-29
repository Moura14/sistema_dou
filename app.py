
import streamlit as st
import pandas as pd

from services.leitor_pdf import extrair_texto_pdf
from extracao.portaria import extrair_informacoes


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

            dados = extrair_informacoes(texto_completo)
            dados["arquivo"] = arquivo.name

            resultados.append(dados)

            st.json(dados)

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
