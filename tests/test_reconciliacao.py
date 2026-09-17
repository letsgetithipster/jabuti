"""A diferença entre o livro e a foto da corretora, feita conta e nomeada."""
import pytest

from po.ingestao.reconciliacao import explicar, fill_implicito

COMANDO = "python C:/motor/scripts/registrar.py C:/ws"


@pytest.mark.parametrize("ql,pl,qd,pd,dq,dc,preco,leitura", [
    (100, 30.00, 150, 32.00, 50.0, 1800.0, 36.0, "compra"),
    (50, 155.00, 50, 155.00, 0.0, 0.0, None, "igual"),
    (150, 32.00, 100, 32.00, -50.0, -1600.0, None, "venda"),
    (100, 30.00, 100, 31.00, 0.0, 100.0, None, "ajuste-de-custo"),
])
def test_os_quatro_casos_da_tabela(ql, pl, qd, pd, dq, dc, preco, leitura):
    d = fill_implicito(ql, pl, qd, pd)
    assert (d.delta_qty, d.delta_custo, d.preco_implicito, d.leitura) == (dq, dc, preco, leitura)


def test_compra_com_custo_que_cai_nao_inventa_preco():
    """Entraram unidades e o custo caiu: nenhum preço de compra explica isso. Devolver o
    quociente daria um preço NEGATIVO com cara de número conferido."""
    d = fill_implicito(100, 30.0, 150, 19.0)
    assert d.leitura == "compra" and d.preco_implicito is None and d.delta_custo == -150.0


def test_quantidade_fracionaria_nao_quebra_o_preco_implicito():
    d = fill_implicito(0.5, 200000.0, 0.75, 210000.0)
    assert d.leitura == "compra" and d.preco_implicito == 230000.0


def test_um_satoshi_e_divergencia_nao_ruido():
    """O ledger arredonda a 8 casas; 1e-8 a mais no documento é diferença real. A tolerância
    do ledger (1e-6) serve para dizer se a posição EXISTE, não para engolir um satoshi."""
    d = fill_implicito(0.00012345, 350000.0, 0.00012346, 350000.0)
    assert d.leitura == "compra" and d.delta_qty == 1e-8


def test_explicar_nomeia_a_aritmetica_e_entrega_o_comando():
    texto = "\n".join(explicar(fill_implicito(100, 30.0, 150, 32.0), ticker="PETR4",
                               conta="corretora-br", data="2026-09-11", qty_ledger=100,
                               pm_ledger=30.0, qty_doc=150, pm_doc=32.0, registrar=COMANDO))
    assert "o ledger tem 100 @ R$ 30,00 em 2026-09-11" in texto
    assert "o documento diz 150 @ R$ 32,00" in texto
    assert "R$ 1.800,00" in texto and "preço implícito R$ 36,00" in texto
    assert f"{COMANDO} compra PETR4 50 36,00" in texto
    assert "evento" in texto        # a segunda causa da mesma diferença é nomeada
    assert "Nada foi gravado" in texto


def test_explicar_de_venda_nao_promete_preco_que_a_foto_nao_tem():
    texto = "\n".join(explicar(fill_implicito(150, 32.0, 100, 32.0), ticker="PETR4",
                               conta="corretora-br", data="2026-09-11", qty_ledger=150,
                               pm_ledger=32.0, qty_doc=100, pm_doc=32.0, registrar=COMANDO))
    assert "venda PETR4 50 <preco-de-venda>" in texto
    assert "implícito" not in texto


def test_explicar_de_ajuste_de_custo_nao_manda_registrar_fill():
    """Quantidade bate e custo não: taxa que a corretora não soma, ou arredondamento. Inventar
    um fill aqui dobraria a posição."""
    texto = "\n".join(explicar(fill_implicito(100, 30.0, 100, 31.0), ticker="PETR4",
                               conta="corretora-br", data="2026-09-11", qty_ledger=100,
                               pm_ledger=30.0, qty_doc=100, pm_doc=31.0, registrar=COMANDO))
    assert "compra" not in texto and "venda" not in texto
    assert "nada a fazer" in texto.lower()


def test_explicar_escreve_quantidade_em_pt_br_no_texto_e_no_comando():
    """0,25 no texto e no comando: registrar.py lê pt-BR, e `:g` daria 1e-08 num satoshi."""
    texto = "\n".join(explicar(fill_implicito(0.5, 200000.0, 0.75, 210000.0), ticker="BTC",
                               conta="corretora-br", data="2026-09-11", qty_ledger=0.5,
                               pm_ledger=200000.0, qty_doc=0.75, pm_doc=210000.0, registrar=COMANDO))
    assert "o ledger tem 0,5 @ R$ 200.000,00" in texto
    assert f"{COMANDO} compra BTC 0,25 230.000,00" in texto
    assert "e-0" not in texto
