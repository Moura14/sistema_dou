
import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import json

st.set_page_config(
    page_title="Analisador do DOU",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Analisador de Atos de Pessoal")
st.write(
    "Envie um PDF do Diário Oficial da União para "
    "extrair informações de portarias."
)


def buscar(padrao, texto, grupo=1):
    resultado = re.search(
        padrao,
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )
    return resultado.group(grupo).strip() if resultado else None


def identificar_tipo(texto):
    texto = texto.lower()

    regras = [
        ("Teletrabalho no exterior", r"teletrabalho.*exterior"),
        ("Nomeação", r"\bnomear\b|\bnomeação\b"),
        ("Exoneração", r"\bexonerar\b|\bexoneração\b"),
        ("Aposentadoria", r"\baposentadoria\b|\baposentar\b"),
        ("Cessão", r"\bcessão\b|\bceder\b"),
        ("Remoção", r"\bremoção\b|\bremover\b"),
        ("Licença", r"\blicença\b"),
    ]

    for tipo, padrao in regras:
        if re.search(padrao, texto):
            return tipo

    return "Não identificado"




def extrair_informacoes(texto, pagina):
    texto = re.sub(r"\s+", " ", texto).strip()

    # Número do ato: por exemplo, "Nº 1.097 - NOMEAR"
    numero_portaria = buscar(
        r"\bN[º°o.]?\s*([\d.]+)\s*-\s*"
        r"(?:NOMEAR|EXONERAR|DESIGNAR|DISPENSAR)\b",
        texto
    )

    # Nomeação: o nome aparece antes de "para exercer".
    nome = buscar(
        r"\bNOMEAR\b\s+(.+?)\s*,?\s*para exercer\b",
        texto
    )

    # Exoneração: o nome aparece antes de "do cargo".
    if not nome:
        nome = buscar(
            r"\bEXONERAR\b\s*,?\s*(?:a pedido\s*,?\s*)?"
            r"(.+?)\s+do cargo\b",
            texto
        )

    # Formato alternativo: "ao servidor NOME, matrícula SIAPE..."
    if not nome:
        nome = buscar(
            r"\b(?:ao|à)\s+(?:servidor|servidora)\s+"
            r"(.+?),?\s*matrícula\s+SIAPE\b",
            texto
        )

    if nome:
        nome = nome.strip(" ,.;:-")

    matricula = buscar(
        r"matrícula\s+SIAPE\s*(?:n[º°o.]?\s*)?"
        r"([\d.-]+)",
        texto
    )

    processo = buscar(
        r"Processo\s+n[º°o.]?\s*([\d./-]+)",
        texto
    )

    pais = buscar(
        r"no exterior,\s*na\s+([^,;.]+)",
        texto
    )

    prazo = buscar(
        r"pelo prazo de\s+(.+?)\s+meses?",
        texto
    )

    data_inicio = buscar(
        r"a contar de\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
        texto
    )

    cargo = buscar(
        r"para exercer o cargo de\s+(.+?),\s*código",
        texto
    )

    if not cargo:
        cargo = buscar(
            r"do cargo de\s+(.+?),\s*código",
            texto
        )

    tipo = identificar_tipo(texto)

    return {
        "Tipo de ato": tipo,
        "Nome do servidor": nome,
        "Matrícula SIAPE": matricula,
        "Cargo/função": cargo,
        "Unidade": None,
        "País/local": pais,
        "Prazo": prazo,
        "Data de início": data_inicio,
        "Processo": processo,
        "Número da portaria": numero_portaria,
        "Página": pagina,
        "Texto original": texto,
        "Status": "Conferir"
    }




arquivo = st.file_uploader(
    "Selecione ou arraste o PDF do DOU",
    type=["pdf"]
)

if arquivo:
    st.success(f"PDF selecionado: {arquivo.name}")

    if st.button("🔎 Analisar documento", type="primary"):
        resultados = []
        paginas_sem_texto = []

        try:
            with st.spinner("Lendo o PDF..."):
                with pdfplumber.open(
                    io.BytesIO(arquivo.getvalue())
                ) as pdf:

                    for numero, pagina in enumerate(pdf.pages, start=1):
                        texto = pagina.extract_text() or ""

                        if not texto.strip():
                            paginas_sem_texto.append(numero)
                            continue

                        # Procura trechos iniciados por artigos.
                        blocos = re.split(
                            r"(?=Art\.\s*\d+º?)",
                            texto,
                            flags=re.IGNORECASE
                        )

                        # Reúne os artigos de uma página.
                        # Para este MVP, cada trecho relevante é
                        # apresentado para conferência.
                        for bloco in blocos:
                            if not bloco.strip():
                                continue

                            tipos = identificar_tipo(bloco)

                            if tipos != "Não identificado":
                                resultados.append(
                                    extrair_informacoes(bloco, numero)
                                )

            st.session_state["resultados"] = resultados
            st.session_state["paginas_sem_texto"] = paginas_sem_texto

        except Exception as erro:
            st.error(f"Erro ao processar o PDF: {erro}")


if "resultados" in st.session_state:
    resultados = st.session_state["resultados"]
    paginas_sem_texto = st.session_state["paginas_sem_texto"]

    st.divider()
    st.header("📋 Informações extraídas")

    st.metric("Trechos identificados", len(resultados))

    if paginas_sem_texto:
        st.warning(
            "Não foi possível extrair texto das páginas: "
            + ", ".join(map(str, paginas_sem_texto))
            + ". Pode ser necessário usar OCR."
        )

    if not resultados:
        st.warning(
            "Nenhum trecho com as palavras pesquisadas foi encontrado. "
            "Isso não garante que o PDF não contenha atos relevantes."
        )
    else:
        for indice, item in enumerate(resultados):
            with st.expander(
                f"{item['Tipo de ato']} — Página {item['Página']} "
                f"— Trecho {indice + 1}",
                expanded=(indice == 0)
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.text_input(
                        "Tipo de ato",
                        value=item["Tipo de ato"],
                        key=f"tipo_{indice}"
                    )
                    st.text_input(
                        "Nome do servidor",
                        value=item["Nome do servidor"] or "",
                        key=f"nome_{indice}"
                    )
                    st.text_input(
                        "Cargo/função",
                        value=item["Cargo/função"] or "",
                        key=f"cargo_{indice}"
                    )

                with col2:
                    st.text_input(
                        "Data de início",
                        value=item["Data de início"] or "",
                        key=f"inicio_{indice}"
                    )
                    st.text_input(
                        "Processo",
                        value=item["Processo"] or "",
                        key=f"processo_{indice}"
                    )
                    st.text_input(
                        "Número da portaria",
                        value=item["Número da portaria"] or "",
                        key=f"portaria_{indice}"
                    )

                st.caption(f"Página do PDF: {item['Página']}")
                st.text_area(
                    "Texto original para conferência",
                    value=item["Texto original"],
                    height=180,
                    key=f"texto_{indice}"
                )

        # Exporta os resultados extraídos.
        dados_json = json.dumps(
            resultados,
            ensure_ascii=False,
            indent=2
        )

        st.download_button(
            "⬇️ Baixar informações em JSON",
            data=dados_json.encode("utf-8"),
            file_name="atos_extraidos.json",
            mime="application/json"
        )

        csv_buffer = io.StringIO()
        pd.DataFrame(resultados).drop(
            columns=["Texto original"],
            errors="ignore"
        ).to_csv(csv_buffer, index=False)

        st.download_button(
            "⬇️ Baixar tabela em CSV",
            data=csv_buffer.getvalue().encode("utf-8-sig"),
            file_name="atos_extraidos.csv",
            mime="text/csv"
        )
