
from difflib import SequenceMatcher
from planilhas.esquema import normalizar


def sugerir_colunas_chave(colunas: list[str]) -> list[str]:
    for coluna in colunas:
        if "nome" in normalizar(coluna):
            return [coluna]

    return colunas[:1]


def localizar_linha(
    tabela: dict,
    colunas_chave: list[str],
    valores_chave: dict,
    limite: float = 0.88,
):
    alvo = {
        coluna: normalizar(valores_chave.get(coluna))
        for coluna in colunas_chave
    }

    alvo = {
        coluna: valor
        for coluna, valor in alvo.items()
        if valor
    }

    if not alvo:
        return None, 0.0, 0

    exatos = [
        linha
        for linha, dados in tabela.items()
        if all(
            normalizar(dados.get(coluna)) == valor
            for coluna, valor in alvo.items()
        )
    ]

    if exatos:
        return exatos[0], 1.0, len(exatos)

    melhor = None
    melhor_score = 0.0
    empates = 0

    for linha, dados in tabela.items():
        scores = []

        for coluna, valor in alvo.items():
            atual = normalizar(dados.get(coluna))

            score = (
                SequenceMatcher(None, valor, atual).ratio()
                if atual else 0.0
            )

            scores.append(score)

        score_final = sum(scores) / len(scores)

        if score_final > melhor_score + 1e-9:
            melhor = linha
            melhor_score = score_final
            empates = 1

        elif melhor is not None and abs(
            score_final - melhor_score
        ) <= 1e-9:
            empates += 1

    if melhor is not None and melhor_score >= limite:
        return melhor, melhor_score, empates

    return None, melhor_score, 0