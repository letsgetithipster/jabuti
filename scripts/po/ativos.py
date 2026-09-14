"""Leitura de dados/ativos.csv: a declaração da pessoa sobre qual bloco da política cada ticker
serve.

É o único campo de uma posição que não é derivável de um fill nem é fato de mercado, e é por isso
que ele tem tabela própria: misturado com qty e pm numa linha só, ele impedia a linha inteira de
ser regenerada — a causa raiz que esta fase remove.

Retrocompatibilidade por construção (Emenda A2): workspace criado antes desta versão não tem
ativos.csv e guarda a mesma declaração em dados/posicoes.csv. Enquanto o arquivo antigo existir, a
classe sai dele e nada quebra. Não existe migrador, e é de propósito: migrador é código que só
serve uma vez, e este caminho serve sempre.

A última linha por ticker vence, espelhando csvs.ultimas_cotacoes: anexar_csv nunca reescreve, e
corrigir uma classe é anexar a linha certa no fim.
"""
from pathlib import Path

from po.csvs import ler_csv


def ler_ativos(raiz: str | Path) -> tuple[dict[str, str], list[str], str]:
    """({ticker: classe}, erros, origem). `origem` é 'dados/ativos.csv', 'dados/posicoes.csv'
    (caminho retrocompatível) ou 'nenhum'."""
    raiz = Path(raiz)
    for nome in ("ativos", "posicoes"):
        caminho = raiz / "dados" / f"{nome}.csv"
        if not caminho.exists():
            continue
        linhas, erros = ler_csv(nome, caminho)
        return ({l["ticker"]: l["classe"] for l in linhas}, erros, f"dados/{nome}.csv")
    return {}, [], "nenhum"
