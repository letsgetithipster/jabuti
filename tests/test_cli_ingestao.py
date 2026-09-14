"""Contrato de linha de comando dos CLIs de ingestão, por subprocesso de verdade.

A Task 15 transforma este output em contrato de skill: quem chama precisa ramificar pelo
código de saída, sem parsear texto. Por isso cada código documentado tem um teste aqui.
"""
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from test_validar_dados import copia_exemplo

RAIZ = Path(__file__).resolve().parent.parent
CLI = RAIZ / "scripts" / "importar_extrato.py"
CLI_INSPECAO = RAIZ / "scripts" / "inspecionar_extrato.py"

MAPA_EXTRATO = """\
nome: teste-extrato
versao: 1
numeros: pt-BR
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
numeros: pt-BR
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
05/10/2026,RENDIMENTO HGLG11,"1.234,56","2.534,56"
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

# Posição que dados/ ainda não tem: assim a gravação tem duas tabelas para morrer no meio de,
# posicoes e o saldo-inicial em fills.
POSICOES_NOVAS = """\
Ativo,Classe,Quantidade,Preco
VALE3,acoes-br,10,60.00
"""

pytestmark = pytest.mark.slow


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
    # 1.234,56 e não 56,00: prova ponto de milhar E vírgula decimal de uma vez. Com 56,
    # um parser que devolvesse inteiro passaria — e foi assim que --manual PETR4=41.50
    # gravou 4.150,00 numa task anterior.
    assert "2026-10-05,HGLG11,,rendimento,1234.56,1234.56,corretora-br,BRL" in proventos


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
    # e, não havendo registro novo, a frase diz isso. Antes era "o documento bate com dados/",
    # que contradizia a linha logo acima quando havia lançamento novo esperando gravação
    assert "Não há registro novo" in r.stdout and "não muda dados/" in r.stdout
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


def test_conferir_sem_divergencia_mas_com_registro_novo_diz_quantos(tmp_path):
    """O outro lado da I2: nada em dados/ conflita com o documento e ainda assim há o que
    gravar. A frase final tem que dizer isso, não "o documento bate com dados/"."""
    ws, doc = prepara(tmp_path)
    antes = instantaneo(ws)
    r = roda(ws, doc, "--conferir")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "proventos: 1 nova(s), 0 já presente(s)" in r.stdout
    assert "há 1 registro(s) novo(s) a gravar" in r.stdout
    assert instantaneo(ws) == antes
    assert not (ws / "logs" / "importacoes").exists()


def test_gravacao_parcial_nomeia_o_que_entrou_e_a_rodada_seguinte_completa(tmp_path):
    """I1 de ponta a ponta, com um arquivo de verdade travado. O código de saída 1 era
    documentado como "nada gravado", e isso é falso quando a gravação morre no meio: aqui
    posicoes já entrou e fills não. O CLI tem que nomear a tabela, apontar o log e dizer como
    se recuperar, e a promessa "a importação é idempotente" tem que ser verdade na rodada
    seguinte, senão o texto é conselho ruim."""
    ws, doc = prepara(tmp_path, POSICOES_NOVAS, MAPA_POSICOES, "pos.csv")
    conferencia = ["--data", "2026-09-08", "--total-declarado", "600,00"]
    alvo = ws / "dados" / "fills.csv"
    os.chmod(alvo, stat.S_IREAD)
    try:
        r = roda(ws, doc, *conferencia)
    finally:
        os.chmod(alvo, stat.S_IWRITE)   # sem devolver a escrita o tmp_path não consegue limpar
    assert r.returncode == 1, r.stdout + r.stderr
    assert "A gravação falhou no meio" in r.stdout
    # a causa vira a MESMA frase acionável do resto do CLI, não o repr cru do OSError
    assert "dados/fills.csv" in r.stdout and "aberto no Excel" in r.stdout
    assert "OSError" not in r.stdout and "Traceback" not in r.stderr
    assert "O que chegou a entrar em dados/: posicoes +1" in r.stdout
    assert "a importação é idempotente" in r.stdout
    logs = sorted((ws / "logs" / "importacoes").glob("*.md"))
    assert len(logs) == 1
    assert f"Log: logs/importacoes/{logs[0].name}" in r.stdout
    corpo = logs[0].read_text(encoding="utf-8")
    assert "**A gravação falhou no meio**" in corpo
    assert "| posicoes | 1 | 0 |" in corpo and "| fills | 0 | 0 |" in corpo

    r2 = roda(ws, doc, *conferencia)                     # a rodada de recuperação
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "Gravado em dados/: fills +1" in r2.stdout
    posicoes = (ws / "dados" / "posicoes.csv").read_text(encoding="utf-8").splitlines()
    assert sum(1 for linha in posicoes if linha.startswith("VALE3,")) == 1     # não duplicou
    fills = (ws / "dados" / "fills.csv").read_text(encoding="utf-8").splitlines()
    abertura = [linha for linha in fills if ",VALE3," in linha]                # e a abertura nasceu
    assert abertura == ["2026-09-08,VALE3,saldo-inicial,10,60,0,corretora-br,BRL"]


def test_provento_com_liquido_negativo_sai_1_e_nada_entra_em_dados(tmp_path):
    """C2 pelo CLI, com o mapeamento real da Schwab e a fixture adulterada no ajuste de imposto
    (-$15.30 no lugar de -$1.53). Antes, dividendo líquido negativo entrava em dados/ com a
    rodada declarando "4 linha(s) conferidas"."""
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        "    moeda: BRL", "    moeda: BRL\n  - id: corretora-us\n    nome: \"Schwab\"\n    moeda: USD", 1),
        encoding="utf-8")
    (ws / "mapeamentos").mkdir(exist_ok=True)
    mapa = ws / "mapeamentos" / "teste.yaml"
    mapa.write_text((RAIZ / "mapeamentos" / "schwab-transacoes.yaml").read_text(encoding="utf-8"),
                    encoding="utf-8")
    doc = ws / "inbox" / "s.csv"
    fixture = RAIZ / "tests" / "fixtures" / "extratos" / "schwab-transacoes.csv"
    doc.write_text(fixture.read_text(encoding="utf-8").replace("-$1.53", "-$15.30"), encoding="utf-8")
    antes = instantaneo(ws)
    r = roda(ws, doc)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "depois do ajuste" in r.stdout and "sinal oposto" in r.stdout
    assert "Traceback" not in r.stderr
    assert instantaneo(ws) == antes


def _inspeciona(*args):
    return subprocess.run([sys.executable, str(CLI_INSPECAO), *[str(a) for a in args]],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_inspecionar_arquivo_inexistente_sai_1_com_frase(tmp_path):
    """Erro que sai 0 é silêncio para quem encadeia comandos: a inspeção devolvia a frase
    "arquivo não encontrado" como resultado normal, e o CLI a imprimia e saía 0."""
    r = _inspeciona(tmp_path / "nao-existe.csv")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "arquivo não encontrado" in r.stdout and "confira o caminho" in r.stdout
    assert "Traceback" not in r.stderr


def test_inspecionar_diretorio_sai_1_dizendo_que_e_diretorio(tmp_path):
    (tmp_path / "umdir").mkdir()
    r = _inspeciona(tmp_path / "umdir")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "é um diretório" in r.stdout and "Traceback" not in r.stderr


def test_inspecionar_arquivo_de_verdade_sai_0(tmp_path):
    """Controle: o código de saída tem que separar erro de sucesso, não reprovar tudo."""
    doc = tmp_path / "x.csv"
    doc.write_text("Ativo,Preco\nPETR4,30.00\n", encoding="utf-8")
    r = _inspeciona(doc)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PETR4" in r.stdout


def test_inspecionar_sem_argumento_sai_2():
    r = _inspeciona()
    assert r.returncode == 2, r.stdout + r.stderr
