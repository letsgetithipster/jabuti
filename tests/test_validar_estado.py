import datetime
import shutil
from pathlib import Path

import pytest

from po.csvs import anexar_csv
from po.estado import gerar_estado
from po.validar.check_estado import checar_estado
from test_atualizar_cotacoes import CONFIG_DUAS_CONTAS
from test_validar_dados import MOTOR, _anexa, copia_exemplo

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_total_bate():
    erros, _ = checar_estado(EXEMPLO)
    assert erros == []


def test_total_divergente_e_erro(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    estado = ws / "estado" / "ESTADO.md"
    texto = estado.read_text(encoding="utf-8")
    estado.write_text(texto.replace("R$ 12.000,00", "R$ 99.000,00"), encoding="utf-8")
    erros, _ = checar_estado(ws)
    # Desde que o check compara o arquivo inteiro, o que esta asserção pina é a mensagem embutir
    # a linha divergente — é por ela que o erro diz onde olhar, e não só que algo difere.
    assert any("Total investido" in e for e in erros)


def test_ticker_sem_cotacao_vira_aviso(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cot = ws / "dados" / "cotacoes.csv"
    linhas = [l for l in cot.read_text(encoding="utf-8").splitlines() if "HGLG11" not in l]
    cot.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []      # sem cotação para todos, a comparação é suspensa...
    assert any("HGLG11" in a for a in avisos)   # ...mas avisa


def test_ultima_cotacao_por_data_nao_por_linha(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") +
                   "2026-09-01,18:00,PETR4,10.00,BRL,manual\n", encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert erros == []  # linha velha appendada depois não vence a data mais nova


def test_moeda_sem_cambio_declarado_suspende(tmp_path):
    """Antes este teste se chamava test_moeda_nao_brl_suspende, e o nome era verdade:
    qualquer posição não-BRL desligava o check. Não é mais — o que suspende é a FALTA do par
    de câmbio, e o aviso tem que nomear o par que falta para a suspensão ser acionável."""
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") +
                   "VOO,rv-int,corretora-br,2,500.00,USD\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") +
                     "2026-08-01,VOO,saldo-inicial,2,500.00,0,corretora-br,USD\n", encoding="utf-8")
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") +
                   "2026-09-08,18:00,VOO,510.00,USD,manual\n", encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspensa" in a and "sem câmbio USDBRL" in a for a in avisos)


def test_mensagem_de_divergencia_em_ptbr(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    estado = ws / "estado" / "ESTADO.md"
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 9.000,00"),
                      encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert any("R$ 9.000,00" in e and "12.000,00" in e for e in erros)


def test_dados_com_erro_suspende_com_aviso(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    (ws / "dados" / "posicoes.csv").write_text(
        "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,cem,30.00,BRL\n",
        encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspensa" in a for a in avisos)


def test_estado_nao_utf8_vira_erro(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    (ws / "estado" / "ESTADO.md").write_bytes(
        "---\ntipo: estado\n---\nTotal investido: R$ 1,00 ação\n".encode("latin-1"))
    erros, _ = checar_estado(ws)
    assert any("UTF-8" in e for e in erros)


# --- C2: o check consome po/carteira.py, o cálculo único, em vez de recalcular por conta ---

def test_total_adulterado_com_carteira_multi_moeda_e_erro(tmp_path):
    """O check antigo não conhecia câmbio: bastava UMA posição não-BRL para o único guarda-corpo
    do arquivo gerado desligar inteiro, com aviso e zero erros. Medido: total trocado à mão para
    R$ 999.999,00 contra R$ 14.300,00 reais, e o validador passava."""
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=MOTOR.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "AAPL,rv-int,corretora-us,2,200.00,USD")
    _anexa(ws, "dados/fills.csv", "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,AAPL,230.00,USD,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,00:00,USDBRL,5.00,BRL,manual")
    estado = ws / "estado" / "ESTADO.md"
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 999.999,00"),
                      encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert any("999.999,00" in e and "14.300,00" in e for e in erros), (erros, avisos)
    assert not any("suspensa" in a for a in avisos)


def test_multi_moeda_com_total_correto_nao_acusa(tmp_path):
    """A outra ponta: o check passou a valer para carteira em dólar, então ele tem que ficar
    calado quando o número está certo, e não trocar um falso-negativo por um falso-positivo.

    O "número certo" deixou de ser a linha do total escrita à mão: o check compara o arquivo
    inteiro, e um ESTADO com o total corrigido a dedo mas a tabela de blocos velha é justamente
    a edição à mão que ele existe para pegar. O jeito de ter o número certo é regenerar."""
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=MOTOR.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "AAPL,rv-int,corretora-us,2,200.00,USD")
    _anexa(ws, "dados/fills.csv", "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,AAPL,230.00,USD,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,00:00,USDBRL,5.00,BRL,manual")
    _caminho, texto = gerar_estado(ws, hoje=datetime.date(2026, 9, 8))
    assert "R$ 14.300,00" in texto, texto
    assert checar_estado(ws) == ([], [])


def test_posicao_sem_cotacao_continua_suspendendo_com_aviso_e_nao_erro(tmp_path):
    """A suspensão legítima não virou erro no caminho: quando a valoração recusa número parcial,
    a comparação suspende e nomeia a causa. Quem acusa a origem é o check de dados."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/posicoes.csv", "VALE3,acoes-br,corretora-br,10,60.00,BRL")
    _anexa(ws, "dados/fills.csv", "2026-08-01,VALE3,saldo-inicial,10,60.00,0,corretora-br,BRL")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspensa" in a and "VALE3 sem cotação" in a for a in avisos)


# --- A3: ancoragem temporal — o gerado se confere contra si mesmo e contra os inputs ---

def test_estado_identico_ao_render_ancorado_passa(tmp_path):
    ws = copia_exemplo(tmp_path)
    assert checar_estado(ws) == ([], [])


def test_estado_nao_vence_com_o_calendario(tmp_path, monkeypatch):
    """A3: comparar contra date.today() daria erro todo dia seguinte ao da geração, sem que
    nenhum dado tivesse mudado. O check ancora no data-referencia do PRÓPRIO arquivo."""
    ws = copia_exemplo(tmp_path)
    import po.validar.check_estado as ce

    class Congelado(datetime.date):
        @classmethod
        def today(cls):
            return datetime.date(2031, 1, 1)

    monkeypatch.setattr(ce.datetime, "date", Congelado)
    assert checar_estado(ws) == ([], [])


def test_edicao_a_mao_no_estado_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    alvo = ws / "estado" / "ESTADO.md"
    texto = alvo.read_text(encoding="utf-8")
    assert texto.count("R$ 12.000,00") == 1
    alvo.write_text(texto.replace("R$ 12.000,00", "R$ 99.000,00"), encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert erros and "gerar_estado.py" in erros[0], erros


def test_estado_mais_velho_que_os_dados_e_aviso(tmp_path):
    """Idade de arquivo gerado se mede contra os inputs, nunca contra o relógio: é isso que faz
    o exemplo do repo nunca vencer e o workspace real avisar no instante certo."""
    ws = copia_exemplo(tmp_path)
    anexar_csv("cotacoes", ws / "dados" / "cotacoes.csv",
               [{"data": "2026-09-30", "hora": "18:00", "ticker": "PETR4",
                 "preco": 41.0, "moeda": "BRL", "fonte": "manual"}])
    erros, avisos = checar_estado(ws)
    assert any("regenere" in a for a in avisos), avisos


def test_estado_sem_data_referencia_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    alvo = ws / "estado" / "ESTADO.md"
    texto = alvo.read_text(encoding="utf-8")
    assert texto.count("data-referencia: 2026-09-08\n") == 1
    alvo.write_text(texto.replace("data-referencia: 2026-09-08\n", ""), encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert erros and "data-referencia" in erros[0]


# --- A3, segunda volta: as guardas que faltavam ao que a task passou a saber fazer ---

@pytest.mark.parametrize("antes,depois,trecho", [
    ("| fiis | R$ 8.000,00 | 67 | 20-40 | acima |",
     "| fiis | R$ 8.000,00 | 67 | 20-99 | dentro |", "20-99"),
    ("- fiis acima da banda máxima (66,7% vs 40%): rebalancear via aporte nos blocos abaixo\n",
     "", "fiis acima da banda"),
    ("| acoes-br | R$ 4.000,00 | 33 | 25-45 | dentro |",
     "| acoes-br | R$ 40.000,00 | 33 | 25-45 | dentro |", "R$ 40.000,00"),
])
def test_edicao_a_mao_fora_da_linha_do_total_e_erro(tmp_path, antes, depois, trecho):
    """A linha do total o check antigo já pegava, por regex. O que esta task acrescentou é
    comparar o ARQUIVO INTEIRO: banda, desvio, pendência e valor de bloco também são acusados.
    Sem esta função, reduzir a comparação de volta à linha do total deixa a suíte verde e as
    três adulterações acima passam batido."""
    ws = copia_exemplo(tmp_path)
    alvo = ws / "estado" / "ESTADO.md"
    texto = alvo.read_text(encoding="utf-8")
    assert texto.count(antes) == 1
    alvo.write_text(texto.replace(antes, depois), encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert erros and trecho in erros[0] and "gerar_estado.py" in erros[0], erros


def test_fill_mais_novo_que_o_estado_e_aviso(tmp_path):
    """As duas fontes de input do ESTADO são guardadas, não só cotacoes.csv. O fill que entra
    sem regeneração é o caso que a decisão desta task chama de 'o que interessa': num workspace
    real é ele, e não a cotação, que muda o patrimônio sem ninguém avisar."""
    ws = copia_exemplo(tmp_path)
    anexar_csv("fills", ws / "dados" / "fills.csv",
               [{"data": "2026-09-30", "ticker": "PETR4", "tipo": "compra", "qty": 50,
                 "preco": 36.0, "taxa": 0, "conta": "corretora-br", "moeda": "BRL"}])
    _erros, avisos = checar_estado(ws)
    assert any("2026-09-30" in a and "regenere" in a for a in avisos), avisos


def test_estado_sem_quebra_final_nomeia_a_quebra_e_nao_se_contradiz(tmp_path):
    """Salvar o ESTADO sem \n no fim (editor, copiar-colar) é alcançável e não passa por
    splitlines(): o arquivo difere, a varredura linha a linha não acha divergente e a mensagem
    dizia 'difere ... (os arquivos são iguais)' na mesma frase. Erro que se autocontradiz não é
    frase acionável."""
    ws = copia_exemplo(tmp_path)
    alvo = ws / "estado" / "ESTADO.md"
    alvo.write_text(alvo.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert erros, erros
    assert "quebra de linha" in erros[0], erros[0]
    assert "os arquivos são iguais" not in erros[0], erros[0]


def test_data_referencia_impossivel_e_erro_em_ptbr(tmp_path):
    """2026-13-45 casa o formato AAAA-MM-DD e não existe no calendário. O ValueError do
    fromisoformat caía no except da comparação e virava aviso em inglês ('month must be in
    1..12'): rebaixava erro a aviso e não dizia que o problema estava no frontmatter do ESTADO."""
    ws = copia_exemplo(tmp_path)
    alvo = ws / "estado" / "ESTADO.md"
    texto = alvo.read_text(encoding="utf-8")
    assert texto.count("data-referencia: 2026-09-08") == 1
    alvo.write_text(texto.replace("data-referencia: 2026-09-08", "data-referencia: 2026-13-45"),
                    encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros and "data-referencia" in erros[0] and "2026-13-45" in erros[0], (erros, avisos)
    assert not any("month must be" in a for a in avisos), avisos
