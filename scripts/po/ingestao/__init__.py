"""Ingestão em dados/ — agnóstica de corretora e de provider.

Duas procedências, duas garantias diferentes, porque a prova disponível é diferente:

- **Documento** (`mapeamento`, `engine`, `conciliacao`, `escrita`): a LLM escreve o MAPEAMENTO
  (YAML, po.ingestao.mapeamento) e o mostra ao usuário; o script executa o parse (engine),
  confere a aritmética declarada no próprio documento (conciliacao) e só então grava (escrita).
  Nenhum parser por corretora: corretora nova = mapeamento novo. Documento baixado é imutável e
  reexecutável — ele prova a própria aritmética.
- **Provider de open finance** (`provider`): resposta de API não é imutável nem reexecutável, então
  a garantia é outra — o payload cru vira artefato (a única prova do número) e o status de
  sincronização é precondição da rodada, não linha de relatório. `provider.py` não concilia nada
  nesta fase; quando conciliar, é `conciliacao.conciliar_resposta` (o quarto tipo, ao lado dos três
  de documento) quem faz.

Nenhum campo de `dados/` pode ter nome ou semântica herdada de corretora ou de provider.
"""
