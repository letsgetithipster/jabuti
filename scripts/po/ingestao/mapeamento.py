"""Mapeamento documento → schema canônico: carga, validação e resolução por nome.

O mapeamento é DADO (YAML), o engine é código. Vocabulário fechado:

  nome, versao (1), descricao, verificado-contra-export-real (bool)
  detectar: {cabecalho-contem: [textos]}         # auto-seleção do mapeamento pelo cabeçalho
  arquivo: {formato: csv|xlsx, aba, encoding, delimitador, cabecalho-contem, fim-em-vazio}
  datas: {formatos: [strptime...], extrair: regex com 1 grupo (opcional)}
  conta: id da conta na config (o CLI --conta sobrescreve)
  moeda: BRL|USD|EUR
  colunas: {apelido: "Nome exato no cabeçalho"}
  extrair: {apelido: regex com grupos nomeados}   # aplicado a toda linha antes das regras
  linhas: [ {quando: {apelido: regex}, destino: posicoes|fills|proventos|eventos|ignorar|ajuste,
             campos: {campo do schema: literal | "{apelido}" | "{apelido|padrão}"},
             motivo (ignorar) | aplica-em, campo, chave, valor (ajuste)} ]
  conciliacao: {tipo: saldo-corrente (valor, saldo, ordem)
                    | valor-da-linha (proventos: valor_bruto|valor_liquido)
                    | total-declarado (soma: campo | campo*campo; origem: flag | {linha-contem, coluna})}

Regras: primeira que casa vence; linha que não casa nenhuma é ERRO no engine.
Grupos nomeados das regex (?P<ticker>...) viram apelidos disponíveis nos templates.
"""
import datetime
import re
from pathlib import Path

import yaml

from po.csvs import MOEDAS, SCHEMAS, em_vocabulario
from po.ingestao.leitores import DependenciaAusente, ler_tabela

DESTINOS_TABELA = {"posicoes", "fills", "proventos", "eventos"}
DESTINOS = DESTINOS_TABELA | {"ignorar", "ajuste"}
FORMATOS = {"csv", "xlsx"}
CONCILIACOES = {"saldo-corrente", "valor-da-linha", "total-declarado"}
TOKEN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\|([^}]*))?\}")


def _grupos(regex) -> set[str]:
    return set(re.compile(regex).groupindex)


def validar_mapeamento(mapa: object) -> list[str]:
    """Lista de erros em pt-BR (vazia = válido). Nunca levanta."""
    if not isinstance(mapa, dict):
        return ["mapeamento deve ser um mapeamento YAML (chave: valor)"]
    erros = []
    if not isinstance(mapa.get("nome"), str) or not mapa["nome"]:
        erros.append("nome ausente")
    if mapa.get("versao") != 1:
        erros.append("versao deve ser 1")
    arquivo = mapa.get("arquivo")
    if not isinstance(arquivo, dict) or not em_vocabulario(arquivo.get("formato"), FORMATOS):
        erros.append(f"arquivo.formato deve ser um de {sorted(FORMATOS)}")
    datas = mapa.get("datas")
    if (not isinstance(datas, dict) or not isinstance(datas.get("formatos"), list) or not datas["formatos"]
            or not all(isinstance(f, str) for f in datas["formatos"])):
        erros.append("datas.formatos deve ser uma lista de formatos strptime (ex.: ['%d/%m/%Y'])")
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
    apelidos = set(colunas)
    extrair = mapa.get("extrair") or {}
    if not isinstance(extrair, dict):
        erros.append("extrair deve ser {apelido: regex}")
        extrair = {}
    for apelido, regex in extrair.items():
        if apelido not in colunas:
            erros.append(f"extrair.{apelido}: apelido não existe em colunas")
        try:
            apelidos |= _grupos(regex)
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
            if not isinstance(regra.get("chave"), list) or not regra["chave"]:
                erros.append(f"{onde}: ajuste exige chave (lista de campos para achar a linha principal)")
            if not regra.get("valor"):
                erros.append(f"{onde}: ajuste exige valor (template da quantia)")
        else:
            campos = regra.get("campos") or {}
            if not isinstance(campos, dict):
                erros.append(f"{onde}: campos deve ser um mapeamento")
                continue
            for campo, template in campos.items():
                if campo not in SCHEMAS[destino]:
                    erros.append(f"{onde}: campo {campo!r} fora do schema de {destino}")
                for nome, _ in TOKEN.findall(str(template)):
                    if nome not in apelidos:
                        erros.append(f"{onde}: {campo} usa {{{nome}}}, que não é apelido nem grupo de regex")
    conc = mapa.get("conciliacao")
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
        origem = conc.get("origem")
        if origem != "flag" and not (isinstance(origem, dict) and origem.get("linha-contem") and origem.get("coluna")):
            erros.append("total-declarado exige origem: flag, ou {linha-contem: texto, coluna: nome da coluna}")
    return erros


def carregar_mapeamento(caminho: str | Path) -> dict:
    """Lê e valida um arquivo de mapeamento. ValueError com os erros em pt-BR."""
    caminho = Path(caminho)
    if not caminho.exists():
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
