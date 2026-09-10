"""Gerador mínimo de estado/ESTADO.md a partir de dados/ e da política declarada.

ESTADO.md é gerado, nunca editado à mão (camada de consistência, regra 3). O fechar-mes
da Fase 4 absorve este gerador; até lá, ele roda depois de importar/cotar.
Formato pinado pelo check_estado: linha 'Total investido: R$ x' e tabela de blocos.
"""
import datetime
from pathlib import Path

from po.carteira import valorar
from po.csvs import ler_csv
from po.numeros import formatar_brl


def _pct(valor: float, total: float) -> int:
    return int(round(100 * valor / total)) if total else 0


def render_estado(raiz: str | Path, hoje: datetime.date | None = None) -> str:
    raiz = Path(raiz)
    hoje = hoje or datetime.date.today()
    c = valorar(raiz)
    bandas = {b.bloco: b for b in c.bandas}
    linhas_tab, pendencias = [], []
    ordem = [b.bloco for b in c.bandas] + sorted(bl for bl in c.por_bloco if bl not in bandas)
    for bloco in ordem:
        valor = c.por_bloco[bloco]
        pct = _pct(valor, c.total_brl)
        b = bandas.get(bloco)
        if b is None:
            banda, desvio = "—", "sem banda"
            pendencias.append(f"{bloco} tem posição mas nenhuma banda declarada (defina no /definir-macro)")
        else:
            banda = f"{b.minimo:g}-{b.maximo:g}"
            if pct < b.minimo:
                desvio = "abaixo"
                pendencias.append(f"{bloco} abaixo do mínimo ({pct}% vs {b.minimo:g}%): priorizar nos próximos aportes")
            elif pct > b.maximo:
                desvio = "acima"
                pendencias.append(f"{bloco} acima da banda máxima ({pct}% vs {b.maximo:g}%): rebalancear via aporte nos blocos abaixo")
            else:
                desvio = "dentro"
        linhas_tab.append(f"| {bloco} | R$ {formatar_brl(valor)} | {pct} | {banda} | {desvio} |")
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


def gerar_estado(raiz: str | Path, hoje: datetime.date | None = None) -> Path:
    """Escreve estado/ESTADO.md. ValueError (sem gravar) se dados/ não sustenta o número."""
    raiz = Path(raiz)
    texto = render_estado(raiz, hoje)
    destino = raiz / "estado" / "ESTADO.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return destino
