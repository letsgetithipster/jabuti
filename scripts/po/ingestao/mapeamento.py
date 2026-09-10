"""Mapeamento documento → schema canônico: carga, validação e resolução por nome.

O mapeamento é DADO (YAML), o engine é código. Vocabulário fechado (chave fora daqui é
erro de validação, não é ignorada em silêncio — ver _desconhecidas):

  nome, versao (1), descricao, observacoes, verificado-contra-export-real (bool)
  detectar: {cabecalho-contem: [textos]}         # auto-seleção do mapeamento pelo cabeçalho
  arquivo: {formato: csv|xlsx, aba, encoding, delimitador, cabecalho-contem, fim-em-vazio}
  datas: {formatos: [strptime...], extrair: regex com 1 grupo (opcional)}
  conta: id da conta na config (o CLI --conta sobrescreve)
  moeda: BRL|USD|EUR
  colunas: {apelido: "Nome exato no cabeçalho"}   # apelido é escolha livre, não vocabulário fechado
  extrair: {apelido: regex com grupos nomeados}   # roda sobre o VALOR da coluna do apelido (que já
                                                   # existe em colunas), não sobre a linha inteira
  linhas: [ {quando: {apelido: regex}, destino: posicoes|fills|proventos|eventos|ignorar|ajuste,
             campos: {campo do schema: literal | "{apelido}" | "{apelido|padrão}"},
             motivo (ignorar) | aplica-em, campo, chave, valor (ajuste)} ]
  conciliacao: {tipo: saldo-corrente (valor, saldo, ordem)
                    | valor-da-linha (proventos: valor_bruto|valor_liquido)
                    | total-declarado (soma: campo | campo*campo; origem: flag | {linha-contem, coluna: apelido})}

Regras: primeira que casa vence; linha que não casa nenhuma é ERRO no engine. `quando` com mais
de um apelido é AND (todos têm que casar). As regex de `quando`/`extrair`/`detectar` rodam com
`search`, não `fullmatch`: "^TED" ancora no início, mas "TED" solto casa em qualquer posição.
Grupos nomeados das regex (?P<ticker>...) viram apelidos disponíveis nos templates, só dentro
da regra onde aparecem (não vazam para outras regras — ver escopo de `apelidos` por regra).

Preenchimento de `campos` (regra "destino não consegue preencher"): todo campo do schema do
destino tem que estar coberto por um de — chave em `campos`; apelido de mesmo nome (colunas ou
grupo nomeado) preenche o campo implicitamente, sem precisar aparecer em `campos`; `conta` e
`moeda` vêm do cabeçalho do mapa (PREENCHIDOS_PELO_MAPA); `cnpj` (proventos) e `razao` (eventos)
são opcionais (OPCIONAIS); `data` é exceção — quem chama pode suprir `--data` no runtime, o
mapa não precisa cobri-lo.

Defaults que não aparecem em erro nenhum, então ficam só aqui: `ajuste.campo` sem valor é
`valor_liquido`; `conciliacao.ordem` sem valor é `crescente`; `conciliacao.valor-da-linha` exige
um apelido chamado literalmente `valor` em colunas; `conciliacao.origem: flag` significa que
quem roda a ingestão passa a quantia por `--total-declarado` na hora (não vem do documento).

Tipos de célula: xlsx devolve datetime/float nativos por célula (não string) quando a planilha
guarda assim; CSV é sempre string. `datas.formatos` e `po.numeros` lidam com os dois.
"""
import datetime
import re
from pathlib import Path

import yaml

from po.csvs import MOEDAS, OPCIONAIS, SCHEMAS, em_vocabulario
from po.ingestao.leitores import DependenciaAusente, ler_tabela

DESTINOS_TABELA = {"posicoes", "fills", "proventos", "eventos"}
CHAVES_TOPO = {"nome", "versao", "descricao", "observacoes", "verificado-contra-export-real",
               "detectar", "arquivo", "datas", "conta", "moeda", "colunas", "extrair", "linhas",
               "conciliacao"}
CHAVES_ARQUIVO = {"formato", "aba", "encoding", "delimitador", "cabecalho-contem", "fim-em-vazio"}
CHAVES_DATAS = {"formatos", "extrair"}
CHAVES_REGRA = {"quando", "destino", "campos", "motivo", "aplica-em", "campo", "chave", "valor"}
CHAVES_CONCILIACAO = {"tipo", "valor", "saldo", "ordem", "proventos", "soma", "origem", "tolerancia"}
PREENCHIDOS_PELO_MAPA = {"conta", "moeda"}
DESTINOS = DESTINOS_TABELA | {"ignorar", "ajuste"}
FORMATOS = {"csv", "xlsx"}
CONCILIACOES = {"saldo-corrente", "valor-da-linha", "total-declarado"}
TOKEN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\|([^}]*))?\}")


def _grupos(regex) -> set[str]:
    return set(re.compile(regex).groupindex)


def _desconhecidas(bloco: dict, conhecidas: set, onde: str) -> list[str]:
    """Chave fora do vocabulário é typo, e typo silencioso é o erro mais comum de quem
    escreve YAML a partir de um docstring."""
    # key=repr: YAML resolve `on:`/`2026:` para bool/int, e ordenar chaves de tipos
    # mistos levantaria TypeError — dentro do helper que existe pra não levantar.
    extras = sorted((k for k in bloco if k not in conhecidas), key=repr)
    return [f"{onde}: chave desconhecida {k!r} (conhecidas: {sorted(conhecidas)})" for k in extras]


def validar_mapeamento(mapa: object) -> list[str]:
    """Lista de erros em pt-BR (vazia = válido). Nunca levanta."""
    if not isinstance(mapa, dict):
        return ["mapeamento deve ser um mapeamento YAML (chave: valor)"]
    erros = _desconhecidas(mapa, CHAVES_TOPO, "mapeamento")
    detectar = mapa.get("detectar")
    if detectar is not None:
        if not isinstance(detectar, dict):
            erros.append("detectar deve ser um mapeamento {cabecalho-contem: [textos]}")
        else:
            erros.extend(_desconhecidas(detectar, {"cabecalho-contem"}, "detectar"))
            assinatura = detectar.get("cabecalho-contem")
            if (not isinstance(assinatura, list) or not assinatura
                    or not all(isinstance(x, str) and x for x in assinatura)):
                erros.append("detectar.cabecalho-contem deve ser uma lista não-vazia de textos do cabeçalho")
    if not isinstance(mapa.get("nome"), str) or not mapa["nome"]:
        erros.append("nome ausente")
    if mapa.get("versao") != 1:
        erros.append("versao deve ser 1")
    arquivo = mapa.get("arquivo")
    if not isinstance(arquivo, dict) or not em_vocabulario(arquivo.get("formato"), FORMATOS):
        erros.append(f"arquivo.formato deve ser um de {sorted(FORMATOS)}")
    if isinstance(arquivo, dict):
        erros.extend(_desconhecidas(arquivo, CHAVES_ARQUIVO, "arquivo"))
    datas = mapa.get("datas")
    if (not isinstance(datas, dict) or not isinstance(datas.get("formatos"), list) or not datas["formatos"]
            or not all(isinstance(f, str) for f in datas["formatos"])):
        erros.append("datas.formatos deve ser uma lista de formatos strptime (ex.: ['%d/%m/%Y'])")
    if isinstance(datas, dict):
        erros.extend(_desconhecidas(datas, CHAVES_DATAS, "datas"))
    extrair_data = datas.get("extrair") if isinstance(datas, dict) else None
    if extrair_data is not None:
        try:
            if re.compile(extrair_data).groups != 1:
                erros.append("datas.extrair precisa de exatamente um grupo de captura")
        except (re.error, TypeError) as e:
            erros.append(f"datas.extrair: regex inválida ({e})")
    formatos = datas.get("formatos") if isinstance(datas, dict) and isinstance(datas.get("formatos"), list) else []
    for fmt in formatos:
        if not isinstance(fmt, str):
            continue
        try:   # typo de diretiva (%Q) é erro de mapeamento, não "data ilegível" em toda linha
            datetime.datetime.strptime(datetime.datetime(2000, 1, 2, 3, 4, 5).strftime(fmt), fmt)
        except ValueError as e:
            erros.append(f"datas.formatos: {fmt!r} não é um formato strptime válido ({e})")
    if not isinstance(mapa.get("conta"), str) or not mapa["conta"]:
        erros.append("conta ausente (id da conta na config)")
    if not em_vocabulario(mapa.get("moeda"), MOEDAS):
        erros.append(f"moeda deve ser uma de {sorted(MOEDAS)}")
    colunas = mapa.get("colunas")
    if not isinstance(colunas, dict) or not colunas or not all(isinstance(v, str) and v for v in colunas.values()):
        erros.append("colunas deve mapear apelido -> nome da coluna no documento")
        colunas = {}
    apelidos_base = set(colunas)
    extrair = mapa.get("extrair") or {}
    if not isinstance(extrair, dict):
        erros.append("extrair deve ser {apelido: regex}")
        extrair = {}
    for apelido, regex in extrair.items():
        if apelido not in colunas:
            erros.append(f"extrair.{apelido}: apelido não existe em colunas")
        try:
            apelidos_base |= _grupos(regex)
        except (re.error, TypeError) as e:
            erros.append(f"extrair.{apelido}: regex inválida ({e})")
    regras = mapa.get("linhas")
    if not isinstance(regras, list) or not regras:
        erros.append("linhas deve ser uma lista não-vazia de regras")
        regras = []
    for i, regra in enumerate(regras, start=1):
        onde = f"linhas[{i}]"
        if not isinstance(regra, dict):
            erros.append(f"{onde}: regra deve ser um mapeamento")
            continue
        erros.extend(_desconhecidas(regra, CHAVES_REGRA, onde))
        apelidos = set(apelidos_base)   # por regra: grupo de outra regra não vale aqui
        quando = regra.get("quando")
        if not isinstance(quando, dict) or not quando:
            erros.append(f"{onde}: quando ausente ({{apelido: regex}})")
        else:
            for apelido, regex in quando.items():
                if apelido not in colunas:
                    erros.append(f"{onde}: quando.{apelido} não é um apelido de colunas")
                try:
                    apelidos |= _grupos(regex)
                except (re.error, TypeError) as e:
                    erros.append(f"{onde}: regex inválida em quando.{apelido} ({e})")
        destino = regra.get("destino")
        if not em_vocabulario(destino, DESTINOS):
            erros.append(f"{onde}: destino {destino!r} fora de {sorted(DESTINOS)}")
            continue
        if destino == "ignorar":
            if not regra.get("motivo"):
                erros.append(f"{onde}: ignorar exige motivo")
        elif destino == "ajuste":
            alvo = regra.get("aplica-em")
            if not em_vocabulario(alvo, DESTINOS_TABELA):
                erros.append(f"{onde}: ajuste exige aplica-em (uma tabela de dados/)")
            elif regra.get("campo", "valor_liquido") not in SCHEMAS[alvo]:
                erros.append(f"{onde}: ajuste.campo fora do schema de {alvo}")
            chave = regra.get("chave")
            if not isinstance(chave, list) or not chave:
                erros.append(f"{onde}: ajuste exige chave (lista de campos para achar a linha principal)")
            elif em_vocabulario(alvo, DESTINOS_TABELA):
                fora = [c for c in chave if not em_vocabulario(c, SCHEMAS[alvo])]
                if fora:
                    erros.append(f"{onde}: ajuste.chave {fora} fora do schema de {alvo} ({SCHEMAS[alvo]})")
            if not regra.get("valor"):
                erros.append(f"{onde}: ajuste exige valor (template da quantia)")
        else:
            campos = regra.get("campos") or {}
            if not isinstance(campos, dict):
                erros.append(f"{onde}: campos deve ser um mapeamento")
                continue
            faltando = [c for c in SCHEMAS[destino]
                        if c not in campos and c not in apelidos and c not in PREENCHIDOS_PELO_MAPA
                        and c not in OPCIONAIS.get(destino, set())
                        and c != "data"]   # data é exceção: --data supre no runtime, mapa não precisa
            if faltando:
                erros.append(f"{onde}: destino {destino} não consegue preencher {faltando} — "
                             "declare em campos ou dê a esses nomes um apelido em colunas/extrair")
            for campo, template in campos.items():
                if campo not in SCHEMAS[destino]:
                    erros.append(f"{onde}: campo {campo!r} fora do schema de {destino}")
                for nome, _ in TOKEN.findall(str(template)):
                    if nome not in apelidos:
                        erros.append(f"{onde}: {campo} usa {{{nome}}}, que não é apelido nem grupo de regex")
    conc = mapa.get("conciliacao")
    if isinstance(conc, dict):
        erros.extend(_desconhecidas(conc, CHAVES_CONCILIACAO, "conciliacao"))
        tolerancia = conc.get("tolerancia")
        if tolerancia is not None:
            if isinstance(tolerancia, bool) or not isinstance(tolerancia, (int, float)) or tolerancia <= 0:
                erros.append(f"conciliacao.tolerancia deve ser um número positivo (veio {tolerancia!r})")
            if conc.get("tipo") != "total-declarado":
                erros.append("conciliacao.tolerancia só vale com conciliacao.tipo total-declarado "
                             "(é onde ela é honrada — ver po.ingestao.conciliacao)")
    if not isinstance(conc, dict) or not em_vocabulario(conc.get("tipo"), CONCILIACOES):
        erros.append(f"conciliacao.tipo deve ser um de {sorted(CONCILIACOES)} — mapeamento sem conciliação é recusado")
    elif conc["tipo"] == "saldo-corrente":
        for chave in ("valor", "saldo"):
            if not em_vocabulario(conc.get(chave), colunas):
                erros.append(f"conciliacao.{chave} deve ser um apelido de colunas")
        if conc.get("ordem", "crescente") not in ("crescente", "decrescente"):
            erros.append("conciliacao.ordem deve ser crescente ou decrescente")
    elif conc["tipo"] == "valor-da-linha":
        if "valor" not in colunas:
            erros.append("valor-da-linha exige o apelido 'valor' em colunas")
        if conc.get("proventos", "valor_bruto") not in ("valor_bruto", "valor_liquido"):
            erros.append("conciliacao.proventos deve ser valor_bruto ou valor_liquido")
    else:
        if not isinstance(conc.get("soma"), str) or not conc["soma"]:
            erros.append("total-declarado exige soma (campo ou campo*campo do registro)")
        else:   # os campos da soma têm que existir no schema de algum destino que o mapa produz
            destinos = {r.get("destino") for r in regras
                        if isinstance(r, dict) and isinstance(r.get("destino"), str)} & DESTINOS_TABELA
            conhecidos = {c for d in destinos for c in SCHEMAS[d]}
            fora = [c for c in (x.strip() for x in conc["soma"].split("*"))
                    if not em_vocabulario(c, conhecidos)]
            if destinos and fora:
                erros.append(f"conciliacao.soma cita {fora}, que não é campo de nenhum destino "
                             f"produzido por este mapa ({sorted(destinos)})")
        origem = conc.get("origem")
        if origem == "flag":
            pass
        elif not isinstance(origem, dict):
            erros.append("total-declarado exige origem: flag, ou {linha-contem: texto, coluna: apelido}")
        else:
            erros.extend(_desconhecidas(origem, {"linha-contem", "coluna"}, "conciliacao.origem"))
            linha_contem = origem.get("linha-contem")
            if not isinstance(linha_contem, str) or not linha_contem:
                erros.append("conciliacao.origem.linha-contem deve ser o texto que marca a linha de total")
            if not em_vocabulario(origem.get("coluna"), colunas):   # apelido, como o resto da DSL
                erros.append("conciliacao.origem.coluna deve ser um apelido de colunas")
    return erros


def carregar_mapeamento(caminho: str | Path) -> dict:
    """Lê e valida um arquivo de mapeamento. ValueError com os erros em pt-BR."""
    caminho = Path(caminho)
    if not caminho.is_file():   # exists() é verdade para diretório, e aí o open vazaria OSError
        raise FileNotFoundError(f"mapeamento {caminho} não encontrado")
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError(f"{caminho.name}: não é UTF-8 válido") from e
    try:
        mapa = yaml.safe_load(texto)
    except yaml.YAMLError as e:
        raise ValueError(f"{caminho.name}: YAML malformado: {e}") from e
    erros = validar_mapeamento(mapa)
    if erros:
        raise ValueError(f"{caminho.name}: mapeamento inválido: " + "; ".join(erros))
    return mapa


def listar_mapeamentos(raiz_ws: Path, motor: Path) -> dict[str, Path]:
    """{nome: caminho}; o do workspace sobrepõe o do motor de mesmo nome."""
    encontrados = {}
    for base in (Path(motor) / "mapeamentos", Path(raiz_ws) / "mapeamentos"):
        if base.is_dir():
            for p in sorted(base.glob("*.yaml")):
                encontrados[p.stem] = p
    return encontrados


def resolver_mapeamento(nome_ou_caminho: str, raiz_ws: Path, motor: Path) -> Path:
    """Caminho .yaml existente, ou nome em mapeamentos/ do workspace (prioridade) ou do motor."""
    p = Path(nome_ou_caminho)
    if p.suffix == ".yaml" and p.exists():
        return p
    disponiveis = listar_mapeamentos(raiz_ws, motor)
    if nome_ou_caminho in disponiveis:
        return disponiveis[nome_ou_caminho]
    raise FileNotFoundError(f"mapeamento {nome_ou_caminho!r} não encontrado (disponíveis: {sorted(disponiveis)})")


def detectar_mapeamento(caminho_doc: Path, raiz_ws: Path, motor: Path) -> Path | None:
    """Mapeamento cujo detectar.cabecalho-contem casa com o cabeçalho do documento.
    None se nenhum casa; ValueError se mais de um casa."""
    ext = Path(caminho_doc).suffix.lower().lstrip(".")
    casam = []
    for _, p in listar_mapeamentos(raiz_ws, motor).items():
        try:
            mapa = carregar_mapeamento(p)
        except (ValueError, FileNotFoundError):
            continue
        assinatura = (mapa.get("detectar") or {}).get("cabecalho-contem")
        if not assinatura or mapa["arquivo"]["formato"] != ext:
            continue
        try:
            tabela = ler_tabela(caminho_doc, mapa["arquivo"])
        except DependenciaAusente:
            raise
        except (ValueError, FileNotFoundError):
            continue
        if all(t in set(tabela.cabecalho) for t in assinatura):
            casam.append(p)
    if len(casam) > 1:
        raise ValueError(f"mais de um mapeamento casa com o documento: {[p.stem for p in casam]} — passe --mapeamento")
    return casam[0] if casam else None
