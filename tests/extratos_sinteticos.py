"""Constrói fixtures xlsx sintéticas com a ESTRUTURA dos exports reais (Clear, B3), sem dado real.
Chamado pelos testes; quem usa faz pytest.importorskip('openpyxl') antes."""
import datetime


def construir_clear(caminho):
    """Extrato da conta da Clear: 13 linhas de preâmbulo, cabeçalho na linha 14 (coluna B..G, E vazia),
    lançamentos em ordem decrescente de data com saldo corrente, linha vazia e rodapé."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planilha1"
    ws.append([])
    ws.append(["", "", "", "", "", "", "Extrato da conta"])
    ws.append(["", "", "", "", "", "", "Data da consulta: 23/08/2026 20:48"])
    ws.append(["", "", "", "", "", "", "De: 01/06/2026 Até: 23/08/2026"])
    ws.append(["", "FULANO DE TAL", "", "", "", "", "Conta Clear: 000000"])
    for rotulo in ("Projeções futuras", "Resgates de Fundos/Clubes Pendentes", "Termos à vencer",
                   "Outros", "Garantias", "Operações de hoje"):
        ws.append(["", rotulo, "", "", "", "", "0"])
    ws.append(["", "Saldo total projetado", "", "", "", "", "1305.74"])
    ws.append([])
    ws.append(["", "Movimentação", "Liquidação", "Lançamento", "", "Valor (R$)", "Saldo (R$)"])
    d = datetime.datetime
    for mov, liq, lanc, valor, saldo in [
        (d(2026, 8, 20), d(2026, 8, 20), "JUROS S/ CAPITAL DE CLIENTES RENT4 S/             13", 5.74, 1305.74),
        (d(2026, 8, 14), d(2026, 8, 14), "RENDIMENTOS DE CLIENTES HGLG11 S/             90", 99.00, 1300.00),
        (d(2026, 8, 12), d(2026, 8, 12), "DIVIDENDOS DE CLIENTES WEGE3 S/            100", 25.00, 1201.00),
        (d(2026, 8, 10), d(2026, 8, 10), "TED BCO 001 AGE 1  CTA 000000  - RETIRADA EM C/C", -500.00, 1176.00),
        (d(2026, 8, 7), d(2026, 8, 7), "IRRF S/ ETF RF", -24.00, 1676.00),
        (d(2026, 8, 6), d(2026, 8, 7), "OPERAÇÕES EM BOLSA LIQ. D+1 PR 06/08/2026 NOTA Nº 000001", -300.00, 1700.00),
        (d(2026, 8, 3), d(2026, 8, 3), "JUROS S/ CAPITAL DE CLIENTES ITUB3 S/            100", 6.61, 2000.00),
    ]:
        ws.append(["", mov, liq, lanc, "", valor, saldo])
    ws.append([])
    ws.append(["", "CLEAR CTVM S/A", "", "", "Atendimento ao cliente: 0000-0000"])
    ws.append(["", "Rio de Janeiro | RJ"])
    wb.save(caminho)
    return caminho


def construir_b3(caminho):
    """Movimentação da Área do Investidor da B3 no formato documentado (NÃO conferido contra export real)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Movimentação"
    ws.append(["Entrada/Saída", "Data", "Movimentação", "Produto", "Instituição", "Quantidade",
               "Preço unitário", "Valor da Operação"])
    ws.append(["Credito", "20/08/2026", "Rendimento", "HGLG11 - CSHG LOGISTICA FDO INV IMOB", "CORRETORA X CTVM", 50, 1.10, 55.00])
    ws.append(["Credito", "05/08/2026", "Transferência - Liquidação", "PETR4 - PETROBRAS PN N2", "CORRETORA X CTVM", 40, 30.75, 1230.00])
    ws.append(["Debito", "10/07/2026", "Transferência - Liquidação", "VALE3 - VALE ON NM", "CORRETORA X CTVM", 10, 65.00, 650.00])
    ws.append(["Credito", "02/01/2026", "Bonificação em Ativos", "RENT4 - LOCALIZA RENT A CAR S/A", "CORRETORA X CTVM", 13, "", ""])
    ws.append(["Credito", "15/01/2026", "Atualização", "Tesouro Selic 2029", "CORRETORA X CTVM", 1, "", ""])
    wb.save(caminho)
    return caminho
