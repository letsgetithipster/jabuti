"""Engine da ingestão: aplica um mapeamento a uma Tabela crua e produz registros canônicos.

Não grava nada. Toda linha do documento termina em exatamente um destino (tabela,
ignorar ou ajuste): linha que não casa regra nenhuma é ERRO, nunca descarte silencioso.
Registros saem validados pela mesma régua do ler_csv (validar_linha) e carregam
'_linha' (número no documento) para mensagens e conciliação; posições carregam
'_data' (data do documento ou --data) para o saldo-inicial da escrita.
"""
import re
from dataclasses import dataclass, field

from po.csvs import NUMERICOS, OPCIONAIS, SCHEMAS, validar_linha
from po.datas import parse_data
from po.ingestao.leitores import Tabela
from po.ingestao.mapeamento import DESTINOS_TABELA, TOKEN
from po.numeros import parse_valor


@dataclass
class Resultado:
    registros: dict[str, list[dict]] = field(default_factory=lambda: {t: [] for t in sorted(DESTINOS_TABELA)})
    contextos: dict[int, dict] = field(default_factory=dict)     # nº da linha no documento -> ctx
    ignoradas: list[tuple[int, str]] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    linhas_lidas: int = 0
    acertos: dict[int, int] = field(default_factory=dict)   # regra (1-based) -> linhas que casaram

    @property
    def classificadas(self) -> int:
        return sum(len(v) for v in self.registros.values())


def _resumo(linha: list) -> str:
    texto = " | ".join(str(c) for c in linha if str(c).strip())
    return texto[:80] + ("…" if len(texto) > 80 else "")


def _vazio(valor) -> bool:
    return valor is None or str(valor).strip() == ""


def _resolver(template, ctx: dict):
    """Template: literal, '{apelido}', '{apelido|padrão}' ou texto com tokens."""
    if not isinstance(template, str):
        return template
    m = TOKEN.fullmatch(template)
    if m:
        valor = ctx.get(m.group(1))
        if _vazio(valor):
            return m.group(2) if m.group(2) is not None else valor
        return valor
    return TOKEN.sub(lambda mm: (mm.group(2) or "") if _vazio(ctx.get(mm.group(1))) else str(ctx[mm.group(1)]), template)


def _converter(campo: str, valor, datas: dict) -> tuple[object, str | None]:
    """Converte o valor resolvido para o tipo do campo. Retorna (valor, erro)."""
    if campo in NUMERICOS:
        if isinstance(valor, bool):
            return None, f"{campo} não numérico: {valor!r}"
        if isinstance(valor, (int, float)):
            return float(valor), None
        num = parse_valor(str(valor)) if valor is not None else None
        if num is None:
            return None, f"{campo} não numérico: {valor!r}"
        return num, None
    if campo == "data":
        d = parse_data(valor, datas.get("formatos", []), datas.get("extrair"))
        if d is None:
            return None, f"data ilegível: {valor!r} (formatos: {datas.get('formatos')})"
        return d.isoformat(), None
    return ("" if valor is None else str(valor).strip()), None


def _data_da_linha(ctx: dict, indices: dict, datas: dict, data_padrao: str | None):
    """Data da linha: da coluna do documento (formatos do mapeamento) ou do --data, que o
    usuário digita já em ISO e por isso NÃO passa pelos formatos do documento."""
    if "data" in indices:
        return _converter("data", ctx.get("data"), datas)
    if _vazio(data_padrao):
        return None, "este documento não traz data — passe --data AAAA-MM-DD"
    return _converter("data", data_padrao, {"formatos": ["%Y-%m-%d"]})


def executar(mapa: dict, tabela: Tabela, *, conta: str | None = None, data_padrao: str | None = None) -> Resultado:
    """Aplica o mapeamento. conta sobrepõe mapa['conta']; data_padrao supre documentos sem coluna de data."""
    res = Resultado(linhas_lidas=len(tabela.linhas))
    conta = conta or mapa["conta"]
    moeda = mapa["moeda"]
    datas = mapa.get("datas") or {}
    indices = {}
    for apelido, nome_col in mapa["colunas"].items():
        if nome_col not in tabela.cabecalho:
            res.erros.append(f"coluna {nome_col!r} (apelido {apelido}) não encontrada no cabeçalho: {tabela.cabecalho}")
        else:
            indices[apelido] = tabela.cabecalho.index(nome_col)
    duplicadas = {nome for nome in tabela.cabecalho
                  if nome and tabela.cabecalho.count(nome) > 1 and nome in mapa["colunas"].values()}
    for nome in sorted(duplicadas):
        posicoes = [i for i, c in enumerate(tabela.cabecalho) if c == nome]
        res.erros.append(f"coluna {nome!r} aparece {len(posicoes)} vezes no cabeçalho (posições {posicoes}) "
                         "e o mapeamento a referencia — renomeie no documento ou aponte outra coluna")
    for i, linha in enumerate(tabela.linhas):
        if len(linha) > len(tabela.cabecalho):
            res.erros.append(f"linha {tabela.numero_da_linha(i)}: {len(linha)} células para "
                             f"{len(tabela.cabecalho)} colunas do cabeçalho — o cabeçalho foi achado "
                             "na linha errada?")
            break
    if res.erros:
        return res
    extrair = {ap: re.compile(rx) for ap, rx in (mapa.get("extrair") or {}).items()}
    regras = [(regra, {ap: re.compile(rx) for ap, rx in regra["quando"].items()}) for regra in mapa["linhas"]]
    res.acertos = {i: 0 for i in range(1, len(regras) + 1)}
    ajustes = []

    for i, linha in enumerate(tabela.linhas):
        n = tabela.numero_da_linha(i)
        ctx = {ap: linha[idx] for ap, idx in indices.items()}
        for ap, rx in extrair.items():
            m = rx.search(str(ctx.get(ap, "")))
            if m:
                ctx.update({k: v for k, v in m.groupdict().items() if v is not None})
        escolhida = None
        for ordem, (regra, padroes) in enumerate(regras, start=1):
            grupos, ok = {}, True
            for ap, rx in padroes.items():
                m = rx.search(str(ctx.get(ap, "")))
                if not m:
                    ok = False
                    break
                grupos.update({k: v for k, v in m.groupdict().items() if v is not None})
            if ok:
                ctx.update(grupos)
                escolhida, ordem_escolhida = regra, ordem
                res.acertos[ordem] = res.acertos.get(ordem, 0) + 1
                break
        if escolhida is None:
            res.erros.append(f"linha {n}: não classificada por nenhuma regra — {_resumo(linha)}")
            continue
        res.contextos[n] = ctx
        destino = escolhida["destino"]
        if destino == "ignorar":
            res.ignoradas.append((n, escolhida["motivo"]))
            continue
        if destino == "ajuste":
            ajustes.append((n, escolhida, ctx))
            continue
        # `_regra` deixa a conciliação saber de qual regra o registro veio, para não
        # contar como "conferida" a linha cujo campo saiu da mesma célula que ela compara.
        registro = {"_linha": n, "_regra": ordem_escolhida}
        campos = escolhida.get("campos") or {}
        falhou = False
        for campo in SCHEMAS[destino]:
            if campo in campos:
                bruto = _resolver(campos[campo], ctx)
            elif campo == "data":
                valor, erro = _data_da_linha(ctx, indices, datas, data_padrao)
                if erro:
                    res.erros.append(f"linha {n}: {erro}")
                    falhou = True
                    break
                registro[campo] = valor
                continue
            elif campo == "conta":
                bruto = conta
            elif campo == "moeda":
                bruto = moeda
            elif campo in ctx:
                bruto = ctx[campo]
            elif campo in OPCIONAIS.get(destino, set()):
                bruto = ""
            else:
                res.erros.append(f"linha {n}: campo {campo} de {destino} não mapeado (declare em campos)")
                falhou = True
                break
            valor, erro = _converter(campo, bruto, datas)
            if erro:
                res.erros.append(f"linha {n}: {erro}")
                falhou = True
                break
            registro[campo] = valor
        if falhou:
            continue
        if destino == "posicoes":
            valor, erro = _data_da_linha(ctx, indices, datas, data_padrao)
            if erro:
                res.erros.append(f"linha {n}: posições exigem a data do documento — {erro}")
                continue
            registro["_data"] = valor
        errs = validar_linha(destino, registro, f"linha {n}")
        if errs:
            res.erros.extend(errs)
        else:
            res.registros[destino].append(registro)

    for n, regra, ctx in ajustes:
        alvo = regra["aplica-em"]
        campo = regra.get("campo", "valor_liquido")
        chave, falhou = {}, False
        for c in regra["chave"]:
            valor, erro = _converter(c, ctx.get(c), datas)
            if erro:
                res.erros.append(f"linha {n}: ajuste com {erro}")
                falhou = True
                break
            chave[c] = valor
        if falhou:
            continue
        quantia, erro = _converter(campo, _resolver(regra["valor"], ctx), datas)
        if erro:
            res.erros.append(f"linha {n}: ajuste com {erro}")
            continue
        alvos = [r for r in res.registros[alvo] if all(r.get(c) == v for c, v in chave.items())]
        if len(alvos) != 1:
            res.erros.append(f"linha {n}: ajuste sem linha principal única em {alvo} para {chave} "
                             f"(encontradas: {len(alvos)})")
            continue
        alvos[0][campo] = round(alvos[0][campo] + quantia, 8)   # 8 = precisão canônica do projeto
        # O registro já tinha passado pelo validar_linha antes do ajuste; depois do ajuste ele
        # pode ter saído da regra (qty de fill zerada por estorno, por exemplo). Sem reconferir,
        # o erro só apareceria lá no anexar_csv, como exceção e sem a linha do documento.
        res.erros.extend(validar_linha(alvo, dict(alvos[0]), f"linha {n}: depois do ajuste"))
    # A regra "nenhuma linha some em silêncio" é o que sustenta a ingestão agnóstica de
    # corretora: sem parser por corretora, um tipo de lançamento que o mapa não menciona só é
    # detectável aqui. Até agora ela valia por inspeção do fluxo; esta conta a torna verificada.
    com_erro = {int(m.group(1)) for e in res.erros
                if (m := re.match(r"linha (\d+):", e))}
    contadas = res.classificadas + len(res.ignoradas) + len(ajustes) + len(com_erro - _linhas_de_ajuste(ajustes))
    if contadas != res.linhas_lidas:
        res.erros.append(f"erro interno da ingestão: {res.linhas_lidas} linhas lidas mas "
                         f"{contadas} classificadas — alguma linha se perdeu, não grave nada")
    return res


def _linhas_de_ajuste(ajustes: list) -> set:
    return {n for n, _, _ in ajustes}
