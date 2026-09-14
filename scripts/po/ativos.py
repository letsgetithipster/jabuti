"""Leitura de dados/ativos.csv: a declaração da pessoa sobre qual bloco da política cada ticker
serve.

É o único campo de uma posição que não é derivável de um fill nem é fato de mercado, e é por isso
que ele tem tabela própria: misturado com qty e pm numa linha só, ele impedia a linha inteira de
ser regenerada — a causa raiz que esta fase remove.

Retrocompatibilidade por construção (Emenda A2): workspace criado antes desta versão não tem
ativos.csv e guarda a mesma declaração em dados/posicoes.csv. Enquanto o arquivo antigo existir, a
classe sai dele e nada quebra. Não existe migrador, e é de propósito: migrador é código que só
serve uma vez, e este caminho serve sempre.

Os dois arquivos se SOMAM, ticker a ticker, com ativos.csv por cima: a declaração nova vence onde
existe, a antiga cobre o resto. Preferir um arquivo inteiro ao outro parecia equivalente e não é —
todo workspace criado pelo template já nasce com um ativos.csv vazio, e "existe" bastava para
desligar a queda. Medido: importar um extrato num workspace novo gravava a classe em posicoes.csv,
ativos.csv continuava só com o cabeçalho, e gerar_estado.py morria com "PETR4 tem fill mas nenhuma
classe declarada". Somar torna a frase acima verdadeira em vez de aspiracional.

A última linha por ticker vence, espelhando csvs.ultimas_cotacoes: anexar_csv nunca reescreve, e
corrigir uma classe é anexar a linha certa no fim.
"""
from pathlib import Path

from po.csvs import ler_csv


def ler_ativos(raiz: str | Path) -> tuple[dict[str, str], list[str], str]:
    """({ticker: classe}, erros, origem). `origem` nomeia o arquivo que tem a última palavra:
    'dados/ativos.csv' quando ele existe, 'dados/posicoes.csv' no caminho retrocompatível puro,
    'nenhum' quando não há nenhum dos dois."""
    raiz = Path(raiz)
    classes: dict[str, str] = {}
    erros: list[str] = []
    origens: list[str] = []
    for nome in ("posicoes", "ativos"):        # ativos por último: ele sobrescreve, nunca o contrário
        caminho = raiz / "dados" / f"{nome}.csv"
        if not caminho.exists():
            continue
        linhas, erros_do_arquivo = ler_csv(nome, caminho)
        erros += erros_do_arquivo
        classes.update({l["ticker"]: l["classe"] for l in linhas})
        origens.append(f"dados/{nome}.csv")
    return classes, erros, origens[-1] if origens else "nenhum"
