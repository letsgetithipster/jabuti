"""Cotações: tipos canônicos, providers plugáveis e orquestração do append em cotacoes.csv.

Dois Protocols (decisão 1 do brainstorming da Fase 2):

- ProviderCotacoes (construído): cotar(pedidos) -> (cotações, falhas). Registry em
  po.cotacoes.providers. Cada provider recebe a função de rede injetável (`buscar`),
  então a suíte roda com fixtures JSON e nunca toca a rede.
- ProviderMovimentacoes (ponto de extensão, NÃO construído): um provider de dados de
  conta (ex.: open banking via MCP) devolveria registros no schema canônico de dados/
  — os mesmos dicts que a ingestão produz (po.ingestao.engine.Resultado) — e passaria
  pela mesma conciliação e escrita (po.ingestao.escrita). O que se compartilha é o tipo
  canônico do registro e a verificação de soma, não uma classe-base.
"""
