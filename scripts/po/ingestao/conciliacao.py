"""Conciliação declarada: o documento prova a própria aritmética antes de qualquer gravação.

Três tipos (vocabulário fechado, decisão 8):
- saldo-corrente: saldo[i] = saldo[i-1] + valor[i], linha a linha, sobre TODAS as linhas
  do documento (ordem crescente ou decrescente declarada).
- valor-da-linha: fills: |valor| = qty × preço + taxa (compra) ou − taxa (venda);
  proventos: valor_bruto (ou valor_liquido, declarado) = |valor| quando a linha traz valor.
- total-declarado: soma de um campo (ou campo*campo) dos registros = total do documento
  (linha de total) ou --total-declarado digitado pelo usuário.
"""
from po.ingestao.engine import Resultado
from po.ingestao.leitores import Tabela
from po.numeros import parse_valor

TOL = 0.011  # um centavo, com folga de ponto flutuante


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return parse_valor(str(v))


def _soma_do_registro(registro: dict, soma: str) -> float:
    if "*" in soma:
        a, b = (s.strip() for s in soma.split("*", 1))
        return float(registro[a]) * float(registro[b])
    return float(registro[soma])


def conciliar(mapa: dict, tabela: Tabela, res: Resultado,
              total_declarado: float | None = None) -> tuple[list[str], str]:
    """Retorna (erros, descrição do que foi conferido). Chamar só com res.erros vazio."""
    conc = mapa["conciliacao"]
    tipo = conc["tipo"]
    idx = {ap: tabela.cabecalho.index(nome) for ap, nome in mapa["colunas"].items() if nome in tabela.cabecalho}
    erros = []

    if tipo == "saldo-corrente":
        i_valor, i_saldo = idx[conc["valor"]], idx[conc["saldo"]]
        pontos = []
        for i, linha in enumerate(tabela.linhas):
            n = tabela.numero_da_linha(i)
            v, s = _num(linha[i_valor]), _num(linha[i_saldo])
            if v is None or s is None:
                erros.append(f"linha {n}: valor ou saldo ilegível para conciliação "
                             f"({linha[i_valor]!r}, {linha[i_saldo]!r})")
                continue
            pontos.append((n, v, s))
        if conc.get("ordem", "crescente") == "decrescente":
            pontos.reverse()
        pares = 0
        for (n_ant, _, s_ant), (n, v, s) in zip(pontos, pontos[1:]):
            esperado = s_ant + v
            if abs(esperado - s) > TOL:
                erros.append(f"linha {n}: saldo {s:.2f} ≠ saldo anterior (linha {n_ant}) {s_ant:.2f} "
                             f"+ valor {v:.2f} = {esperado:.2f}")
            pares += 1
        return erros, f"saldo-corrente: {pares} par(es) de linhas conferidos"

    if tipo == "valor-da-linha":
        campo_prov = conc.get("proventos", "valor_bruto")
        conferidas = 0
        for f in res.registros["fills"]:
            if f["tipo"] == "saldo-inicial":
                continue
            declarado = _num(res.contextos[f["_linha"]].get("valor"))
            if declarado is None:
                erros.append(f"linha {f['_linha']}: fill sem valor declarado na coluna {mapa['colunas']['valor']!r}")
                continue
            sinal = 1 if f["tipo"] == "compra" else -1
            esperado = f["qty"] * f["preco"] + sinal * f["taxa"]
            if abs(abs(declarado) - esperado) > TOL:
                erros.append(f"linha {f['_linha']}: {f['ticker']} {f['tipo']} qty {f['qty']:g} × preço {f['preco']:g} "
                             f"{'+' if sinal > 0 else '−'} taxa {f['taxa']:g} = {esperado:.2f} "
                             f"≠ valor declarado {abs(declarado):.2f}")
            conferidas += 1
        for p in res.registros["proventos"]:
            declarado = _num(res.contextos[p["_linha"]].get("valor"))
            if declarado is None:
                continue
            if abs(abs(declarado) - p[campo_prov]) > TOL:
                erros.append(f"linha {p['_linha']}: {p['ticker']} {p['tipo']} {campo_prov} {p[campo_prov]:.2f} "
                             f"≠ valor declarado {abs(declarado):.2f}")
            conferidas += 1
        return erros, f"valor-da-linha: {conferidas} linha(s) conferidas"

    origem = conc["origem"]
    if origem == "flag":
        if total_declarado is None:
            return ["este mapeamento exige --total-declarado (o documento não traz linha de total)"], ""
        total, de = total_declarado, "--total-declarado"
    else:
        if origem["coluna"] not in idx:   # apelido, resolvido pelo bloco colunas do mapa
            return [f"conciliacao.origem.coluna {origem['coluna']!r} não é um apelido de colunas "
                    "presente no cabeçalho do documento"], ""
        i_col = idx[origem["coluna"]]
        total = None
        for linha in tabela.linhas:
            if any(str(c).strip() == origem["linha-contem"] for c in linha):
                total = _num(linha[i_col])
                break
        if total is None:
            return [f"linha de total contendo {origem['linha-contem']!r} não encontrada "
                    f"(ou valor ilegível na coluna {origem['coluna']!r})"], ""
        de = f"linha {origem['linha-contem']!r} do documento"
    soma = 0.0
    for regs in res.registros.values():
        for r in regs:
            try:
                soma += _soma_do_registro(r, conc["soma"])
            except (KeyError, TypeError, ValueError):
                continue   # tabela sem esses campos não entra na soma
    if abs(soma - total) > TOL:
        erros.append(f"soma de {conc['soma']} nos registros = {soma:.2f} ≠ total declarado {total:.2f} ({de})")
    return erros, f"total-declarado: soma {soma:.2f} contra {total:.2f} ({de})"
