import datetime
import subprocess
import sys
from pathlib import Path

from po.estado import gerar_estado, render_estado
from po.validar import validar
from test_atualizar_cotacoes import CONFIG_DUAS_CONTAS
from test_validar_dados import _anexa, copia_exemplo

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_esta_regenerado_pelo_gerador():
    """O ESTADO.md do exemplo é exatamente o que o gerador produz (drift = teste vermelho)."""
    esperado = render_estado(EXEMPLO, hoje=datetime.date(2026, 9, 8))
    assert (EXEMPLO / "estado" / "ESTADO.md").read_text(encoding="utf-8") == esperado


def test_gera_total_tabela_e_pendencias(tmp_path):
    ws = copia_exemplo(tmp_path)
    caminho, _ = gerar_estado(ws, hoje=datetime.date(2026, 9, 8))
    texto = caminho.read_text(encoding="utf-8")
    assert "gerado-por: gerar-estado" in texto and "data-referencia: 2026-09-08" in texto
    assert "Total investido: R$ 12.000,00" in texto
    assert "| acoes-br | R$ 4.000,00 | 33 | 25-45 | dentro |" in texto
    assert "| fiis | R$ 8.000,00 | 67 | 20-40 | acima |" in texto
    assert "| rf-br | R$ 0,00 | 0 | 25-45 | abaixo |" in texto
    assert "- fiis acima da banda máxima (66,7% vs 40%)" in texto
    assert "- rf-br abaixo do mínimo (0,0% vs 25%)" in texto
    erros, avisos = validar(ws)
    assert erros == [] and avisos == []


def test_evento_pendente_e_bloco_sem_banda_viram_pendencia(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/eventos.csv", "2026-09-08,PETR4,variacao-anomala,-50%,nao")
    _anexa(ws, "dados/posicoes.csv", "BTC,cripto,corretora-br,0.01,300000.00,BRL")
    _anexa(ws, "dados/fills.csv", "2026-08-01,BTC,saldo-inicial,0.01,300000.00,0,corretora-br,BRL")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,BTC,400000.00,BRL,manual")
    texto = gerar_estado(ws, hoje=datetime.date(2026, 9, 8))[1]
    assert "| cripto | R$ 4.000,00 | 25 | — | sem banda |" in texto
    assert "- cripto tem posição mas nenhuma banda declarada" in texto
    assert "- 1 evento(s) em eventos.csv aguardando confirmação (PETR4)" in texto
    erros, _ = validar(ws)
    assert erros == []


def test_sem_cotacao_nao_gera_e_declara(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "VALE3,acoes-br,corretora-br,10,60.00,BRL")
    try:
        gerar_estado(ws)
        assert False, "deveria ter levantado"
    except ValueError as e:
        assert "VALE3 sem cotação" in str(e)
    assert (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8") == antes


# --- CLI scripts/gerar_estado.py: todo erro é frase acionável, nunca traceback ---

MOTOR = Path(__file__).resolve().parent.parent
GERADOR = MOTOR / "scripts" / "gerar_estado.py"


def _roda(*args, env=None):
    import os
    return subprocess.run([sys.executable, str(GERADOR), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, **(env or {})})


def test_cli_regenera_e_imprime_total_e_pendencias(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = _roda(str(ws), "--data", "2026-09-08")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "estado/ESTADO.md regenerado — Total investido: R$ 12.000,00" in r.stdout
    assert "- fiis acima da banda máxima (66,7% vs 40%)" in r.stdout
    assert "data-referencia: 2026-09-08" in (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8")


def test_cli_caminho_relativo_funciona(tmp_path):
    """O comando documentado passa caminho relativo; o relative_to do print exige raiz resolvida."""
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(GERADOR), "ws"], cwd=tmp_path, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0 and "estado/ESTADO.md regenerado" in r.stdout, r.stdout + r.stderr
    assert ws.exists()


def test_cli_data_malformada_e_frase_e_nao_grava(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8")
    r = _roda(str(ws), "--data", "08/09/2026")
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "--data inválida" in r.stdout and "AAAA-MM-DD" in r.stdout
    assert (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8") == antes


def test_cli_workspace_inexistente_e_frase(tmp_path):
    r = _roda(str(tmp_path / "nao-existe"))
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "não existe" in r.stdout


def test_cli_csv_ausente_e_frase_nao_errno_cru(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "cotacoes.csv").unlink()
    r = _roda(str(ws))
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "dados/cotacoes.csv não encontrado" in r.stdout
    assert "Errno" not in r.stdout


def test_cli_estado_travado_vira_frase_de_arquivo_aberto(tmp_path):
    """Pasta no lugar do ESTADO.md: OSError que não é FileNotFoundError, o caso 'aberto no Excel'."""
    ws = copia_exemplo(tmp_path)
    alvo = ws / "estado" / "ESTADO.md"
    alvo.unlink()
    alvo.mkdir()
    r = _roda(str(ws))
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "não consegui ler/gravar estado/ESTADO.md" in r.stdout
    assert "aberto no Excel" in r.stdout


def test_cli_sobrevive_a_console_cp1252(tmp_path):
    """A saída tem — e ·, que não existem em cp1252: sem preparar_console() o CLI morria
    com UnicodeEncodeError em vez de imprimir o total."""
    ws = copia_exemplo(tmp_path)
    r = _roda(str(ws), "--data", "2026-09-08", env={"PYTHONIOENCODING": "cp1252"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Total investido: R$ 12.000,00" in r.stdout


# --- C1: quem decide a banda é a fração exata, não o percentual arredondado da tabela ---

HOJE = datetime.date(2026, 9, 10)   # dois dias depois da cotação do exemplo: nada envelheceu


def _cotacoes(ws, *linhas):
    """Reescreve cotacoes.csv inteiro. Anexar sobre o arquivo do exemplo deixaria a data/hora
    decidindo o preço vencedor, e o que estes testes exercitam é o veredito de banda."""
    (ws / "dados" / "cotacoes.csv").write_text(
        "data,hora,ticker,preco,moeda,fonte\n" + "".join(l + "\n" for l in linhas), encoding="utf-8")


def _linha(texto, prefixo):
    return next(l for l in texto.splitlines() if l.startswith(prefixo))


def test_fracao_acima_do_maximo_que_arredonda_para_o_maximo_e_acima(tmp_path):
    """45,4% com máximo 45 arredonda para 45. Decidindo sobre o inteiro, o ESTADO dizia 'dentro'
    e não abria pendência: o número certo com o veredito errado, no arquivo que existe para dar
    o veredito. A tabela segue mostrando o inteiro; a decisão e a pendência usam a fração."""
    ws = copia_exemplo(tmp_path)
    _cotacoes(ws, "2026-09-08,18:00,PETR4,45.40,BRL,manual",
                  "2026-09-08,18:00,HGLG11,109.20,BRL,manual")
    texto = render_estado(ws, hoje=HOJE)
    assert _linha(texto, "| acoes-br") == "| acoes-br | R$ 4.540,00 | 45 | 25-45 | acima |"
    assert "- acoes-br acima da banda máxima (45,4% vs 45%): rebalancear via aporte" in texto


def test_fracao_abaixo_do_minimo_que_arredonda_para_o_minimo_e_abaixo(tmp_path):
    """A outra ponta do mesmo defeito: 24,6% com mínimo 25 arredondava para 25 e virava 'dentro'."""
    ws = copia_exemplo(tmp_path)
    _cotacoes(ws, "2026-09-08,18:00,PETR4,24.60,BRL,manual",
                  "2026-09-08,18:00,HGLG11,150.80,BRL,manual")
    texto = render_estado(ws, hoje=HOJE)
    assert _linha(texto, "| acoes-br") == "| acoes-br | R$ 2.460,00 | 25 | 25-45 | abaixo |"
    assert "- acoes-br abaixo do mínimo (24,6% vs 25%): priorizar nos próximos aportes" in texto


def test_fracao_no_meio_da_banda_continua_dentro_e_sem_pendencia(tmp_path):
    """Controle: a fração exata não pode transformar bloco saudável em pendência."""
    ws = copia_exemplo(tmp_path)
    _cotacoes(ws, "2026-09-08,18:00,PETR4,35.00,BRL,manual",
                  "2026-09-08,18:00,HGLG11,130.00,BRL,manual")
    texto = render_estado(ws, hoje=HOJE)
    assert _linha(texto, "| acoes-br") == "| acoes-br | R$ 3.500,00 | 35 | 25-45 | dentro |"
    assert not any(l.startswith("- acoes-br") for l in texto.splitlines())


# --- I1: cotação e câmbio velhos viram pendência, não patrimônio silencioso de hoje ---

def test_cotacao_velha_vira_pendencia_nomeando_ticker_e_idade(tmp_path):
    """Preço de 2019 virava patrimônio de hoje com o validador verde: a data mais antiga era só
    impressa na linha de rodapé, sem pendência."""
    ws = copia_exemplo(tmp_path)
    _cotacoes(ws, "2026-09-08,18:00,PETR4,40.00,BRL,manual",
                  "2019-01-02,18:00,HGLG11,160.00,BRL,manual")
    idade = (HOJE - datetime.date(2019, 1, 2)).days
    pend = _linha(render_estado(ws, hoje=HOJE), "- cotação com mais de 7 dias")
    assert f"HGLG11 (2019-01-02, {idade} dias)" in pend
    assert "PETR4" not in pend and "atualizar_cotacoes.py" in pend


def test_cambio_velho_vira_pendencia_mesmo_com_cotacao_fresca(tmp_path):
    """O câmbio converte o preço de hoje: velho, ele erra o patrimônio inteiro do bloco em moeda
    estrangeira sem que nenhum ticker apareça como desatualizado."""
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=MOTOR.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "AAPL,rv-int,corretora-us,2,200.00,USD")
    _anexa(ws, "dados/fills.csv", "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,AAPL,230.00,USD,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-08-01,00:00,USDBRL,5.00,BRL,manual")
    idade = (HOJE - datetime.date(2026, 8, 1)).days
    texto = render_estado(ws, hoje=HOJE)
    assert f"- câmbio USDBRL de 2026-08-01 ({idade} dias) convertendo preço de hoje" in texto
    assert not any("mais de 7 dias" in l for l in texto.splitlines())   # nenhum ticker envelheceu


def test_exemplo_na_data_de_referencia_nao_tem_pendencia_de_idade():
    """Controle do limiar: o `hoje` atravessa render_estado até valorar justamente para o exemplo
    do repo não começar a acusar cotação velha sozinho quando a data real passar do limiar."""
    texto = render_estado(EXEMPLO, hoje=datetime.date(2026, 9, 8))
    assert "mais de 7 dias" not in texto and "câmbio" not in texto


# --- I4: bloco duplicado na política soma duas vezes na tabela do ESTADO ---

def test_bloco_duplicado_na_politica_impede_gerar_o_estado(tmp_path):
    """A tabela de bandas repetida saía duas vezes na tabela do ESTADO e a soma dela passava do
    'Total investido' impresso logo acima — no arquivo que o cabeçalho diz ser gerado e confiável."""
    ws = copia_exemplo(tmp_path)
    antes = (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8")
    p = ws / "politica" / "01-alocacao-alvo.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "| fiis | 20 | 30 | 40 |", "| fiis | 20 | 30 | 40 |\n| fiis | 20 | 30 | 40 |"), encoding="utf-8")
    try:
        gerar_estado(ws, hoje=HOJE)
        assert False, "deveria ter levantado"
    except ValueError as e:
        assert "'fiis' duplicado" in str(e)
    assert (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8") == antes


# --- I5: a frase de bloco sem banda mora em um lugar só ---

def test_frase_de_sem_banda_aparece_exatamente_uma_vez(tmp_path):
    """A frase estava duplicada palavra por palavra entre carteira.py e estado.py, e
    Carteira.avisos não tinha consumidor. Agora o ESTADO estende as pendências com c.avisos:
    consumir os dois lados sem apagar o local imprimiria a pendência em dobro."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/posicoes.csv", "BTC,cripto,corretora-br,1,100000.00,BRL")
    _anexa(ws, "dados/fills.csv", "2026-08-01,BTC,saldo-inicial,1,100000.00,0,corretora-br,BRL")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,BTC,120000.00,BRL,manual")
    texto = render_estado(ws, hoje=HOJE)
    assert sum(1 for l in texto.splitlines() if "nenhuma banda declarada" in l) == 1
    assert "| cripto | R$ 120.000,00 | 91 | — | sem banda |" in texto
