"""Escrita em dados/ após conciliação: dedupe por chave natural, saldo-inicial para posição
nova, log de importação em logs/importacoes/. Nada aqui roda sem a conciliação ter passado."""
import datetime
from pathlib import Path

from po.csvs import anexar_csv, ler_csv
from po.ingestao.engine import Resultado

TABELAS = ("posicoes", "fills", "proventos", "eventos")
CHAVES = {
    "proventos": lambda r: (r["data"], r["ticker"], r["tipo"], r["conta"], round(float(r["valor_bruto"]), 2)),
    "fills": lambda r: (r["data"], r["ticker"], r["tipo"], r["conta"], round(float(r["qty"]), 6), round(float(r["preco"]), 4)),
    "eventos": lambda r: (r["data"], r["ticker"], r["tipo"]),
    "posicoes": lambda r: (r["ticker"], r["conta"]),
}


def _existentes(raiz: Path) -> dict[str, list[dict]]:
    tabelas = {}
    for nome in TABELAS:
        linhas, erros = ler_csv(nome, raiz / "dados" / f"{nome}.csv")
        if erros:
            raise ValueError(f"dados/{nome}.csv com erros — corrija antes de importar (rode o validador): {erros[0]}")
        tabelas[nome] = linhas
    return tabelas


def _mesma_posicao(a: dict, b: dict) -> bool:
    return abs(a["qty"] - b["qty"]) <= 1e-6 and abs(a["pm"] - b["pm"]) <= 0.005


def separar(raiz: Path, res: Resultado) -> tuple[dict[str, list[dict]], dict[str, int], list[str]]:
    """(novos por tabela, duplicadas por tabela, conflitos de posição)."""
    existentes = _existentes(raiz)
    novos, duplicadas, conflitos = {}, {}, []
    for nome in TABELAS:
        chave = CHAVES[nome]
        atuais = {chave(e): e for e in existentes[nome]}
        novos[nome], duplicadas[nome] = [], 0
        for r in res.registros.get(nome, []):
            k = chave(r)
            if k in atuais:
                if nome == "posicoes" and not _mesma_posicao(atuais[k], r):
                    e = atuais[k]
                    conflitos.append(f"{r['ticker']} ({r['conta']}): já existe em posicoes.csv com qty {e['qty']:g} "
                                     f"@ {e['pm']:.2f}; o documento diz {r['qty']:g} @ {r['pm']:.2f} — use --conferir "
                                     "ou corrija dados/ antes")
                    continue
                duplicadas[nome] += 1
                continue
            atuais[k] = r
            novos[nome].append(r)
    return novos, duplicadas, conflitos


def gravar(raiz: str | Path, res: Resultado, *, mapeamento: str, arquivo: str, conciliacao: str,
           conta: str, hoje: datetime.date | None = None) -> dict:
    """Grava os registros novos e o log. Retorna {'gravadas': {...}, 'duplicadas': {...}, 'log': Path}.
    ValueError em conflito de posição ou dados/ sujo — nada é gravado nesses casos."""
    raiz = Path(raiz)
    hoje = hoje or datetime.date.today()
    novos, duplicadas, conflitos = separar(raiz, res)
    if conflitos:
        raise ValueError("conflito com dados/ existente — nada gravado:\n  " + "\n  ".join(conflitos))
    for p in novos["posicoes"]:   # decisão 6: posição nova nasce com saldo-inicial, o ledger fecha
        novos["fills"].append({"data": p["_data"], "ticker": p["ticker"], "tipo": "saldo-inicial", "qty": p["qty"],
                               "preco": p["pm"], "taxa": 0.0, "conta": p["conta"], "moeda": p["moeda"]})
    gravadas = {}
    for nome in TABELAS:
        gravadas[nome] = anexar_csv(nome, raiz / "dados" / f"{nome}.csv", novos[nome]) if novos[nome] else 0
    log = _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas, duplicadas)
    return {"gravadas": gravadas, "duplicadas": duplicadas, "log": log}


def _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas, duplicadas) -> Path:
    pasta = raiz / "logs" / "importacoes"
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"{hoje.isoformat()}-{mapeamento}"
    caminho, k = pasta / f"{base}.md", 2
    while caminho.exists():
        caminho = pasta / f"{base}-{k}.md"
        k += 1
    motivos = {}
    for _, motivo in res.ignoradas:
        motivos[motivo] = motivos.get(motivo, 0) + 1
    tabela = "\n".join(f"| {t} | {gravadas[t]} | {duplicadas[t]} |" for t in TABELAS)
    ignoradas = "; ".join(f"{m}: {c}" for m, c in motivos.items()) or "nenhuma"
    caminho.write_text(
        "---\n"
        f"tipo: log-importacao\ndata: {hoje.isoformat()}\nconta: {conta}\nmapeamento: {mapeamento}\n"
        f"arquivo: \"{arquivo}\"\nconciliacao: \"{conciliacao}\"\n"
        "---\n\n"
        f"# Importação {hoje.isoformat()} — {mapeamento}\n\n"
        f"Arquivo `{arquivo}` na conta `{conta}`: {res.linhas_lidas} linha(s) lidas, "
        f"{res.classificadas} classificadas, {len(res.ignoradas)} ignoradas.\n\n"
        "| Tabela | Gravadas | Duplicadas (puladas) |\n|---|---|---|\n" + tabela + "\n\n"
        f"Ignoradas por motivo: {ignoradas}\n\n"
        f"Conciliação: {conciliacao}\n",
        encoding="utf-8")
    return caminho


def conferir(raiz: str | Path, res: Resultado) -> list[str]:
    """Compara o documento com dados/ sem gravar. Uma linha de texto por achado."""
    raiz = Path(raiz)
    existentes = _existentes(raiz)
    linhas = []
    chave = CHAVES["posicoes"]
    atual = {chave(e): e for e in existentes["posicoes"]}
    doc = set()
    for r in res.registros["posicoes"]:
        k = chave(r)
        doc.add(k)
        e = atual.get(k)
        if e is None:
            linhas.append(f"  {r['ticker']} ({r['conta']}): NOVA no documento — {r['qty']:g} @ {r['pm']:.2f}")
        elif not _mesma_posicao(e, r):
            linhas.append(f"  {r['ticker']} ({r['conta']}): DIVERGE — dados/ {e['qty']:g} @ {e['pm']:.2f} "
                          f"vs documento {r['qty']:g} @ {r['pm']:.2f}")
        else:
            linhas.append(f"  {r['ticker']} ({r['conta']}): OK — {r['qty']:g} @ {r['pm']:.2f}")
    if res.registros["posicoes"]:
        for k, e in atual.items():
            if k not in doc:
                linhas.append(f"  {e['ticker']} ({e['conta']}): só em dados/ (ausente no documento)")
    for nome in ("fills", "proventos", "eventos"):
        regs = res.registros[nome]
        if regs:
            vistas = {CHAVES[nome](e) for e in existentes[nome]}
            ja = sum(1 for r in regs if CHAVES[nome](r) in vistas)
            linhas.append(f"  {nome}: {len(regs) - ja} nova(s), {ja} já presente(s)")
    return linhas
