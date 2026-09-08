# PatrimônioOS

**O sistema operacional do seu patrimônio.** Um repo open source que você
clona e opera com a LLM que já usa (Claude Code em primeira classe; Codex,
Cursor e app web via compilação) para montar e tocar a própria carteira com
a disciplina de um family office: assessment de perfil, alocação por bandas,
cesta por classe/país, rotina mensal e preparação de IR — sob guardrails
que impedem a LLM de inventar número, análise ou decisão.

> Leia **[GUARDRAILS.md](GUARDRAILS.md)** antes de usar. É o contrato que
> torna este produto confiável — e o motivo de ele existir.

## Por que isso existe

Assessoria tradicional custa 0,5-2% a.a. ou é remunerada por distribuição
(conflito de interesse estrutural). Family office dedicado é inacessível.
A LLM tem mais informação do que qualquer escritório — o que falta é
método, memória e guardrails. É isso que este repo entrega: *um family
office de uma pessoa só, com a disciplina que a LLM sozinha não tem.* O
custo é a assinatura de LLM que você já paga.

## Estado atual

**Fase 1 (fundação) — concluída:** camada de dados canônica (6 CSVs com
schema), config de workspace, validador com testes, instanciador de
workspace e workspace-exemplo.
**Próximas fases:** motor de dados e cotações (2), método + funil
init→macro→micro + compilador multi-LLM (3), skills de rotina (4), IR (5).

## Começando (nesta fase)

```powershell
git clone <url> patrimonio-os
cd patrimonio-os
python -m pip install -r requirements.txt
python -m pytest                                  # suíte verde
python scripts/criar_workspace.py C:\caminho\meu-vault
python scripts/validar_workspace.py C:\caminho\meu-vault
```

Seu workspace é **privado por desenho** — não o publique. Os fluxos de
`/init` em diante chegam na Fase 3.

## Estrutura

| Pasta | O que mora |
|---|---|
| `metodo/` | rubricas e frameworks do método (sem nenhum número pessoal) |
| `templates/` | árvore de workspace + esqueletos de documentos |
| `skills/` | procedimentos operacionais (funil e rotina) |
| `rules/` | núcleo de voz e personas, fontes do compilador multi-LLM |
| `scripts/` | validador, instanciador, geradores — com testes |
| `fiscal/` | pacotes tributários por ano-fiscal, com validade declarada |
| `exemplos/` | workspace fictício completo, validado em todo commit |

## Contribuindo

Método canônico (rubricas, frameworks, princípios) muda só via issue de
método com racional. Contribuição aberta e bem-vinda nas bordas: parsers
de corretora, providers de cotação, pacotes fiscais anuais, testes.

## Licença e aviso

Apache-2.0. **Não é recomendação de investimento** — veja o aviso legal
completo em [GUARDRAILS.md](GUARDRAILS.md).

---

## English

**PatrimônioOS** ("WealthOS") is an open-source, LLM-operated personal
portfolio management system for Brazilian investors: profile assessment,
band-based allocation, per-country asset baskets, monthly routines and tax
support — under strict anti-hallucination guardrails (prices only via
scripts, deterministic tax math, user-declared policy as the only decision
maker). Portuguese-first by design; code contributions welcome.
