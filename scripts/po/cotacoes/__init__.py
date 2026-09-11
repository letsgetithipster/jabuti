"""Cotações: tipos canônicos, providers plugáveis e orquestração do append em cotacoes.csv.

Dois Protocols (decisão 1 do brainstorming da Fase 2):

- ProviderCotacoes (construído): cotar(pedidos) -> (cotações, falhas). Registry em
  po.cotacoes.providers. Cada provider recebe a função de rede injetável (`buscar`),
  então a suíte roda com fixtures JSON e nunca toca a rede.
- ProviderMovimentacoes (ponto de extensão, NÃO construído): um provider de dados de
  conta (ex.: open banking via MCP) devolveria registros no schema canônico de dados/
  — os mesmos dicts que a ingestão produz (po.ingestao.engine.Resultado) — e usaria a
  mesma escrita (po.ingestao.escrita). A conferência de soma do caminho de provider NÃO
  é a mesma conciliação de documento: é `conciliar_resposta` (po.ingestao.conciliacao),
  com garantia declaradamente menor — compara a resposta contra o total que o chamador
  afirma ter pedido, não contra a aritmética do próprio documento, porque uma resposta
  de API não declara o próprio total como um extrato declara. O que se compartilha é o
  tipo canônico do registro e a escrita, não uma classe-base nem o tipo de conciliação.
"""
