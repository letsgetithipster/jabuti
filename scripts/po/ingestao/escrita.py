"""Escrita em dados/ após conciliação: dedupe por multiconjunto contra dados/, saldo-inicial
para ticker sem NENHUM fill, log de importação em logs/importacoes/. Nada aqui roda sem a
conciliação ter passado: `gravar` recusa Resultado com erro."""
import datetime
from collections import Counter
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


def separar(existentes: dict[str, list[dict]], res: Resultado) -> tuple[dict[str, list[dict]], dict[str, int], list[str]]:
    """(novos por tabela, duplicadas por tabela, conflitos de posição).

    A comparação é de MULTICONJUNTO contra o que já está em dados/, nunca do documento contra
    ele mesmo: duas execuções parciais da mesma ordem no mesmo dia, pelo mesmo preço, são dois
    eventos reais e rotineiros em B3 e Schwab. Deduplicar o documento contra si mesmo perderia
    a segunda em silêncio — e a conciliação já tinha abençoado as duas."""
    novos, duplicadas, conflitos = {}, {}, []
    for nome in TABELAS:
        chave = CHAVES[nome]
        restantes = Counter(chave(e) for e in existentes[nome])
        por_chave = {chave(e): e for e in existentes[nome]}
        novos[nome], duplicadas[nome] = [], 0
        for r in res.registros.get(nome, []):
            k = chave(r)
            if restantes[k] > 0:
                if nome == "posicoes" and not _mesma_posicao(por_chave[k], r):
                    e = por_chave[k]
                    conflitos.append(f"{r['ticker']} ({r['conta']}): já existe em posicoes.csv com qty {e['qty']:g} "
                                     f"@ {e['pm']:.2f}; o documento diz {r['qty']:g} @ {r['pm']:.2f}. Ou a corretora "
                                     "reapresentou a posição, ou este é o arquivo/conta errado — confira com "
                                     "--conferir antes de mexer em dados/")
                    continue
                restantes[k] -= 1
                duplicadas[nome] += 1
                continue
            novos[nome].append(r)
    return novos, duplicadas, conflitos


def gravar(raiz: str | Path, res: Resultado, *, mapeamento: str, arquivo: str, conciliacao: str,
           conta: str, hoje: datetime.date | None = None) -> dict:
    """Grava os registros novos e o log. Retorna {'gravadas': {...}, 'duplicadas': {...}, 'log': Path}.
    ValueError em conflito de posição ou dados/ sujo — nada é gravado nesses casos."""
    raiz = Path(raiz)
    hoje = hoje or datetime.date.today()
    if res.erros:   # o contrato do módulo é este; sem a guarda ele valia só por disciplina
        raise ValueError("a ingestão reportou erro — nada gravado: " + res.erros[0])
    existentes = _existentes(raiz)
    novos, duplicadas, conflitos = separar(existentes, res)
    if conflitos:
        raise ValueError("conflito com dados/ existente — nada gravado:\n  " + "\n  ".join(conflitos))
    # Decisão 6: posição sem NENHUM fill ganha um saldo-inicial, e o ledger fecha. A condição é
    # "sem fill", não "posição nova": se uma gravação anterior morreu no meio (arquivo travado),
    # a posição já está lá e a rodada seguinte precisa conseguir completar a abertura que
    # faltou. Ticker que já tem fill de verdade nunca ganha abertura sintética.
    com_fills = {(f["ticker"], f["conta"]) for f in existentes["fills"]}
    com_fills |= {(f["ticker"], f["conta"]) for f in novos["fills"]}
    for p in res.registros.get("posicoes", []):
        chave = (p["ticker"], p["conta"])
        if chave in com_fills:
            continue
        novos["fills"].append({"data": p["_data"], "ticker": p["ticker"], "tipo": "saldo-inicial", "qty": p["qty"],
                               "preco": p["pm"], "taxa": 0.0, "conta": p["conta"], "moeda": p["moeda"]})
        com_fills.add(chave)
    gravadas = {t: 0 for t in TABELAS}
    try:
        for nome in TABELAS:
            if novos[nome]:
                gravadas[nome] = anexar_csv(nome, raiz / "dados" / f"{nome}.csv", novos[nome])
    except (OSError, ValueError) as e:
        # A rodada que mais precisa de registro é justamente a que morreu no meio.
        _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas, duplicadas,
                      falha=str(e))
        raise
    log = _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas, duplicadas)
    return {"gravadas": gravadas, "duplicadas": duplicadas, "log": log}


def _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas, duplicadas,
                  falha: str = "") -> Path:
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
    # Regra morta neste documento é sintoma fraco (mapa real tem uma regra por tipo de evento e
    # um mês aciona duas ou três), então não vira aviso gritado em toda rodada. Mas some se não
    # ficar em lugar nenhum: o log é o registro durável onde ela pode ser auditada depois.
    acertos = "; ".join(f"regra {i}: {c}" for i, c in sorted(res.acertos.items())) or "nenhuma regra"
    sem_uso = [i for i, c in sorted(res.acertos.items()) if c == 0]
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
        f"Linhas ignoradas: {[n for n, _ in res.ignoradas] or 'nenhuma'}\n\n"
        f"Acertos por regra de `linhas`: {acertos}\n\n"
        f"Regras que nunca casaram: {sem_uso or 'nenhuma'}\n\n"
        f"Conciliação: {conciliacao}\n"
        + (f"\n**A gravação falhou no meio**: {falha}\n\nO que está na tabela acima chegou a ser "
           "gravado; o resto não. Rode de novo depois de resolver — a importação é idempotente.\n"
           if falha else ""),
        encoding="utf-8")
    return caminho


def conferir(raiz: str | Path, res: Resultado) -> tuple[list[str], bool]:
    """Compara o documento com dados/ sem gravar. (linhas de texto, houve divergência).

    Usa o MESMO `separar` da gravação, para que a prévia não possa prometer um número que a
    gravação não vai cumprir — foi o que acontecia quando cada um contava do seu jeito."""
    raiz = Path(raiz)
    existentes = _existentes(raiz)
    novos, duplicadas, conflitos = separar(existentes, res)
    linhas, divergiu = [], bool(conflitos)
    chave = CHAVES["posicoes"]
    atual = {chave(e): e for e in existentes["posicoes"]}
    contas_do_documento = {r["conta"] for r in res.registros["posicoes"]}
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
            divergiu = True
        else:
            linhas.append(f"  {r['ticker']} ({r['conta']}): OK — {r['qty']:g} @ {r['pm']:.2f}")
    for k, e in atual.items():
        # só as contas que ESTE documento cobre: posição de outra corretora não está faltando
        if k not in doc and e["conta"] in contas_do_documento:
            linhas.append(f"  {e['ticker']} ({e['conta']}): só em dados/ (ausente no documento)")
            divergiu = True
    for nome in ("fills", "proventos", "eventos"):
        if res.registros[nome]:
            linhas.append(f"  {nome}: {len(novos[nome])} nova(s), {duplicadas[nome]} já presente(s)")
    if not linhas:
        linhas.append("  nada a comparar: o documento não trouxe posição nem lançamento")
    return linhas, divergiu
