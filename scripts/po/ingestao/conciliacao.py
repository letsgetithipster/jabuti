"""Conciliação declarada: o documento prova a própria aritmética antes de qualquer gravação.

Três tipos (vocabulário fechado, decisão 8):
- saldo-corrente: saldo[i] = saldo[i-1] + valor[i], linha a linha, sobre TODAS as linhas
  do documento (ordem crescente ou decrescente declarada). Linha com saldo e sem valor é
  âncora: só a primeira da cadeia pode trazer saldo novo (é a abertura); âncora no meio
  tem que repetir o saldo anterior, senão é salto sem lançamento que o explique.
- valor-da-linha: fills: |valor| = qty × preço + taxa (compra) ou − taxa (venda);
  proventos: valor_bruto (ou valor_liquido, declarado) = |valor| quando a linha traz valor.
- total-declarado: soma de um campo (ou campo*campo) dos registros = total do documento
  (linha de total) ou --total-declarado digitado pelo usuário.
"""
from po.ingestao.engine import Resultado
from po.ingestao.leitores import Tabela
from po.numeros import parse_valor

TOL = 0.011           # um centavo, com folga de ponto flutuante
ROUNDING_POR_UNIDADE = 0.005   # meia casa: quanto um preço exibido com 2 decimais pode estar errado
# Política de tolerância, decidida em vez de descoberta: um centavo é a medida certa para
# `valor-da-linha` e `saldo-corrente`, que comparam UMA quantia contra outra quantia do mesmo
# documento. É a medida errada para `total-declarado` com soma de produto (qty*pm): a corretora
# exibe o PM com 2 casas mas calcula o total com o PM cheio, então o erro cresce com a
# quantidade — 300 posições de 1.000 ações erram até R$ 1.500 sem que nada esteja errado. Ali o
# default escala com a soma do primeiro fator.
# Isso são DEFAULTS. Qualquer mapeamento, de qualquer um dos três tipos, declara a sua própria
# em `conciliacao.tolerancia` e justifica o número em `observacoes` — inclusive para apertar: o
# default de total-declarado é o limite teórico, largo o bastante para uma posição inteira de
# R$ 1.200 sumir sem acusar, que é justamente o que total-declarado existe para pegar.


def _motivos_fora(mapa: dict) -> set[str]:
    """Motivos das regras marcadas `fora-da-cadeia: true`. O elo entre regra e linha é o motivo,
    porque é o que `res.ignoradas` carrega; motivo é obrigatório em `ignorar`, então sempre existe."""
    return {r["motivo"] for r in mapa["linhas"]
            if r.get("fora-da-cadeia") and r.get("destino") == "ignorar" and r.get("motivo")}


def _tolerancia(conc: dict, padrao: float = TOL,
                porque: str = "um centavo, com folga de ponto flutuante") -> tuple[float, str]:
    """(tolerância, por quê). A declarada no mapeamento vence o default do tipo de conciliação."""
    declarada = conc.get("tolerancia")
    if declarada is not None:
        return float(declarada), "declarada no mapeamento"
    return padrao, porque


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

    tol, porque_tol = _tolerancia(conc)

    if tipo == "saldo-corrente":
        if conc["valor"] not in idx or conc["saldo"] not in idx:
            faltando = [k for k in (conc["valor"], conc["saldo"]) if k not in idx]
            return [f"conciliacao: apelido(s) {faltando} não estão no cabeçalho do documento"], ""
        i_valor, i_saldo = idx[conc["valor"]], idx[conc["saldo"]]
        ignoradas = {n for n, _ in res.ignoradas}
        # `ignorar` significa "não vira registro", não "não conta na aritmética": um rodapé de saldo
        # disponível ou bloqueado dentro da tabela é forma comum em extrato brasileiro e mostra um
        # saldo que não pertence à cadeia. Sem escotilha, a única saída era subir a tolerância até
        # engolir o salto — o que desliga a conferência do documento inteiro. `fora-da-cadeia: true`
        # na regra é a saída explícita, e vale só em `ignorar`.
        fora_da_cadeia = {n for n, motivo in res.ignoradas if motivo in _motivos_fora(mapa)}
        pontos, ancoras = [], 0
        for i, linha in enumerate(tabela.linhas):
            n = tabela.numero_da_linha(i)
            v, s = _num(linha[i_valor]), _num(linha[i_saldo])
            if n in fora_da_cadeia:
                continue
            if s is None:
                if n in ignoradas and v is None:
                    continue      # linha que o mapa descartou e não move saldo: fora da cadeia
                erros.append(f"linha {n}: saldo ilegível para conciliação ({linha[i_saldo]!r}) — "
                             "sem ele a cadeia de saldos não fecha")
                continue
            if v is None:         # SALDO ANTERIOR e afins: ancoram a cadeia, não têm par a conferir
                ancoras += 1
            pontos.append((n, v, s))
        if conc.get("ordem", "crescente") == "decrescente":
            pontos.reverse()
        pares = 0
        for (n_ant, _, s_ant), (n, v, s) in zip(pontos, pontos[1:]):
            if v is None:
                # Âncora fora do início da cadeia. A primeira linha pode trazer um saldo do nada
                # (é a abertura, e não há elo anterior para conferir); da segunda em diante, uma
                # linha sem valor não pode mover o saldo — se move, há lançamento fora do
                # documento, e sem esta conferência o salto passaria limpo.
                if abs(s - s_ant) > tol:
                    erros.append(f"linha {n}: âncora sem valor com saldo {s:.2f} ≠ saldo anterior "
                                 f"(linha {n_ant}) {s_ant:.2f} — salto de {abs(s - s_ant):.2f} sem "
                                 "lançamento que o explique (só a primeira linha da cadeia abre saldo)")
                continue
            esperado = s_ant + v
            if abs(esperado - s) > tol:
                erros.append(f"linha {n}: saldo {s:.2f} ≠ saldo anterior (linha {n_ant}) {s_ant:.2f} "
                             f"+ valor {v:.2f} = {esperado:.2f}")
            pares += 1
        extra = f", {ancoras} âncora(s) sem valor" if ancoras else ""
        if pares == 0:
            if res.linhas_lidas == 0:
                return erros, "saldo-corrente: documento sem linhas — nada a conciliar (no-op)"
            erros.append(f"saldo-corrente não conferiu par nenhum ({len(pontos)} linha(s) com saldo"
                         f"{extra}) — o documento não provou a própria aritmética")
        return erros, (f"saldo-corrente: {pares} par(es) de linhas conferidos{extra}, "
                       f"tolerância {tol:g} ({porque_tol})")

    if tipo == "valor-da-linha":
        campo_prov = conc.get("proventos", "valor_bruto")
        # Uma linha de provento cujo `campo_prov` é literalmente "{valor}" não prova nada: os dois
        # lados da comparação saem da MESMA célula do documento. Contá-la como conferida faz o texto
        # afirmar prova que não houve, e foi assim que um dividendo líquido negativo passou com
        # "4 linha(s) conferidas". Elas viram uma contagem própria, honesta sobre o que são.
        tautologicas = {i for i, regra in enumerate(mapa["linhas"], start=1)
                        if regra.get("destino") == "proventos"
                        and (regra.get("campos") or {}).get(campo_prov) == "{valor}"}
        conferidas, sem_valor, declaradas = 0, 0, 0
        for f in res.registros["fills"]:
            if f["tipo"] == "saldo-inicial":
                continue
            declarado = _num(res.contextos[f["_linha"]].get("valor"))
            if declarado is None:
                erros.append(f"linha {f['_linha']}: fill sem valor declarado na coluna {mapa['colunas']['valor']!r}")
                continue
            sinal = 1 if f["tipo"] == "compra" else -1
            esperado = f["qty"] * f["preco"] + sinal * f["taxa"]
            if abs(abs(declarado) - esperado) > tol:
                erros.append(f"linha {f['_linha']}: {f['ticker']} {f['tipo']} qty {f['qty']:g} × preço {f['preco']:g} "
                             f"{'+' if sinal > 0 else '−'} taxa {f['taxa']:g} = {esperado:.2f} "
                             f"≠ valor declarado {abs(declarado):.2f}")
            conferidas += 1
        for p in res.registros["proventos"]:
            declarado = _num(res.contextos[p["_linha"]].get("valor"))
            if declarado is None:
                sem_valor += 1     # o documento não declarou valor nessa linha: nada a provar
                continue
            if p.get("_regra") in tautologicas:
                declaradas += 1
                continue
            if abs(abs(declarado) - p[campo_prov]) > tol:
                erros.append(f"linha {p['_linha']}: {p['ticker']} {p['tipo']} {campo_prov} {p[campo_prov]:.2f} "
                             f"≠ valor declarado {abs(declarado):.2f}")
            conferidas += 1
        fora = f", {sem_valor} sem valor declarado" if sem_valor else ""
        fora += (f", {declaradas} provento(s) apenas transcrito(s) do documento (sem prova "
                 "independente: o valor gravado É a célula)") if declaradas else ""
        if conferidas == 0 and declaradas and not sem_valor:
            erros.append("valor-da-linha não conferiu linha nenhuma: todo provento deste mapeamento "
                         "copia o valor da mesma coluna que a conciliação leria. Declare "
                         "conciliacao.tipo: saldo-corrente, ou aponte proventos para um campo que o "
                         "documento calcule (ex.: valor_liquido, quando há coluna de imposto)")
        return erros, (f"valor-da-linha: {conferidas} linha(s) conferidas{fora}, "
                       f"tolerância {tol:g} ({porque_tol})")

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
    soma, escala = 0.0, 0.0
    fator = conc["soma"].split("*")[0].strip() if "*" in conc["soma"] else None
    for regs in res.registros.values():
        for r in regs:
            try:
                soma += _soma_do_registro(r, conc["soma"])
                if fator:
                    escala += abs(float(r[fator]))
            except (KeyError, TypeError, ValueError):
                continue   # tabela sem esses campos não entra na soma
    if fator:
        tolerancia, porque = _tolerancia(
            conc, max(TOL, ROUNDING_POR_UNIDADE * escala),
            f"arredondamento de {conc['soma'].split('*')[1].strip()} a 2 casas sobre {escala:g} de {fator}")
    else:
        tolerancia, porque = _tolerancia(conc)
    if abs(soma - total) > tolerancia:
        erros.append(f"soma de {conc['soma']} nos registros = {soma:.2f} ≠ total declarado {total:.2f} "
                     f"({de}); diferença {abs(soma - total):.2f} passa da tolerância {tolerancia:g} ({porque})")
    return erros, (f"total-declarado: soma {soma:.2f} contra {total:.2f} ({de}), "
                   f"diferença {abs(soma - total):.2f} dentro da tolerância {tolerancia:g} ({porque})")
