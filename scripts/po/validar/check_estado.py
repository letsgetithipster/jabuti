"""Confere estado/ESTADO.md contra o que o gerador produz a partir de dados/ e da política.

O recálculo não mora aqui: mora em po/estado.py, o mesmo que gerar_estado.py chama. O check
renderiza em memória e compara o ARQUIVO INTEIRO, em vez de pinar a linha do total por regex —
assim uma edição à mão em qualquer linha (banda, percentual, pendência) é acusada, não só no total.

A comparação ancora no `data-referencia` do próprio arquivo, nunca em date.today(): ancorado ela
é estável para sempre; contra o relógio ela ficaria vermelha todo dia seguinte ao da geração, com
erro que não corresponde a defeito de dado nenhum. Pelo mesmo motivo, a IDADE do arquivo se mede
contra os INPUTS dele (a data mais recente em cotacoes.csv e fills.csv), não contra o calendário:
gerado que ficou para trás dos dados é o defeito real; gerado que envelheceu sozinho não é.

Duas bordas são nomeadas em vez de silenciadas: `data-referencia` com forma certa e data
impossível é erro do frontmatter, não aviso em inglês vindo do fromisoformat; e arquivo que só
difere na quebra de linha final é acusado pela quebra, porque splitlines() não a enxerga.
"""
import datetime
import re
from pathlib import Path

from po.csvs import ler_csv
from po.estado import render_estado

DATA_REF_RE = re.compile(r"(?m)^data-referencia:\s*(\d{4}-\d{2}-\d{2})\s*$")


def _data_mais_recente(raiz: Path, nome: str) -> str | None:
    caminho = raiz / "dados" / f"{nome}.csv"
    if not caminho.exists():
        return None
    linhas, erros = ler_csv(nome, caminho)
    if erros or not linhas:
        return None
    return max(l["data"] for l in linhas)


def _quebras(texto: str) -> str:
    """Como o texto termina e que quebra de linha ele usa. splitlines() apaga as duas coisas,
    então é aqui que a divergência que ele não vê vira frase."""
    estilo = "CRLF" if "\r\n" in texto else "CR" if "\r" in texto else "LF"
    fim = "com" if texto.endswith(("\n", "\r")) else "sem"
    return f"{estilo}, {fim} quebra de linha no fim"


def _primeira_divergencia(esperado: str, obtido: str) -> str:
    a, b = esperado.splitlines(), obtido.splitlines()
    for i in range(max(len(a), len(b))):
        la = a[i] if i < len(a) else "(fim do arquivo)"
        lb = b[i] if i < len(b) else "(fim do arquivo)"
        if la != lb:
            return f"linha {i + 1}: o arquivo diz {lb!r}, o gerador produz {la!r}"
    return ("as linhas batem uma a uma e as quebras de linha não: o arquivo está em "
            f"{_quebras(obtido)} e o gerador produz {_quebras(esperado)}")


def checar_estado(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Dado ausente/sujo suspende a comparação com aviso: o check de
    dados é quem nomeia a causa de origem, e somar erro derivado aqui esconderia ela."""
    raiz = Path(raiz)
    erros, avisos = [], []
    estado = raiz / "estado" / "ESTADO.md"
    if not estado.exists():
        return ["estado/ESTADO.md ausente"], []
    try:
        conteudo = estado.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return ["estado/ESTADO.md: não é UTF-8 válido — salve o arquivo como UTF-8"], []
    m = DATA_REF_RE.search(conteudo)
    if not m:
        return ["estado/ESTADO.md: frontmatter sem `data-referencia: AAAA-MM-DD` — o arquivo é "
                "gerado; rode `python <motor>/scripts/gerar_estado.py .` em vez de editá-lo"], []
    referencia = m.group(1)
    try:
        ancora = datetime.date.fromisoformat(referencia)
    except ValueError:
        return [f"estado/ESTADO.md: data-referencia {referencia} tem a forma AAAA-MM-DD mas não é "
                "uma data do calendário — o arquivo é gerado, nunca editado à mão: rode "
                "`python <motor>/scripts/gerar_estado.py .`"], []
    try:
        esperado = render_estado(raiz, hoje=ancora)
    except (FileNotFoundError, ValueError) as e:
        avisos.append(f"ESTADO: comparação suspensa — {e}")
        return erros, avisos
    if esperado != conteudo:
        erros.append(
            "estado/ESTADO.md difere do que o gerador produz a partir de dados/ e da política "
            f"({_primeira_divergencia(esperado, conteudo)}) — o arquivo é gerado, nunca editado "
            "à mão: rode `python <motor>/scripts/gerar_estado.py .`")
    mais_novo = max((d for d in (_data_mais_recente(raiz, "cotacoes"),
                                 _data_mais_recente(raiz, "fills")) if d), default=None)
    if mais_novo and mais_novo > referencia:
        avisos.append(f"estado/ESTADO.md tem data-referencia {referencia} e dados/ já tem dado de "
                      f"{mais_novo} — regenere: `python <motor>/scripts/gerar_estado.py .`")
    return erros, avisos
