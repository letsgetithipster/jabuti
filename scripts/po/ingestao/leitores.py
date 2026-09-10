"""Leitura tabular de documentos de corretora (CSV e xlsx) para a ingestão.

Devolve uma Tabela crua: cabeçalho (nomes exatos, strip) e linhas como listas de
células. Nada é convertido aqui — número e data são assunto do engine, pelo mapeamento.
openpyxl é opcional: só o caminho .xlsx o importa (lazy), com erro acionável se faltar.
"""
import csv
from dataclasses import dataclass
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

    def numero_da_linha(self, indice: int) -> int:
        """Número no documento da i-ésima linha de dados (0-based)."""
        return self.linha_cabecalho + 1 + indice


def _celula(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return v


def _vazia(linha) -> bool:
    return all(str(c).strip() == "" for c in linha)


def _linhas_csv(caminho: Path, cfg: dict) -> list[list]:
    encoding = cfg.get("encoding", "utf-8-sig")
    delimitador = cfg.get("delimitador", ",")
    try:
        with caminho.open(encoding=encoding, newline="") as f:
            return [[_celula(c) for c in linha] for linha in csv.reader(f, delimiter=delimitador)]
    except UnicodeDecodeError as e:
        raise ValueError(f"{caminho.name}: não é {encoding} válido — confira 'arquivo.encoding' no "
                         "mapeamento (latin-1 é comum em export brasileiro)") from e


def _linhas_xlsx(caminho: Path, cfg: dict) -> list[list]:
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
    _recusar_formula_sem_valor(caminho, wb, aba, linhas)
    return linhas


def _recusar_formula_sem_valor(caminho: Path, wb, aba, linhas: list[list]) -> None:
    """Com data_only=True, uma fórmula sem valor em cache volta None — indistinguível de célula
    vazia. Uma coluna Total que é fórmula viraria coluna vazia, e com 'fim-em-vazio' uma linha
    inteira de fórmulas truncaria a tabela sem erro nenhum. Melhor parar e mandar recalcular."""
    import openpyxl
    bruto = openpyxl.load_workbook(caminho, data_only=False)
    ws = bruto.worksheets[aba] if isinstance(aba, int) else bruto[aba]
    for linha in ws.iter_rows():
        for c in linha:
            if isinstance(c.value, str) and c.value.startswith("="):
                calculada = linhas[c.row - 1][c.column - 1] if c.row - 1 < len(linhas) else ""
                if calculada == "":
                    raise ValueError(
                        f"{caminho.name}: célula {c.coordinate} é fórmula sem valor calculado "
                        "— abra e salve a planilha no Excel/LibreOffice, ou exporte como CSV")


def ler_tabela(caminho: str | Path, cfg: dict) -> Tabela:
    """cfg = bloco 'arquivo' do mapeamento: formato (csv|xlsx), aba, encoding, delimitador,
    cabecalho-contem (textos que identificam a linha de cabeçalho; default: primeira linha
    não-vazia), fim-em-vazio (a tabela termina na primeira linha vazia após o cabeçalho)."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"{caminho}: arquivo não encontrado")
    formato = cfg.get("formato", "csv")
    linhas = _linhas_xlsx(caminho, cfg) if formato == "xlsx" else _linhas_csv(caminho, cfg)
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
    dados = []
    for linha in linhas[indice + 1:]:
        if _vazia(linha):
            if cfg.get("fim-em-vazio", False):
                break
            continue
        linha = list(linha) + [""] * max(0, len(cabecalho) - len(linha))
        dados.append(linha)
    return Tabela(cabecalho, dados, indice + 1)
