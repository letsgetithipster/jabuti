import re
from pathlib import Path

import pytest

from extratos_sinteticos import construir_b3, construir_clear
from po.ingestao.conciliacao import conciliar
from po.ingestao.engine import executar
from po.ingestao.leitores import ler_tabela
from po.ingestao.mapeamento import carregar_mapeamento, listar_mapeamentos

MOTOR = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "extratos"


def _rodar(nome, doc, **kw):
    mapa = carregar_mapeamento(MOTOR / "mapeamentos" / f"{nome}.yaml")
    tabela = ler_tabela(doc, mapa["arquivo"])
    res = executar(mapa, tabela, **kw)
    erros, desc = list(res.erros), ""
    if not erros:
        e2, desc = conciliar(mapa, tabela, res)
        erros += e2
    return mapa, res, erros, desc


def test_todos_os_mapeamentos_do_motor_sao_validos():
    nomes = set(listar_mapeamentos(MOTOR / "nao-existe", MOTOR))
    assert nomes == {"clear-extrato", "schwab-transacoes", "b3-movimentacao", "exemplo-posicoes-csv"}
    for p in (MOTOR / "mapeamentos").glob("*.yaml"):
        carregar_mapeamento(p)


def test_todo_mapeamento_do_motor_declara_a_propria_tolerancia():
    """Herdar o pior caso em silêncio é o que a calibração do review da Task 10 fechou: o default
    de total-declarado é o limite teórico, largo o bastante para uma posição inteira sumir."""
    for p in (MOTOR / "mapeamentos").glob("*.yaml"):
        mapa = carregar_mapeamento(p)
        assert mapa["conciliacao"].get("tolerancia"), f"{p.stem} não declara conciliacao.tolerancia"
        assert any(p in mapa["observacoes"].lower() for p in ("tolerância", "tolerancia")), f"{p.stem} não justifica a tolerância em observacoes"


SIM = {"sim"}
NAO = {"não", "nao", "modelo"}


def _diz_sim(celula: str, nome: str) -> bool:
    """Primeira palavra da célula, sem ênfase markdown. Conjunto explícito nos dois lados: um
    `startswith("sim")` aceitaria "simulado" e "sim, parcialmente" como verificado, que é
    exatamente a afirmação bonita que este teste existe para barrar. Palavra fora do vocabulário
    é falha, não um `False` silencioso."""
    palavra = celula.strip().lstrip("*").split()[0].strip("*,.:;").lower()
    assert palavra in SIM | NAO, f"{nome}: célula do README começa com {palavra!r}, fora de {sorted(SIM | NAO)}"
    return palavra in SIM


def test_readme_dos_prontos_reflete_o_campo_verificado_de_cada_yaml():
    """A tabela do README é afirmação sobre o que foi conferido contra documento real. Se ela e o
    YAML divergirem, a errada é sempre a que é bonita de dizer."""
    linhas = {}
    for linha in (MOTOR / "mapeamentos" / "README.md").read_text(encoding="utf-8").splitlines():
        if linha.startswith("| `"):
            celulas = [c.strip() for c in linha.strip("|").split("|")]
            linhas[celulas[0].strip("`")] = celulas[2]
    assert set(linhas) == set(listar_mapeamentos(MOTOR / "nao-existe", MOTOR))
    for nome, dito in linhas.items():
        verificado = carregar_mapeamento(MOTOR / "mapeamentos" / f"{nome}.yaml")["verificado-contra-export-real"]
        assert _diz_sim(dito, nome) is bool(verificado), f"{nome}: README diz {dito!r}"


def test_clear_extrato(tmp_path):
    pytest.importorskip("openpyxl")
    doc = construir_clear(tmp_path / "extrato.xlsx")
    mapa, res, erros, desc = _rodar("clear-extrato", doc)
    assert erros == [] and mapa["verificado-contra-export-real"] is True
    prov = {(p["ticker"], p["tipo"]): p["valor_bruto"] for p in res.registros["proventos"]}
    assert prov == {("RENT4", "jcp"): 5.74, ("HGLG11", "rendimento"): 99.0, ("WEGE3", "dividendo"): 25.0, ("ITUB3", "jcp"): 6.61}
    assert res.registros["proventos"][0]["data"] == "2026-08-20"
    assert len(res.ignoradas) == 3 and res.registros["fills"] == []
    assert "6 par(es)" in desc


def test_clear_saldo_quebrado_para(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    doc = construir_clear(tmp_path / "extrato.xlsx")
    wb = openpyxl.load_workbook(doc)
    wb.active["G17"] = 1200.00          # saldo da linha do WEGE3 adulterado
    wb.save(doc)
    _, _, erros, _ = _rodar("clear-extrato", doc)
    assert any("saldo" in e and "≠" in e for e in erros)


def test_clear_lancamento_desconhecido_e_erro_nao_descarte(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    doc = construir_clear(tmp_path / "extrato.xlsx")
    wb = openpyxl.load_workbook(doc)
    wb.active["D16"] = "AMORTIZAÇÃO DE CLIENTES HGLG11 S/ 90"
    wb.save(doc)
    _, _, erros, _ = _rodar("clear-extrato", doc)
    assert any("não classificada" in e and "AMORTIZAÇÃO" in e for e in erros)


def test_clear_ancora_no_meio_do_extrato_nao_pode_saltar(tmp_path):
    """Calibração 2 do review da Task 10: uma linha com saldo e sem valor ancora a cadeia, e sem
    conferir contra o saldo anterior um salto inexplicado no meio do extrato passava limpo."""
    openpyxl = pytest.importorskip("openpyxl")
    doc = construir_clear(tmp_path / "extrato.xlsx")
    wb = openpyxl.load_workbook(doc)
    ws = wb.active
    ws["D18"] = "TED SALDO EM CONTA"    # linha do TED (8/10) vira âncora: sem valor, saldo mantido
    ws["F18"] = None
    ws["G18"] = 1676.00                 # repete o saldo da linha anterior na cadeia crescente
    for celula, saldo in (("G17", 1701.00), ("G16", 1800.00), ("G15", 1805.74)):
        ws[celula] = saldo              # os 500,00 que a TED não retira mais seguem cadeia acima
    wb.save(doc)
    _, _, erros, desc = _rodar("clear-extrato", doc)
    assert erros == [] and "1 âncora(s)" in desc
    wb = openpyxl.load_workbook(doc)
    wb.active["G18"] = 10674.00         # salto de 8.998,00 sem lançamento nenhum
    wb.save(doc)
    _, _, erros, _ = _rodar("clear-extrato", doc)
    assert any("âncora" in e and "8998.00" in e for e in erros)


def test_schwab_transacoes():
    mapa, res, erros, desc = _rodar("schwab-transacoes", FIX / "schwab-transacoes.csv")
    assert erros == []
    prov = {p["ticker"]: (p["valor_bruto"], round(p["valor_liquido"], 2)) for p in res.registros["proventos"]}
    assert prov == {"WELL": (5.10, 3.57), "AAPL": (1.89, 1.32)}
    fills = {(f["ticker"], f["tipo"]): (f["qty"], f["preco"], f["taxa"], f["data"]) for f in res.registros["fills"]}
    assert fills == {("AAPL", "compra"): (2.0, 230.5, 0.0, "2026-08-05"), ("O", "venda"): (3.0, 60.0, 0.05, "2026-07-15")}
    ev = res.registros["eventos"]
    assert len(ev) == 1
    assert (ev[0]["ticker"], ev[0]["tipo"], ev[0]["confirmado"], ev[0]["data"]) == ("MNST", "split", "nao", "2026-08-11")
    # 2 conferidas (os dois fills, cujo qty × preço ± taxa é prova de verdade) e 2 apenas
    # transcritas: o valor_bruto do dividendo SAI da coluna que a conciliação leria.
    assert len(res.ignoradas) == 1
    assert "2 linha(s) conferidas" in desc and "2 provento(s) apenas transcrito" in desc
    assert all(p["moeda"] == "USD" and p["conta"] == "corretora-us" for p in res.registros["proventos"])


def test_schwab_valor_adulterado_para(tmp_path):
    doc = tmp_path / "s.csv"
    doc.write_text((FIX / "schwab-transacoes.csv").read_text(encoding="utf-8").replace("-$461.00", "-$400.00"),
                   encoding="utf-8")
    _, _, erros, _ = _rodar("schwab-transacoes", doc)
    assert any("AAPL compra" in e and "≠ valor declarado 400.00" in e for e in erros)


def test_b3_movimentacao(tmp_path):
    pytest.importorskip("openpyxl")
    doc = construir_b3(tmp_path / "b3.xlsx")
    mapa, res, erros, desc = _rodar("b3-movimentacao", doc)
    assert erros == [] and mapa["verificado-contra-export-real"] is False
    assert [(f["ticker"], f["tipo"], f["qty"], f["preco"]) for f in res.registros["fills"]] == \
        [("PETR4", "compra", 40.0, 30.75), ("VALE3", "venda", 10.0, 65.0)]
    assert [(p["ticker"], p["tipo"], p["valor_bruto"]) for p in res.registros["proventos"]] == [("HGLG11", "rendimento", 55.0)]
    assert [(e["ticker"], e["tipo"], e["razao"]) for e in res.registros["eventos"]] == [("RENT4", "bonificacao", "13 novas")]
    assert len(res.ignoradas) == 1


def test_posicoes_exemplo_csv():
    mapa, res, erros, desc = _rodar("exemplo-posicoes-csv", FIX / "posicoes-exemplo.csv", data_padrao="2026-08-01")
    assert erros == []
    assert [(p["ticker"], p["classe"], p["qty"], p["pm"], p["_data"]) for p in res.registros["posicoes"]] == \
        [("PETR4", "acoes-br", 100.0, 30.0, "2026-08-01"), ("HGLG11", "fiis", 50.0, 155.0, "2026-08-01")]
    assert "10750.00 contra 10750.00" in desc


def test_posicoes_exemplo_sem_data_para_com_frase_acionavel():
    _, _, erros, _ = _rodar("exemplo-posicoes-csv", FIX / "posicoes-exemplo.csv")
    assert any("posições exigem a data do documento" in e and "passe --data AAAA-MM-DD" in e for e in erros)


def test_posicoes_exemplo_com_posicao_faltando_para():
    """Com a tolerância teórica (0,005 × Σqty = 0,75) uma posição inteira sumindo ainda passaria
    longe; com a declarada, a soma que não fecha para a importação."""
    mapa = carregar_mapeamento(MOTOR / "mapeamentos" / "exemplo-posicoes-csv.yaml")
    tabela = ler_tabela(FIX / "posicoes-exemplo.csv", mapa["arquivo"])
    res = executar(mapa, tabela, data_padrao="2026-08-01")
    res.registros["posicoes"].pop()          # a corretora listou HGLG11 no total e não na tabela
    erros, _ = conciliar(mapa, tabela, res)
    assert any("≠ total declarado 10750.00" in e and "tolerância 0.01" in e for e in erros)


def test_fixtures_nao_carregam_dado_pessoal():
    """Guarda-corpo: nomes/contas reais nunca entram nas fixtures. Ajuste a lista se o seu nome for outro.

    VARRE a pasta de fixtures inteira em vez de enumerar arquivos. A lista fixa de três arquivos
    que esta guarda tinha antes passava verde para toda fixture nova — inclusive as de open
    finance, que são justamente as que nascem de resposta de API com dado real e precisam ser
    anonimizadas à mão. Guarda que não cobre o arquivo novo é guarda decorativa.

    CPF e CNPJ entram na lista porque `create_data_consent` recebe documento: a partir da camada
    de provider, essa é a forma que tem chance real de cair numa fixture colada de um payload.
    """
    proibidos = ["GUILHERME", "@outlook", "@gmail"]
    formatos_de_documento = [
        re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"),            # CPF formatado
        re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"),      # CNPJ formatado
    ]
    aqui = Path(__file__).resolve().parent
    arquivos = sorted(p for p in (aqui / "fixtures").rglob("*") if p.is_file())
    arquivos.append(aqui / "extratos_sinteticos.py")
    # metodo/ é rubrica: número de método, nunca número de carteira nem nome de pessoa
    arquivos.extend(sorted(p for p in (aqui.parent / "metodo").rglob("*") if p.is_file()))
    assert len(arquivos) > 3, "varredura de fixtures não achou arquivo; o caminho mudou de lugar?"
    for caminho in arquivos:
        try:
            t = caminho.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue                                          # binário não é fixture de texto
        for p in proibidos:
            assert p.lower() not in t.lower(), f"{caminho.name} carrega {p!r}"
        for forma in formatos_de_documento:
            achado = forma.search(t)
            assert achado is None, (
                f"{caminho.name} carrega o que parece um CPF/CNPJ ({achado.group()}) — "
                "substitua à mão preservando a forma, como nas outras fixtures")


def test_schwab_ajuste_de_imposto_com_digito_a_mais_para(tmp_path):
    """C2 de ponta a ponta. O NRA Tax Adj da WELL com um dígito a mais (-$15.30 no lugar de
    -$1.53, sobre um dividendo de $5.10) gravava dividendo líquido NEGATIVO com "4 linha(s)
    conferidas": `valor-da-linha` comparava valor_bruto com a mesma célula de onde ele saiu, e
    valor_liquido, o único campo que o ajuste move, não era conferido por nada."""
    doc = tmp_path / "s.csv"
    doc.write_text((FIX / "schwab-transacoes.csv").read_text(encoding="utf-8").replace("-$1.53", "-$15.30"),
                   encoding="utf-8")
    _, res, erros, _ = _rodar("schwab-transacoes", doc)
    assert any("depois do ajuste" in e and "sinal oposto" in e for e in erros)
    # e o registro envenenado não sobrevive à rodada: com res.erros preenchido, o CLI não grava
    assert res.erros
