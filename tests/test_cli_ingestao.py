"""Contrato de linha de comando do importar_extrato.py, por subprocesso de verdade.

A Task 15 transforma este output em contrato de skill: quem chama precisa ramificar pelo
código de saída, sem parsear texto. Por isso cada código documentado tem um teste aqui.
"""
import os
import subprocess
import sys
from pathlib import Path

from test_validar_dados import copia_exemplo

RAIZ = Path(__file__).resolve().parent.parent
CLI = RAIZ / "scripts" / "importar_extrato.py"

MAPA_EXTRATO = """\
nome: teste-extrato
versao: 1
descricao: extrato de conta corrente para teste de CLI
arquivo:
  formato: csv
datas:
  formatos: ['%d/%m/%Y']
conta: corretora-br
moeda: BRL
colunas:
  data: Data
  descricao: Histórico
  valor: Valor
  saldo: Saldo
linhas:
  - quando: {descricao: '^RENDIMENTO (?P<ticker>[A-Z0-9]{4,6})$'}
    destino: proventos
    campos: {tipo: rendimento, valor_bruto: '{valor}', valor_liquido: '{valor}'}
  - quando: {descricao: '^JCP (?P<ticker>[A-Z0-9]{4,6})$'}
    destino: proventos
    campos: {tipo: jcp, valor_bruto: '{valor}', valor_liquido: '{valor}'}
  - quando: {descricao: '^SALDO ANTERIOR$'}
    destino: ignorar
    motivo: ancora
conciliacao: {tipo: saldo-corrente, valor: valor, saldo: saldo, ordem: decrescente}
"""

MAPA_POSICOES = """\
nome: teste-posicoes
versao: 1
descricao: posição consolidada para teste de CLI
arquivo:
  formato: csv
datas:
  formatos: ['%d/%m/%Y']
conta: corretora-br
moeda: BRL
colunas:
  ticker: Ativo
  classe: Classe
  qty: Quantidade
  pm: Preco
linhas:
  - quando: {ticker: '^[A-Z]'}
    destino: posicoes
conciliacao: {tipo: total-declarado, soma: 'qty*pm', origem: flag}
"""

EXTRATO = """\
Data,Histórico,Valor,Saldo
05/10/2026,RENDIMENTO HGLG11,"56,00","1.356,00"
04/10/2026,SALDO ANTERIOR,,"1.300,00"
"""

POSICOES_IGUAIS = """\
Ativo,Classe,Quantidade,Preco
PETR4,acoes-br,100,30.00
HGLG11,fiis,50,155.00
"""

POSICOES_DIVERGENTES = """\
Ativo,Classe,Quantidade,Preco
PETR4,acoes-br,120,30.00
HGLG11,fiis,50,155.00
"""


def prepara(tmp_path, documento=EXTRATO, mapa=MAPA_EXTRATO, nome="doc.csv"):
    """Workspace do exemplo + um mapeamento em mapeamentos/ + o documento em inbox/."""
    ws = copia_exemplo(tmp_path)
    (ws / "mapeamentos").mkdir(exist_ok=True)
    (ws / "mapeamentos" / "teste.yaml").write_text(mapa, encoding="utf-8")
    doc = ws / "inbox" / nome
    doc.write_text(documento, encoding="utf-8")
    return ws, doc


def roda(ws, doc, *args, env=None):
    return subprocess.run([sys.executable, str(CLI), str(ws), str(doc),
                           "--mapeamento", str(ws / "mapeamentos" / "teste.yaml"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def instantaneo(ws):
    return {p.name: p.read_text(encoding="utf-8") for p in sorted((ws / "dados").glob("*.csv"))}


def test_caminho_feliz_importa_e_sai_0(tmp_path):
    ws, doc = prepara(tmp_path)
    r = roda(ws, doc)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Gravado em dados/: proventos +1" in r.stdout
    proventos = (ws / "dados" / "proventos.csv").read_text(encoding="utf-8")
    assert "2026-10-05,HGLG11,,rendimento,56,56,corretora-br,BRL" in proventos


def test_log_de_importacao_real_registra_acertos_por_regra(tmp_path):
    """A regra de JCP não casa neste documento. O stdout não grita (mapa real tem uma regra
    por tipo de evento), mas o log fica com a contagem e nomeia a que não casou."""
    ws, doc = prepara(tmp_path)
    r = roda(ws, doc)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nunca casaram" not in r.stdout
    log = next(iter(sorted((ws / "logs" / "importacoes").glob("*.md"))))
    corpo = log.read_text(encoding="utf-8")
    assert "Acertos por regra de `linhas`: regra 1: 1; regra 2: 0; regra 3: 1" in corpo
    assert "Regras que nunca casaram: [2]" in corpo


def test_dry_run_avisa_regra_morta_e_nao_toca_dados(tmp_path):
    ws, doc = prepara(tmp_path)
    antes = instantaneo(ws)
    r = roda(ws, doc, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "aviso: regra(s) [2]" in r.stdout and "nunca casaram" in r.stdout
    assert "--dry-run: nada gravado." in r.stdout
    assert instantaneo(ws) == antes
    assert not (ws / "logs" / "importacoes").exists()


def test_conferir_sem_divergencia_sai_0(tmp_path):
    ws, doc = prepara(tmp_path, POSICOES_IGUAIS, MAPA_POSICOES, "pos.csv")
    antes = instantaneo(ws)
    r = roda(ws, doc, "--conferir", "--data", "2026-09-10", "--total-declarado", "10750,00")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PETR4 (corretora-br): OK" in r.stdout and "HGLG11 (corretora-br): OK" in r.stdout
    assert "Sem divergência" in r.stdout
    assert instantaneo(ws) == antes


def test_conferir_com_divergencia_sai_3(tmp_path):
    """Divergência não é erro de execução: código próprio, para a skill ramificar sem ler texto."""
    ws, doc = prepara(tmp_path, POSICOES_DIVERGENTES, MAPA_POSICOES, "pos.csv")
    antes = instantaneo(ws)
    r = roda(ws, doc, "--conferir", "--data", "2026-09-10", "--total-declarado", "11350,00")
    assert r.returncode == 3, r.stdout + r.stderr
    assert "PETR4 (corretora-br): DIVERGE" in r.stdout
    assert "nada gravado" in r.stdout
    assert instantaneo(ws) == antes
    assert "Traceback" not in r.stderr


def test_conta_nao_declarada_sai_1_com_frase(tmp_path):
    ws, doc = prepara(tmp_path)
    antes = instantaneo(ws)
    r = roda(ws, doc, "--conta", "corretora-marte")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "não declarada na config" in r.stdout and "corretora-marte" in r.stdout
    assert "Traceback" not in r.stderr and r.stderr.strip() == ""
    assert instantaneo(ws) == antes


def test_documento_vazio_diz_o_que_provavelmente_aconteceu_e_sai_1(tmp_path):
    """Antes disto o usuário via '0 lidas · 0 classificadas', a conciliação passava vazia e a
    rodada terminava como se o documento estivesse em dia."""
    ws, doc = prepara(tmp_path, "Data,Histórico,Valor,Saldo\n")
    antes = instantaneo(ws)
    r = roda(ws, doc)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "nenhuma linha de dados abaixo do cabeçalho" in r.stdout
    assert "inspecionar_extrato.py" in r.stdout
    assert "aba errada" in r.stdout
    assert "Traceback" not in r.stderr
    assert instantaneo(ws) == antes


def test_uso_invalido_sai_2(tmp_path):
    r = subprocess.run([sys.executable, str(CLI)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 2, r.stdout + r.stderr


def test_sobrevive_a_console_cp1252(tmp_path):
    """O output tem ·, ← e — , que não existem em cp1252: sem o reconfigure o CLI morreria
    com UnicodeEncodeError em vez de importar."""
    ws, doc = prepara(tmp_path)
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    r = roda(ws, doc, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "UnicodeEncodeError" not in r.stderr and "Traceback" not in r.stderr
    assert "Gravado em dados/" in r.stdout
