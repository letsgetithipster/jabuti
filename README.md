# Mesa Própria

**O sistema operacional do seu patrimônio.** Um repo open source que você
clona e opera com a LLM que já usa para tocar a própria carteira com a
disciplina de um family office — sob guardrails que impedem a LLM de inventar
número, análise ou decisão. Hoje ele já faz a parte de **dados**: extrato de
corretora entra em CSVs canônicos com conciliação verificada, cotação entra
por script com fonte e hora, e sai um cockpit xlsx e um ESTADO de uma tela.
O funil de perfil e alocação, a rotina mensal, a preparação de IR e a
compilação para Codex/Cursor/app web chegam nas fases seguintes (abaixo).

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

**Fase 2 (motor de dados) — concluída:** ingestão de extrato agnóstica de
corretora (mapeamento YAML + conciliação declarada, com `clear-extrato`,
`schwab-transacoes`, `b3-movimentacao` e `exemplo-posicoes-csv` prontos);
cotações por provider plugável (Yahoo, brapi, BCB/SGS, manual) com detecção
de variação anômala; validador v2 (vocabulários, moeda por conta, ledger
cronológico com PM, bandas somando 100); gerador de `ESTADO.md`; cockpit
xlsx; skills `/atualizar-cotacoes` e `/importar-extrato`.

**Próximas fases:** método destilado + funil `/init` → `/definir-macro` →
`/refinar-micro` → `/aprofundar-tese` + compilador multi-LLM (3); skills de
rotina `/registrar-aporte`, `/consultar-aporte`, `/fechar-mes` (4); pacote
fiscal e `/preparar-ir` (5).

## Começando

Requisitos: Python 3.11+ e git. openpyxl é opcional (extrato .xlsx e cockpit).
(macOS/Linux: troque os caminhos, ex. `python3 scripts/criar_workspace.py ~/meu-vault`)

```powershell
git clone <url> personal-finance-br
cd personal-finance-br
python -m pip install -r requirements.txt          # pyyaml + pytest
python -m pip install -r requirements-xlsx.txt     # opcional: openpyxl
python -m pytest                                   # suíte verde
python scripts/criar_workspace.py C:\caminho\meu-vault
```

No workspace, o ciclo da Fase 2 (as duas skills fazem isso por você no Claude Code):

```powershell
# 1. exporte o extrato/posições da corretora para meu-vault\inbox\ e inspecione
python scripts\inspecionar_extrato.py C:\caminho\meu-vault\inbox\extrato.xlsx
# 2. importe (mapeamento pronto detectado pelo cabeçalho, ou --mapeamento <nome>)
python scripts\importar_extrato.py C:\caminho\meu-vault C:\caminho\meu-vault\inbox\extrato.xlsx --dry-run
python scripts\importar_extrato.py C:\caminho\meu-vault C:\caminho\meu-vault\inbox\extrato.xlsx
# 3. cotações (provider em vault.config.yaml; --manual TICKER=PRECO para o que não tem mercado)
python scripts\atualizar_cotacoes.py C:\caminho\meu-vault
# 4. ESTADO de uma tela e cockpit xlsx
python scripts\gerar_estado.py C:\caminho\meu-vault
python scripts\gerar_cockpit.py C:\caminho\meu-vault
# 5. validador (roda também no pre-commit do workspace)
python scripts\validar_workspace.py C:\caminho\meu-vault
```

Seu workspace é **privado por desenho** — não o publique. Extratos ficam em
`inbox/` fora do versionamento; o cockpit xlsx é regenerável e não versionado.

## Estrutura

| Pasta | O que mora | Fase |
|---|---|---|
| `templates/` | árvore de workspace + esqueletos de documentos | 1 |
| `scripts/` | validador, instanciador, cotações, ingestão, geradores — com testes | 1-2 |
| `mapeamentos/` | mapeamentos documento → `dados/` por corretora (YAML); superfície de contribuição | 2 |
| `skills/` | procedimentos operacionais: cotações e ingestão prontas; funil e rotina | 2 (3-4) |
| `exemplos/` | workspace fictício completo, validado em todo commit | 1 |
| `metodo/` | rubricas e frameworks do método (sem número pessoal) | 3 |
| `rules/` | núcleo de voz e personas, fontes do compilador multi-LLM | 3 |
| `fiscal/` | pacotes tributários por ano-fiscal, com validade declarada | 5 |

## Contribuindo

Método canônico (rubricas, frameworks, princípios) muda só via issue de
método com racional. Contribuição aberta e bem-vinda nas bordas: mapeamentos
de corretora (com fixture sintética — ver `mapeamentos/README.md`), providers
de cotação, pacotes fiscais anuais, testes.
Num clone novo, ative o hook: `git config core.hooksPath .githooks` — ele
mantém o exemplo sempre verde e a suíte passando em todo commit. Instale
também `requirements-xlsx.txt`: sem openpyxl os testes de xlsx aparecem como
`skipped` e você não exercita esse caminho.

## Licença e aviso

Apache-2.0. **Não é recomendação de investimento** — veja o aviso legal
completo em [GUARDRAILS.md](GUARDRAILS.md).

---

## English

**Mesa Própria** is an open-source, LLM-operated personal
portfolio system for Brazilian investors, built under strict anti-hallucination
guardrails: prices only via scripts with source and timestamp, broker
statements ingested through declarative YAML mappings with arithmetic
reconciliation against the document itself, user-declared policy as the only
decision maker. Today (phase 2) it ships the data engine: canonical CSVs,
validator, quote providers, statement ingestion, a generated one-screen state
file and an xlsx cockpit. Profile assessment, allocation funnel, monthly
routine and tax support are the next phases. Portuguese-first by design;
code contributions welcome.
