"""Ingestão de documentos de corretora em dados/ — agnóstica de corretora.

Divisão rígida (spec §6, GUARDRAILS camada 1): a LLM escreve o MAPEAMENTO (YAML,
po.ingestao.mapeamento) e o mostra ao usuário; o script executa o parse (engine),
confere a aritmética declarada no próprio documento (conciliacao) e só então grava
(escrita). Nenhum parser por corretora: corretora nova = mapeamento novo.
"""
