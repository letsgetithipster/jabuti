import datetime
import re
import shutil
from pathlib import Path

from po import csvs
from po.estado import gerar_estado
from po.validar import validar
from po.validar.check_dados import checar_dados

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"
MOTOR = EXEMPLO.parent.parent


def copia_exemplo(tmp_path):
    """Copia o exemplo e absolutiza o motor (o '../..' relativo só vale in-place)."""
    destino = tmp_path / "ws"
    shutil.copytree(EXEMPLO, destino)
    cfg = destino / "vault.config.yaml"
    texto = re.sub(r"motor: '[^']*'", f"motor: '{MOTOR.as_posix()}'",
                   cfg.read_text(encoding="utf-8"))
    cfg.write_text(texto, encoding="utf-8")
    return destino


def _workspace_antigo(ws):
    """Workspace nascido de motor anterior: dados/posicoes.csv ainda no disco, com o que o exemplo
    carregava antes de G1 tirar a tabela do template e do exemplo. Só os checks retrocompatíveis
    (zero silencioso, ativos.csv ausente) ainda a leem."""
    (ws / "dados" / "posicoes.csv").write_text(
        "ticker,classe,conta,qty,pm,moeda\n"
        "PETR4,acoes-br,corretora-br,100,30.00,BRL\n"
        "HGLG11,fiis,corretora-br,50,155.00,BRL\n", encoding="utf-8")
    return ws


def test_workspace_exemplo_sem_erros():
    erros, _ = checar_dados(EXEMPLO)
    assert erros == []


def test_fill_sem_classe_declarada_e_erro_acionavel(tmp_path):
    """Spec §3, divergência 3: fill de ticker sem linha em ativos.csv é erro com a linha a
    acrescentar. Antes o mesmo caso era 'fills na conta mas não existe em posicoes.csv'."""
    ws = copia_exemplo(tmp_path)
    fills = ws / "dados" / "fills.csv"
    conteudo = fills.read_text(encoding="utf-8")
    fills.write_text(conteudo + "2026-09-06,VALE3,compra,10,60.00,0,corretora-br,BRL\n",
                     encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("dados/ativos.csv: VALE3 tem fill mas nenhuma classe declarada" in e
               and " ativo VALE3=<classe>" in e for e in erros), erros


def test_conta_desconhecida_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _troca(ws, "dados/fills.csv", "corretora-br", "conta-fantasma")
    erros, _ = checar_dados(ws)
    assert any("conta-fantasma" in e and "não declarada" in e for e in erros)


def test_posicao_declarada_sem_fill_e_erro_com_a_linha_do_saldo_inicial(tmp_path):
    """B2: com a posição derivada do ledger, ITSA4 declarada só na posicoes.csv de um workspace
    antigo vale zero no ESTADO. Antes era aviso ("PM não verificável") e o gerador publicava o
    total sem ela."""
    ws = _workspace_antigo(copia_exemplo(tmp_path))
    _anexa(ws, "dados/posicoes.csv", "ITSA4,acoes-br,corretora-br,200,9.50,BRL")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,ITSA4,9.60,BRL,manual")
    erros, avisos = checar_dados(ws)
    assert any("ITSA4" in e and "sem nenhum fill" in e and
               "AAAA-MM-DD,ITSA4,saldo-inicial,200,9.5,0,corretora-br,BRL" in e for e in erros), erros
    assert not any("PM não verificável" in a for a in avisos), avisos


def test_venda_no_saldo(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text(
        "data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
        "2026-08-01,HGLG11,saldo-inicial,50,155.00,0,corretora-br,BRL\n"
        "2026-08-05,PETR4,compra,90,29.50,0,corretora-br,BRL\n"
        "2026-08-20,PETR4,compra,30,30.00,0,corretora-br,BRL\n"
        "2026-09-05,PETR4,venda,20,31.00,0,corretora-br,BRL\n",
        encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert erros == []  # 90 + 30 - 20 = 100: o ledger fecha sozinho, não há tabela para cruzar


def test_multi_conta_importada_e_permitida(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    # v2 também acusa o mesmo ticker em mais de uma moeda entre contas (cotacoes.csv só
    # guarda uma cotação vencedora por ticker); a segunda conta deste teste fica em BRL,
    # igual à primeira, pra manter o que o teste exercita (multi-conta, não multi-moeda).
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        "contas:", 'contas:\n  - id: corretora-br-2\n    nome: "Segunda corretora"\n    moeda: BRL'),
        encoding="utf-8")
    _anexa(ws, "dados/fills.csv", "2026-08-01,PETR4,saldo-inicial,50,28.00,0,corretora-br-2,BRL")
    erros, _ = checar_dados(ws)
    assert erros == []  # posição em outra conta, mesma moeda, com o saldo-inicial dela: permitida


def test_posicao_declarada_em_conta_sem_fill_dessa_conta_e_erro(tmp_path):
    """Sonda da revisão do F1.6 (RB2b): a chave do check do zero silencioso caía para só o ticker
    com a suíte verde. PETR4 tem fill em corretora-br; a linha de corretora-br-2 sem fill próprio
    é zero no ledger dessa conta e sumiria do ESTADO em silêncio se a chave não carregasse a
    conta."""
    ws = _workspace_antigo(copia_exemplo(tmp_path))
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        "contas:", 'contas:\n  - id: corretora-br-2\n    nome: "Segunda corretora"\n    moeda: BRL'),
        encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "PETR4,acoes-br,corretora-br-2,50,28.00,BRL")
    erros, _ = checar_dados(ws)
    assert any("PETR4 (corretora-br-2) sem nenhum fill" in e and
               "AAAA-MM-DD,PETR4,saldo-inicial,50,28,0,corretora-br-2,BRL" in e for e in erros), erros
    assert not any("PETR4 (corretora-br) sem nenhum fill" in e for e in erros), erros


def test_leitura_suja_pula_cross_check(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text(
        "data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
        "2026-08-05,PETR4,compra,cem,29.50,0,corretora-br,BRL\n",
        encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("formato canônico" in e for e in erros)
    assert not any("difere do saldo" in e for e in erros)


def test_csv_ausente(tmp_path):
    """Tabela de TABELAS_DADOS ausente é erro. `movimentacoes` está fora desta cobrança: continua
    em SCHEMAS (o motor sabe lê-la) e volta a ser exigida no commit que trouxer o executor dela;
    `indices` saiu de SCHEMAS inteira."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "proventos.csv").unlink()
    erros, _ = checar_dados(ws)
    assert any("proventos.csv ausente" in e for e in erros)


def test_motor_nao_substituido(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    texto = re.sub(r"motor: '[^']*'", "motor: __MOTOR__", cfg.read_text(encoding="utf-8"))
    cfg.write_text(texto, encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("não foi substituído" in e for e in erros)


def test_motor_invalido(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    texto = re.sub(r"motor: '[^']*'", "motor: 'C:/nao/existe'", cfg.read_text(encoding="utf-8"))
    cfg.write_text(texto, encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("motor" in e for e in erros)


def _troca(ws, rel, antigo, novo):
    p = ws / rel
    p.write_text(p.read_text(encoding="utf-8").replace(antigo, novo), encoding="utf-8")


def _anexa(ws, rel, linha):
    p = ws / rel
    p.write_text(p.read_text(encoding="utf-8") + linha + "\n", encoding="utf-8")


def test_posicoes_csv_sem_nenhum_fill_nao_e_zero_silencioso(tmp_path):
    """O caso duro do fechamento da Fase 1: workspace nascido de motor anterior, posicoes.csv
    cheia e fills.csv só com cabeçalho. Medido em 17382c1: antigo R$ 3.000,00, novo R$ 0,00,
    exit 0 no gerador e 0 erro(s) no validador. O gerador continua publicando o que o ledger
    diz (zero); o validador é quem barra, com a linha que abre cada posição."""
    ws = _workspace_antigo(copia_exemplo(tmp_path))
    (ws / "dados" / "fills.csv").write_text("data,ticker,tipo,qty,preco,taxa,conta,moeda\n", encoding="utf-8")
    assert "Total investido: R$ 0,00" in gerar_estado(ws, hoje=datetime.date(2026, 9, 8))[1]
    erros, _ = validar(ws)
    assert [e for e in erros if "sem nenhum fill" in e] == [
        "posicoes.csv: PETR4 (corretora-br) sem nenhum fill — a posição derivada do ledger é zero e o "
        "ESTADO publicaria R$ 0,00. Registre um saldo-inicial em fills.csv: "
        "AAAA-MM-DD,PETR4,saldo-inicial,100,30,0,corretora-br,BRL",
        "posicoes.csv: HGLG11 (corretora-br) sem nenhum fill — a posição derivada do ledger é zero e o "
        "ESTADO publicaria R$ 0,00. Registre um saldo-inicial em fills.csv: "
        "AAAA-MM-DD,HGLG11,saldo-inicial,50,155,0,corretora-br,BRL"], erros


def test_venda_que_zera_posicao_nao_exige_linha_em_posicoes(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-07-01,VALE3,compra,10,60.00,0,corretora-br,BRL")
    _anexa(ws, "dados/fills.csv", "2026-07-15,VALE3,venda,10,65.00,0,corretora-br,BRL")
    erros, _ = checar_dados(ws)
    assert not any("VALE3" in e for e in erros)


def test_venda_acima_do_saldo_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-09-06,PETR4,venda,500,40.00,0,corretora-br,BRL")
    erros, _ = checar_dados(ws)
    assert any("excede o saldo" in e for e in erros)


def test_moeda_da_linha_diferente_da_conta_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _troca(ws, "dados/fills.csv", "2026-08-01,HGLG11,saldo-inicial,50,155.00,0,corretora-br,BRL",
           "2026-08-01,HGLG11,saldo-inicial,50,155.00,0,corretora-br,USD")
    erros, _ = checar_dados(ws)
    assert any("HGLG11" in e and "USD" in e and "conta corretora-br é BRL" in e for e in erros)


def test_posicao_sem_cotacao_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text("\n".join(l for l in cot.read_text(encoding="utf-8").splitlines() if "HGLG11" not in l) + "\n",
                   encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("HGLG11" in e and "sem nenhuma cotação" in e for e in erros)


def test_cotacao_fora_de_ordem_e_aviso(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/cotacoes.csv", "2026-08-15,18:00,PETR4,37.00,BRL,manual")
    erros, avisos = checar_dados(ws)
    assert erros == []
    assert any("PETR4" in a and "fora de ordem" in a for a in avisos)


def test_provento_sem_posicao_e_aviso(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/proventos.csv", "2026-09-05,VALE3,,dividendo,10.00,10.00,corretora-br,BRL")
    erros, avisos = checar_dados(ws)
    assert erros == []
    assert any("VALE3" in a and "sem posição" in a for a in avisos)


def test_evento_anomalo_confirmado_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/eventos.csv", "2026-09-08,PETR4,variacao-anomala,-52.3% vs 2026-09-01,sim")
    erros, _ = checar_dados(ws)
    assert any("variacao-anomala" in e and "troque o tipo" in e for e in erros)


def test_split_confirmado_sem_razao_e_erro_do_ledger_alem_do_aviso(tmp_path):
    """Desde que check_dados passa os eventos ao ledger, split confirmado sem razão é ERRO: a
    posição derivada do ticker fica desconhecida, e sob derivação isso não pode passar como
    aviso. O aviso continua porque é ele que aponta a LINHA do CSV; o erro aponta o efeito."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/eventos.csv", "2026-09-08,PETR4,split,,sim")
    erros, avisos = checar_dados(ws)
    assert any("PETR4" in e and "novas:antigas" in e for e in erros), erros
    assert any("split" in a and "sem razão" in a for a in avisos)


def test_venda_sem_posicao_nao_gera_erro_derivado(tmp_path):
    """O erro de origem (venda sem saldo) é o único: a posição suspeita não entra na carteira
    derivada, então não nasce um segundo erro pedindo cotação para ela."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "VALE3,acoes-br")
    _anexa(ws, "dados/fills.csv", "2026-09-07,VALE3,venda,5,60.00,0,corretora-br,BRL")
    erros, avisos = checar_dados(ws)
    assert any("excede o saldo" in e for e in erros)
    assert not any("VALE3 sem nenhuma cotação" in e for e in erros)      # erro derivado


def test_erro_no_ledger_suspende_comparacao_de_qty(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-09-06,PETR4,venda,500,40.00,0,corretora-br,BRL")
    erros, _ = checar_dados(ws)
    assert any("excede o saldo" in e for e in erros)
    assert not any("difere do saldo dos fills" in e for e in erros)


def test_cotacao_em_moeda_diferente_da_posicao_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _troca(ws, "dados/cotacoes.csv", "2026-09-08,18:00,HGLG11,160.00,BRL,manual",
           "2026-09-08,18:00,HGLG11,160.00,USD,manual")
    erros, _ = checar_dados(ws)
    assert any("HGLG11" in e and "cotado em USD" in e for e in erros)


def test_moeda_divergente_em_fills_e_proventos(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/proventos.csv", "2026-09-06,HGLG11,,rendimento,10.00,10.00,corretora-br,USD")
    _anexa(ws, "dados/fills.csv", "2026-09-06,HGLG11,compra,1,155.00,0,corretora-br,USD")
    erros, _ = checar_dados(ws)
    assert any("proventos.csv" in e and "USD" in e and "conta corretora-br é BRL" in e for e in erros)
    assert any("fills.csv" in e and "USD" in e and "conta corretora-br é BRL" in e for e in erros)


def test_tabela_ausente_diz_como_criar(tmp_path):
    """Workspace criado antes da tabela existir precisa de frase acionável, não só de 'ausente'."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "eventos.csv").unlink()
    erros, _ = checar_dados(ws)
    assert any("eventos.csv ausente" in e and "data,ticker,tipo,razao,confirmado" in e
               for e in erros)


def test_mesmo_ticker_em_duas_moedas_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        "  - id: corretora-br\n", "  - id: corretora-us\n    nome: US\n    moeda: USD\n  - id: corretora-br\n"),
        encoding="utf-8")
    _anexa(ws, "dados/fills.csv", "2026-08-01,PETR4,saldo-inicial,10,6.00,0,corretora-us,USD")
    erros, _ = checar_dados(ws)
    assert any(e.startswith("fills.csv: PETR4 aparece em mais de uma moeda (BRL/USD)") for e in erros), erros


def test_workspace_sem_ativos_csv_so_avisa_e_diz_o_que_colar(tmp_path):
    ws = _workspace_antigo(copia_exemplo(tmp_path))
    (ws / "dados" / "ativos.csv").unlink()
    erros, avisos = checar_dados(ws)
    assert not any("ativos.csv ausente" in e for e in erros), erros
    texto = "\n".join(avisos)
    assert "dados/ativos.csv" in texto and "PETR4,acoes-br" in texto and "HGLG11,fiis" in texto
def test_tabela_fora_de_TABELAS_DADOS_ausente_nao_e_erro(tmp_path):
    """T4 achado 1: apagar `if nome not in TABELAS_DADOS: continue` revertia a intenção da Task 4
    com a suíte verde. A testemunha é `movimentacoes`: está em SCHEMAS, fora de TABELAS_DADOS e
    fora do disco do exemplo (G1), e nem por isso é acusada."""
    ws = copia_exemplo(tmp_path)
    assert "movimentacoes" in csvs.SCHEMAS and "movimentacoes" not in csvs.TABELAS_DADOS
    assert not (ws / "dados" / "movimentacoes.csv").exists()
    erros, avisos = checar_dados(ws)
    assert erros == [] and not any("ausente" in a for a in avisos), (erros, avisos)


def test_workspace_sem_ativos_csv_nem_posicoes_csv_e_erro_acionavel(tmp_path):
    """T4 achado 2: a guarda `and posicoes.csv existe` separa workspace antigo (aviso com o que
    colar) de workspace quebrado (erro com o cabeçalho). Sem ela o segundo virava aviso mole."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "ativos.csv").unlink()
    erros, _ = checar_dados(ws)
    assert "dados/ativos.csv ausente — crie o arquivo com a linha de cabeçalho: ticker,classe" in erros, erros


def test_provento_de_ticker_com_posicao_derivada_nao_avisa(tmp_path):
    """O aviso de provento olha a carteira DERIVADA dos fills: PETR4 tem saldo no ledger, então o
    provento dela não é 'sem posição'. Sonda da revisão do G1: `tickers_pos = set()` (avisar para
    todo provento) passava verde, porque só o caso positivo tinha testemunha."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/proventos.csv", "2026-09-05,PETR4,,dividendo,10.00,10.00,corretora-br,BRL")
    erros, avisos = checar_dados(ws)
    assert erros == [] and not any("sem posição" in a for a in avisos), avisos


def test_linha_suja_em_ativos_csv_nao_esconde_ticker_que_ninguem_declarou(tmp_path):
    """Revisão do G1: o filtro "com ativos.csv sujo, o 'sem classe' derivado é ruído" nunca fazia
    o que dizia. ler_csv devolve a linha suja junto com o erro, então o ticker dela SEMPRE está
    declarado (com classe inválida ou vazia) e nunca gera 'sem classe'; o que o filtro escondia
    era ITSA4 sujo calando VALE3 sem declaração nenhuma, um erro de origem independente. Os dois
    erros de origem aparecem, e nenhum derivado nasce da linha suja."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "ITSA4,classe-x")
    _anexa(ws, "dados/fills.csv", "2026-09-01,ITSA4,compra,10,9.50,0,corretora-br,BRL")
    _anexa(ws, "dados/fills.csv", "2026-09-01,VALE3,compra,10,60.00,0,corretora-br,BRL")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,ITSA4,9.60,BRL,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,VALE3,62.00,BRL,manual")
    erros, _ = checar_dados(ws)
    assert any("ativos.csv:4" in e and "'classe-x' fora do vocabulário" in e for e in erros), erros
    assert any("dados/ativos.csv: VALE3 tem fill mas nenhuma classe declarada" in e for e in erros), erros
    assert not any("ITSA4 tem fill mas nenhuma classe" in e for e in erros), erros
    assert len(erros) == 2, erros
