"""Leitura tabular de documentos de corretora (CSV e xlsx) para a ingestão.

Devolve uma Tabela crua: cabeçalho (nomes exatos, strip) e linhas como listas de
células. Nada é convertido aqui — número e data são assunto do engine, pelo mapeamento.
openpyxl é opcional: só o caminho .xlsx o importa (lazy), com erro acionável se faltar.
"""
import csv
from dataclasses import dataclass, field
from pathlib import Path


class DependenciaAusente(Exception):
    """Biblioteca opcional ausente (openpyxl para xlsx)."""


MSG_OPENPYXL = ("arquivo .xlsx exige openpyxl: pip install -r requirements-xlsx.txt, "
                "ou exporte o extrato como CSV")


@dataclass
class Tabela:
    cabecalho: list[str]
    linhas: list[list]
    linha_cabecalho: int   # número da linha do cabeçalho no documento (1-based), para mensagens
    numeros: list[int] = field(default_factory=list)   # linha física de cada linha de dados

    def numero_da_linha(self, indice: int) -> int:
        """Número FÍSICO no documento da i-ésima linha de dados (0-based).

        Não dá pra derivar por aritmética: linha em branco no meio do documento é pulada
        (quando 'fim-em-vazio' é falso), e aí o índice deixa de acompanhar a linha do arquivo.
        Mensagem que aponta a linha errada é pior que mensagem nenhuma."""
        if self.numeros:
            return self.numeros[indice]
        return self.linha_cabecalho + 1 + indice


def _celula(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return v


def _vazia(linha) -> bool:
    return all(str(c).strip() == "" for c in linha)


def _linhas_csv(caminho: Path, cfg: dict) -> tuple[list[list], dict]:
    encoding = cfg.get("encoding", "utf-8-sig")
    delimitador = cfg.get("delimitador", ",")
    try:
        with caminho.open(encoding=encoding, newline="") as f:
            return [[_celula(c) for c in linha] for linha in csv.reader(f, delimiter=delimitador)], {}
    except UnicodeDecodeError as e:
        raise ValueError(f"{caminho.name}: não é {encoding} válido — confira 'arquivo.encoding' no "
                         "mapeamento (latin-1 é comum em export brasileiro)") from e


def _linhas_xlsx(caminho: Path, cfg: dict) -> tuple[list[list], dict]:
    try:
        import openpyxl
    except ImportError as e:
        raise DependenciaAusente(MSG_OPENPYXL) from e
    try:
        # sem read_only: o modo read-only já variou entre versões quanto a linhas vazias
        # no meio da planilha, e 'fim-em-vazio' depende de enxergá-las. Custo zero aqui.
        wb = openpyxl.load_workbook(caminho, data_only=True)
    except Exception as e:  # openpyxl levanta tipos variados para arquivo corrompido
        raise ValueError(f"{caminho.name}: xlsx ilegível ({e})") from e
    aba = cfg.get("aba", 0)
    try:
        ws = wb.worksheets[aba] if isinstance(aba, int) else wb[aba]
    except (IndexError, KeyError):
        raise ValueError(f"{caminho.name}: aba {aba!r} não existe (abas: {wb.sheetnames})")
    linhas = [[_celula(c) for c in linha] for linha in ws.iter_rows(values_only=True)]
    return linhas, _formulas_sem_valor(caminho, aba, linhas)


def _formulas_sem_valor(caminho: Path, aba, linhas: list[list]) -> dict:
    """{(linha0, coluna0): coordenada} das fórmulas que voltaram vazias.

    Com data_only=True, fórmula sem valor em cache volta None — indistinguível de célula vazia.
    Uma coluna Total que é fórmula viraria coluna vazia e uma linha inteira de fórmulas
    truncaria a tabela sob 'fim-em-vazio', sem erro nenhum. Quem decide se isso importa é o
    ler_tabela, que sabe qual região do documento vai mesmo consumir: rodapé de soma fora da
    tabela é justamente o que 'fim-em-vazio' existe pra descartar. Segunda leitura do arquivo
    (data_only=False) é o único jeito de distinguir fórmula de célula vazia — não remova."""
    import openpyxl
    bruto = openpyxl.load_workbook(caminho, data_only=False)
    ws = bruto.worksheets[aba] if isinstance(aba, int) else bruto[aba]
    achadas = {}
    for linha in ws.iter_rows():
        for c in linha:
            e_formula = (isinstance(c.value, str) and c.value.startswith("=")
                         or type(c.value).__name__ in ("ArrayFormula", "DataTableFormula"))
            if not e_formula:
                continue
            i, j = c.row - 1, c.column - 1
            if i < len(linhas) and j < len(linhas[i]) and linhas[i][j] == "":
                achadas[(i, j)] = c.coordinate
    return achadas


def ler_tabela(caminho: str | Path, cfg: dict) -> Tabela:
    """cfg = bloco 'arquivo' do mapeamento: formato (csv|xlsx), aba, encoding, delimitador,
    cabecalho-contem (textos que identificam a linha de cabeçalho; default: primeira linha
    não-vazia), fim-em-vazio (a tabela termina na primeira linha vazia após o cabeçalho)."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"{caminho}: arquivo não encontrado")
    formato = cfg.get("formato", "csv")
    linhas, formulas = _linhas_xlsx(caminho, cfg) if formato == "xlsx" else _linhas_csv(caminho, cfg)
    contem = cfg.get("cabecalho-contem") or []
    indice = None
    for i, linha in enumerate(linhas):
        textos = {str(c).strip() for c in linha}
        if contem:
            if all(t in textos for t in contem):
                indice = i
                break
        elif not _vazia(linha):
            indice = i
            break
    if indice is None:
        raise ValueError(f"{caminho.name}: cabeçalho não encontrado (procurei uma linha com {contem})")
    cabecalho = [str(c).strip() for c in linhas[indice]]
    dados, numeros, examinadas = [], [], {indice}
    for n, linha in enumerate(linhas[indice + 1:], start=indice + 1):
        examinadas.add(n)          # inclui a linha vazia que encerra a leitura: se ela só parece
        if _vazia(linha):          # vazia por ser fórmula sem valor, é ela que trunca a tabela
            if cfg.get("fim-em-vazio", False):
                break
            continue
        linha = list(linha) + [""] * max(0, len(cabecalho) - len(linha))
        dados.append(linha)
        numeros.append(n + 1)          # 1-based, a linha física do arquivo
    if formulas:   # só importa fórmula vazia DENTRO da região que este mapeamento examina
        # largura lógica = última coluna com nome; o iter_rows preenche o cabeçalho até a
        # largura da planilha, então uma fórmula solta à direita não é coluna desta tabela
        nomeadas = [j for j, c in enumerate(cabecalho) if c]
        n_colunas = nomeadas[-1] + 1 if nomeadas else 0
        dentro = sorted(coord for (i, j), coord in formulas.items()
                        if i in examinadas and j < n_colunas)
        if dentro:
            raise ValueError(
                f"{caminho.name}: célula {dentro[0]} é fórmula sem valor calculado "
                "— abra e salve a planilha no Excel/LibreOffice, ou exporte como CSV")
    return Tabela(cabecalho, dados, indice + 1, numeros)
