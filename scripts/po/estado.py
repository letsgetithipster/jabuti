"""Gerador mínimo de estado/ESTADO.md a partir de dados/ e da política declarada.

ESTADO.md é gerado, nunca editado à mão (camada de consistência, regra 3). O fechar-mes
da Fase 4 absorve este gerador; até lá, ele roda depois de importar/cotar.
Formato pinado pelo check_estado: a linha 'Total investido: R$ x'. A tabela de blocos é
conferida só pelos testes deste módulo.
"""
import datetime
from pathlib import Path

from po.carteira import valorar
from po.csvs import ler_csv
from po.numeros import formatar_brl


def _uma_casa(frac: float) -> str:
    """Percentual com uma casa, em pt-BR. O inteiro sozinho fazia a pendência ler '45% vs 45%',
    como se estivesse na banda, justamente no caso-limite que ela existe para denunciar."""
    return f"{frac:.1f}".replace(".", ",")


def _fracao(valor: float, total: float) -> float:
    """Percentual EXATO. O inteiro é para exibir; quem decide banda tem que usar este número.
    Decidir sobre o arredondado fazia 45,4% virar 45 e uma banda de máximo 45 dizer 'dentro',
    sem pendência — no arquivo que existe justamente para dar esse veredito."""
    return 100 * valor / total if total else 0.0


def render_estado(raiz: str | Path, hoje: datetime.date | None = None) -> str:
    raiz = Path(raiz)
    hoje = hoje or datetime.date.today()
    c = valorar(raiz, hoje=hoje)
    bandas = {b.bloco: b for b in c.bandas}
    linhas_tab, pendencias = [], []
    ordem = [b.bloco for b in c.bandas] + sorted(bl for bl in c.por_bloco if bl not in bandas)
    for bloco in ordem:
        valor = c.por_bloco[bloco]
        frac = _fracao(valor, c.total_brl)
        pct = int(round(frac))
        b = bandas.get(bloco)
        if b is None:
            banda, desvio = "—", "sem banda"   # a pendência vem de c.avisos, uma frase só (I5)
        else:
            banda = f"{b.minimo:g}-{b.maximo:g}"
            if frac < b.minimo:
                desvio = "abaixo"
                pendencias.append(f"{bloco} abaixo do mínimo ({_uma_casa(frac)}% vs {b.minimo:g}%): priorizar nos próximos aportes")
            elif frac > b.maximo:
                desvio = "acima"
                pendencias.append(f"{bloco} acima da banda máxima ({_uma_casa(frac)}% vs {b.maximo:g}%): rebalancear via aporte nos blocos abaixo")
            else:
                desvio = "dentro"
        linhas_tab.append(f"| {bloco} | R$ {formatar_brl(valor)} | {pct} | {banda} | {desvio} |")
    pendencias.extend(c.avisos)   # a valoração é quem sabe o que ficou sem banda e o que está velho
    eventos, erros = ler_csv("eventos", raiz / "dados" / "eventos.csv")
    if erros:
        raise ValueError(f"dados/eventos.csv com erros — corrija antes (rode o validador): {erros[0]}")
    pendentes = [e["ticker"] for e in eventos if e["confirmado"] == "nao"]
    if pendentes:
        pendencias.append(f"{len(pendentes)} evento(s) em eventos.csv aguardando confirmação ({', '.join(pendentes)})")
    manuais = sum(1 for l in c.linhas if l.fonte == "manual")
    cot = (f"Cotações: mais antiga de {c.data_cotacao_mais_antiga} · {manuais} manual(is) de {len(c.linhas)}"
           if c.linhas else "Cotações: nenhuma posição")
    corpo = "\n".join(f"- {p}" for p in pendencias) if pendencias else "(nenhuma)"
    return (
        "---\n"
        "tipo: estado\n"
        "gerado-por: gerar-estado\n"
        f"data-referencia: {hoje.isoformat()}\n"
        "---\n\n"
        "# ESTADO — leitura de 1 tela\n\n"
        "> GERADO por scripts/gerar_estado.py a partir de dados/ e da política. Nunca editar à mão.\n"
        "> Primeira leitura para qualquer pergunta de alocação.\n\n"
        f"Total investido: R$ {formatar_brl(c.total_brl)}\n\n"
        "| Bloco | Valor | % | Banda | Desvio |\n|---|---|---|---|---|\n"
        + "\n".join(linhas_tab) + "\n\n"
        f"{cot}\n\n"
        "## Pendências\n"
        f"{corpo}\n"
    )


def gerar_estado(raiz: str | Path, hoje: datetime.date | None = None) -> tuple[Path, str]:
    """Escreve estado/ESTADO.md e devolve (caminho, texto). ValueError (sem gravar) se dados/ não
    sustenta o número. Devolver o texto evita o CLI reler do disco fora do try só para imprimir o
    resumo — releitura que podia levantar depois de todos os except, contra o "nunca traceback"."""
    raiz = Path(raiz)
    texto = render_estado(raiz, hoje)
    destino = raiz / "estado" / "ESTADO.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return destino, texto
