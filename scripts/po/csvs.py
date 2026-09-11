"""Schemas, leitura validada e escrita canônica dos 7 CSVs do workspace (spec §4).

Contrato: os CSVs canônicos são escritos por máquina, então número aceita SÓ
o formato canônico (-?d+(.d+)?, decimal com ponto, sem separador de milhar).
Formato humano/corretora (1.234,56) é assunto da ingestão, que converte ANTES
de gravar aqui (po.numeros.parse_valor). Campos NUMERICOS voltam como float
nas linhas retornadas: a conversão string→número acontece em um lugar só.
Se erros != [], não consuma linhas.

validar_linha é a régua única: ler_csv a aplica ao que vem de arquivo e a
ingestão a aplica ao que vem de parser, antes de gravar.
"""
import csv
import datetime
import math
import re
from pathlib import Path

from po.numeros import formatar_canonico

SCHEMAS = {
    "posicoes": ["ticker", "classe", "conta", "qty", "pm", "moeda"],
    "cotacoes": ["data", "hora", "ticker", "preco", "moeda", "fonte"],
    "fills": ["data", "ticker", "tipo", "qty", "preco", "taxa", "conta", "moeda"],
    "proventos": ["data", "ticker", "cnpj", "tipo", "valor_bruto", "valor_liquido", "conta", "moeda"],
    "eventos": ["data", "ticker", "tipo", "razao", "confirmado"],
    "indices": ["data", "indice", "valor", "fonte"],
    # Movimentação de caixa (entrada e saída), de provider de open finance ou digitada à mão.
    # `valor` carrega o SINAL: gasto é negativo, receita é positiva — ao contrário de qty e
    # preço, onde sinal é erro. `data_referencia` é a data que o PROVIDER declara para o dado,
    # distinta de `data` (quando o lançamento ocorreu) e da data em que a importação rodou.
    # `id_externo` é a chave de dedup em reimportação (junto com `origem`, ver check_dados):
    # sem ela, reconhecer que a mesma movimentação já entrou dependeria de heurística frágil.
    "movimentacoes": ["data", "descricao", "valor", "moeda", "conta",
                      "categoria_origem", "origem", "id_externo", "data_referencia"],
}
NUMERICOS = {"qty", "pm", "preco", "taxa", "valor_bruto", "valor_liquido", "valor"}
CLASSES = {"acoes-br", "fiis", "rv-int", "reits-us", "rf-br", "cripto", "caixa", "commodities"}
MOEDAS = {"BRL", "USD", "EUR"}
TIPOS_FILL = {"compra", "venda", "saldo-inicial"}
TIPOS_PROVENTO = {"dividendo", "jcp", "rendimento", "juros", "outro"}
TIPOS_EVENTO = {"split", "grupamento", "bonificacao", "subscricao", "fusao", "cisao",
                "variacao-anomala", "outro"}
CONFIRMADO = {"sim", "nao"}
INDICES = {"ibov", "sp500", "usdbrl", "cdi", "ipca", "selic"}
FONTES_COTACAO = {"yahoo", "brapi", "bcb-sgs", "manual", "definicao"}   # registry de providers + manual
# definicao: valor que decorre da unidade (saldo em conta vale 1,00), não observação de mercado
# Providers de movimentação. Vocabulário fechado pelo mesmo motivo de FONTES_COTACAO: origem
# é procedência, e procedência que aceita texto livre não é procedência.
# Hoje só existe entrada manual. Cada provider entra aqui no commit que traz o adaptador dele,
# com o teste-ponte no molde do de FONTES_COTACAO (test_registry_fecha_com_o_vocabulario_de_fonte).
# Previstos: finnest (Task 9+), pluggy.
ORIGENS_MOVIMENTACAO = {"manual"}
VOCABULARIOS = {
    ("posicoes", "classe"): CLASSES,
    ("fills", "tipo"): TIPOS_FILL,
    ("proventos", "tipo"): TIPOS_PROVENTO,
    ("eventos", "tipo"): TIPOS_EVENTO,
    ("eventos", "confirmado"): CONFIRMADO,
    ("indices", "indice"): INDICES,
    # Compartilha o vocabulário de cotacoes.fonte por conveniência; "definicao" não tem
    # sentido aqui (nenhum índice é definicional), só ainda não vale a pena um set separado.
    ("indices", "fonte"): FONTES_COTACAO,
    ("cotacoes", "fonte"): FONTES_COTACAO,
    ("movimentacoes", "origem"): ORIGENS_MOVIMENTACAO,
}


def em_vocabulario(valor, vocabulario) -> bool:
    """Pertinência segura: valor não-string (lista, dict, None) nunca levanta, só reprova.

    `x in <set>` chama hash(x), então um bloco YAML (`moeda:\n  - BRL`) derrubaria o
    validador com TypeError em vez de virar uma frase. Todo validador que confere um valor
    do usuário contra vocabulário fechado passa por aqui.
    """
    return isinstance(valor, str) and valor in vocabulario


DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
NUMERO_CANONICO = re.compile(r"^-?\d+(\.\d+)?$")
# Campos de texto que podem ficar vazios; todo o resto é obrigatório
OPCIONAIS = {
    "proventos": {"cnpj"},
    "eventos": {"razao"},
    # Provider pode devolver lançamento sem descrição ou sem categoria; isso não é erro de dado.
    # `categoria_origem` é texto livre DE PROPÓSITO (spec §6.2): categorizar gasto é julgamento,
    # e congelar taxonomia agora faria o motor herdar a opinião do primeiro fornecedor.
    "movimentacoes": {"descricao", "categoria_origem"},
}


def validar_linha(nome: str, linha: dict, onde: str) -> list[str]:
    """Valida UMA linha (dict com todos os campos do schema). NUMERICOS em string
    canônica são convertidos in-place para float; int/float passam (int vira float),
    não-finito é erro; campo de texto exige str. Chaves extras (ex.: '_linha') são ignoradas.

    Convenção de nome: campo chamado exatamente `data` OU com prefixo `data_` (ex.:
    `data_referencia`) é validado como data canônica YYYY-MM-DD. Schema novo não deve usar
    esse prefixo em campo que carregue outra coisa (datetime, timestamp de provider etc.) —
    a validação de data reprovaria em silêncio para quem não leu este trecho."""
    schema = SCHEMAS[nome]
    faltam = [c for c in schema if c not in linha]
    if faltam:
        raise ValueError(f"{onde}: linha sem os campos {faltam} do schema de {nome}")
    opcionais = OPCIONAIS.get(nome, set())
    erros = []
    for campo in schema:
        valor = linha[campo]
        if campo in NUMERICOS and isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if not math.isfinite(valor):
                erros.append(f"{onde}: campo {campo} não finito ({valor!r})")
            else:
                linha[campo] = float(valor)
            continue
        if valor is None:
            valor = ""
        if not isinstance(valor, str):
            erros.append(f"{onde}: campo {campo} deve ser texto, veio {type(valor).__name__}")
            continue
        if valor != valor.strip():
            erros.append(f"{onde}: campo {campo} com espaço nas bordas: {valor!r}")
        if not valor:
            if campo not in opcionais:
                erros.append(f"{onde}: campo {campo} vazio")
            continue
        if campo in NUMERICOS:
            if not NUMERO_CANONICO.match(valor):
                erros.append(
                    f"{onde}: campo {campo} fora do formato canônico "
                    f"(decimal com ponto, sem milhar): {valor!r}")
            else:
                linha[campo] = float(valor)
        elif campo == "data" or campo.startswith("data_"):
            if not DATA_RE.match(valor):
                erros.append(f"{onde}: data deve ser YYYY-MM-DD: {valor!r}")
            else:
                try:
                    datetime.date.fromisoformat(valor)
                except ValueError:
                    erros.append(f"{onde}: data impossível no calendário: {valor!r}")
        elif campo == "hora":
            if not HORA_RE.match(valor):
                erros.append(f"{onde}: hora deve ser HH:MM (24h): {valor!r}")
        elif campo == "moeda":
            if not em_vocabulario(valor, MOEDAS):
                erros.append(f"{onde}: moeda {valor!r} fora do vocabulário {sorted(MOEDAS)}")
        vocab = VOCABULARIOS.get((nome, campo))
        if vocab is not None and not em_vocabulario(valor, vocab):
            erros.append(f"{onde}: {campo} {valor!r} fora do vocabulário {sorted(vocab)}")
    if nome == "fills" and isinstance(linha["qty"], float) and linha["qty"] <= 0:
        erros.append(f"{onde}: qty de fill deve ser positiva (venda usa tipo=venda, não sinal)")
    if nome == "posicoes" and isinstance(linha["qty"], float) and linha["qty"] <= 0:
        erros.append(f"{onde}: qty de posição deve ser positiva (v1 não admite short)")
    if nome == "cotacoes" and isinstance(linha["preco"], float) and linha["preco"] <= 0:
        # Cada provider já barra preço <= 0 na borda (é o que o Yahoo devolve para ativo parado),
        # mas a régua única não barrava: preço 0 zerava o bloco e preço negativo dava patrimônio
        # negativo com percentual de -100%, tudo com o validador verde.
        pista = ("cotação zerada é o que a fonte devolve para ativo parado, não um preço"
                 if linha["preco"] == 0 else "preço negativo não existe; confira o sinal da linha")
        erros.append(f"{onde}: preço deve ser positivo (veio {linha['preco']:g}) — {pista}")
    if nome == "indices" and isinstance(linha["valor"], float) and linha["valor"] <= 0:
        erros.append(f"{onde}: valor de índice deve ser positivo (veio {linha['valor']:g})")
    if nome == "proventos":
        bruto, liquido = linha["valor_bruto"], linha["valor_liquido"]
        if isinstance(bruto, float) and isinstance(liquido, float):
            # Líquido é bruto menos retenção: mesmo sinal e nunca maior em módulo. Sem isto, um
            # ajuste de imposto com um dígito a mais (-15,30 no lugar de -1,53 sobre um dividendo
            # de 5,10) grava provento líquido NEGATIVO e a conciliação declara a linha conferida,
            # porque ela compara valor_bruto com a mesma célula de onde valor_bruto saiu.
            if bruto * liquido < 0:
                erros.append(f"{onde}: valor_liquido {liquido:g} tem sinal oposto ao valor_bruto "
                             f"{bruto:g} — retenção não inverte o sinal de um provento; confira o "
                             "ajuste de imposto do documento")
            elif abs(liquido) > abs(bruto) + 1e-9:
                erros.append(f"{onde}: valor_liquido {liquido:g} maior que valor_bruto {bruto:g} "
                             "em módulo — líquido é bruto menos retenção, nunca mais")
    return erros


def ler_csv(nome: str, caminho: str | Path) -> tuple[list[dict], list[str]]:
    """Lê um CSV canônico. Retorna (linhas, erros); NUMERICOS já convertidos a float."""
    schema = SCHEMAS[nome]
    caminho = Path(caminho)
    erros = []
    try:
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != schema:
                return [], [f"{caminho.name}: header {reader.fieldnames} difere do schema (esperado: {schema})"]
            linhas = list(reader)
    except UnicodeDecodeError:
        return [], [f"{caminho.name}: não é UTF-8 válido — salve o arquivo como UTF-8"]
    except csv.Error as e:
        return [], [f"{caminho.name}: CSV ilegível ({e}) — confira encoding e formato"]
    for i, linha in enumerate(linhas, start=2):
        onde = f"{caminho.name}:{i}"
        extras = linha.pop(None, None)
        if extras:
            erros.append(f"{onde}: linha com colunas a mais ({len(extras)} valor(es) além do schema)")
        faltantes = [c for c in schema if linha[c] is None]
        if faltantes:
            erros.append(f"{onde}: linha com colunas a menos (faltam: {', '.join(faltantes)})")
            continue
        erros.extend(validar_linha(nome, linha, onde))
    return linhas, erros


def _quando(c: dict) -> tuple[str, str]:
    """(data, hora) para ordenar. `hora` ausente vira "" — linha de ler_csv sempre tem, mas quem
    monta dict à mão não deve receber KeyError de uma função de ordenação."""
    return (c["data"], c.get("hora") or "")


def ultimas_cotacoes(cotacoes: list[dict]) -> dict[str, dict]:
    """Cotação vencedora por ticker: a de (DATA, HORA) mais recente; empate, a última linha do
    arquivo. `hora` entra no desempate porque ela é validada e gravada em toda linha: comparar só a
    data escolheria em silêncio a cotação das 09:00 sobre a das 18:00 do mesmo dia no primeiro
    backfill, reordenação ou importação de série histórica.
    Pré-condição: linhas saídas de ler_csv sem erros (comparação textual, exige ISO e HH:MM)."""
    melhor = {}
    for c in cotacoes:
        atual = melhor.get(c["ticker"])
        if atual is None or _quando(c) >= _quando(atual):
            melhor[c["ticker"]] = c
    return melhor


def _celula(campo: str, valor) -> str:
    """Célula canônica. Número vai por formatar_canonico; texto em campo numérico só passa se já
    for canônico (ninguém contorna o 'único caminho' entregando '1.234,56' como string)."""
    if isinstance(valor, bool):
        raise ValueError(f"campo {campo}: booleano não é valor canônico")
    if isinstance(valor, (int, float)):
        return formatar_canonico(float(valor))
    texto = "" if valor is None else str(valor)
    if campo in NUMERICOS and texto and not NUMERO_CANONICO.match(texto):
        raise ValueError(f"campo {campo}: {texto!r} não está no formato canônico — passe número (float), não texto humano")
    return texto


def anexar_csv(nome: str, caminho: str | Path, linhas: list[dict]) -> int:
    """Anexa linhas (dict com todos os campos do schema; número float/int ou str canônica).
    Único writer dos CSVs canônicos: valida cada linha (validar_linha, em cópia), formata TODAS
    as células e confere o header do arquivo existente ANTES de abrir para escrita — erro nunca
    deixa arquivo pela metade. Cria com header se não existir (ou só tem BOM). Lista vazia não
    toca o disco. Nunca reescreve o que já está lá."""
    schema = SCHEMAS[nome]
    caminho = Path(caminho)
    if not linhas:
        return 0
    erros = []
    for i, linha in enumerate(linhas, start=1):
        erros.extend(validar_linha(nome, dict(linha), f"{caminho.name}: linha nova {i}"))
    if erros:
        raise ValueError("nada gravado — " + "; ".join(erros))
    prontas = [[_celula(campo, linha[campo]) for campo in schema] for linha in linhas]
    novo, precisa_quebra = True, False
    if caminho.exists():
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            primeira = f.readline()
        if primeira.strip():
            novo = False
            header = next(csv.reader([primeira]))
            if header != schema:
                raise ValueError(f"{caminho.name}: header {header} difere do schema (esperado: {schema}) "
                                 "— não é o CSV canônico esperado, nada gravado")
            with caminho.open("rb") as f:
                f.seek(-1, 2)
                precisa_quebra = f.read(1) != b"\n"
    with caminho.open("a", encoding="utf-8", newline="") as f:
        if precisa_quebra:
            f.write("\n")
        w = csv.writer(f, lineterminator="\n")
        if novo:
            w.writerow(schema)
        w.writerows(prontas)
    return len(prontas)
