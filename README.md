# jabuti

Suas finanças em texto simples, operadas pela LLM que você já usa, sob guardrails
que não deixam número inventado entrar. **Ele zela, não decide:** a decisão continua sua.

O jabuti não corre. Vive oitenta anos e chega.

De brasileiros, para brasileiros.

Sobre os dados de exemplo que vêm no repo, sem configurar nada:

<!-- demo:start -->
```
$ python scripts/gerar_estado.py exemplos/workspace-exemplo --data 2026-09-08
estado/ESTADO.md regenerado — Total investido: R$ 12.000,00
Pendências:
- fiis acima da banda máxima (66,7% vs 40%): rebalancear via aporte nos blocos abaixo
- rf-br abaixo do mínimo (0,0% vs 25%): priorizar nos próximos aportes
```
<!-- demo:end -->

Isso saiu de CSV canônico: toda cotação carrega fonte, data e hora, e o validador
recalcula os totais em todo commit.

> Leia **[GUARDRAILS.md](GUARDRAILS.md)** antes de usar. É o contrato que torna este
> produto confiável — e o motivo de ele existir.

## Por que isso existe

Assessoria tradicional custa 0,5-2% a.a. ou é remunerada por distribuição
(conflito de interesse estrutural). Family office dedicado é inacessível.
A LLM tem mais informação do que qualquer escritório — o que falta é
método, memória e guardrails. É isso que este repo entrega: *um family
office de uma pessoa só, com a disciplina que a LLM sozinha não tem.* O
custo é a assinatura de LLM que você já paga.

**Declaração de vínculo:** o autor deste repositório é co-founder da Finnest, cujo MCP é a
primeira integração de open finance prevista (Fase 3). O motor não pertence a nenhum
fornecedor: o contrato de ingestão é escrito contra a especificação pública do Open Finance
Brasil, e qualquer provider entra como adaptador.

## Estado atual

**Fase 1 (fundação) — concluída:** camada de dados canônica (`posicoes`,
`cotacoes`, `fills`, `proventos`, `eventos`, `indices`, com schema), config de
workspace, validador com testes, instanciador de workspace e workspace-exemplo.

**Fase 2 (motor de dados) — concluída:** ingestão de extrato agnóstica de
corretora (mapeamento YAML + conciliação declarada, com `clear-extrato`,
`schwab-transacoes`, `b3-movimentacao` e `exemplo-posicoes-csv` prontos);
cotações por provider plugável (Yahoo, brapi, BCB/SGS, manual) com detecção
de variação anômala; validador v2 (vocabulários, moeda por conta, ledger
cronológico com PM, bandas somando 100); gerador de `ESTADO.md`; cockpit
xlsx; skills `/jabuti-cotacoes` e `/jabuti-importar`.

**Fase 3 (gastos e open finance por provider) — parcial:** o que está em
código, commitado e testado é a fundação de ingestão por provider MCP, não
nenhum provider ligado nela. Entregue: tabela canônica `movimentacoes.csv`
(sétima tabela, com sinal no valor e `data_referencia` própria do provider);
quarto tipo de conciliação, `soma-da-resposta`, declaradamente mais fraco que
os três de documento; camada de procedência de dado de API (payload cru
arquivado, status de sincronização como precondição de leitura); `check_segredos`
no validador e, por consequência, no pre-commit. **Não entregue:** nenhum
adaptador de provider — nada chama essa camada ainda. O adaptador da Finnest
(ver "Declaração de vínculo" acima) depende de descobrir o esquema do MCP dela,
o que é escopo de outra fase.

**Fase 4 (onboarding) — parcial:** o que está em código, commitado e testado é o
onboarding em três threads guiadas por `estado/SETUP.md`, cada uma terminando com o
próximo passo pronto para colar: `/jabuti-init` (perfil legível por máquina, com degrau
e risco testado recalculados pelo validador contra `metodo/bandas.yaml`),
`/jabuti-estrategia` (política declarada a partir da estratégia que a pessoa já tem,
ou das três alternativas da rubrica, com log de decisão dela) e o preâmbulo de
onboarding da importação (corretoras, propósito por conta, carteira lida dentro da
política no `ESTADO.md`). E o harness Claude Code — `CLAUDE.md` e `.claude/rules/` —
compilado de `rules/00-voz.md` e do config por `gerar_harness.py`, com `check_harness`
bloqueando commit se o gerado divergir da fonte. **Não entregue:** `/jabuti-micro` e
`/jabuti-tese`, que dependem da destilação do método, e os alvos Codex, Cursor e app
web do compilador.

**Próximas fases:** cesta semente por bloco e tese validada com nota, `/jabuti-micro` e
`/jabuti-tese`, mais personas por classe e os outros alvos do compilador multi-LLM (4b);
`/preparar-ir` e `fiscal/` (6). A rotina mensal da Fase 5 é uma skill só, `/jabuti-mes`,
que decide o aporte e registra o que aconteceu; o mês sem aporte é a mesma decisão
rodada com valor zero, e por isso não há skill nem script de fechamento.

## Começando

Requisitos: Python 3.11+ e git. openpyxl é opcional (extrato .xlsx e cockpit).
(macOS/Linux: troque os caminhos, ex. `python3 scripts/criar_workspace.py ~/meu-vault`)

```powershell
git clone git@github.com:letsgetithipster/jabuti.git
cd jabuti
python -m pip install -r requirements.txt          # pyyaml + pytest
python -m pip install -r requirements-xlsx.txt     # opcional: openpyxl
python -m pytest                                   # suíte verde
python scripts/criar_workspace.py C:\caminho\meu-vault
```

Criado o workspace, abra o Claude Code na pasta e cole `/jabuti-init`: o onboarding leva você
pelo perfil, pela política e pela importação, uma thread por etapa. O ciclo de dados abaixo é o
que as skills rodam por você:

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
| `skills/` | procedimentos operacionais: onboarding, cotações e ingestão prontos; micro, tese e rotina | 2-4 (5) |
| `exemplos/` | workspace fictício completo, validado em todo commit | 1 |
| `metodo/` | rubricas e frameworks do método (sem número pessoal) | 4 |
| `rules/` | núcleo de voz e personas, fontes do compilador multi-LLM | 4 |
| `tests/` | suíte do motor, rodada pelo pre-commit em todo commit | 1-2 |
| `docs/` | documentação de integração por provider (endpoint, tools, campos, status) | 3 |
| `fiscal/` | pacotes tributários por ano-fiscal, com validade declarada | 6 |

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

**jabuti** is an open-source, LLM-operated personal
portfolio system for Brazilian investors, built under strict anti-hallucination
guardrails: prices only via scripts with source and timestamp, broker
statements ingested through declarative YAML mappings with arithmetic
reconciliation against the document itself, user-declared policy as the only
decision maker. Today (phase 4, partial) it ships the data engine — canonical CSVs, validator, quote
providers, statement ingestion, a generated one-screen state file, an xlsx cockpit — and
a guided onboarding: profile, declared allocation policy and portfolio import, one thread
each, plus a compiled Claude Code harness. Asset selection, monthly routine and tax
support are the next phases. Portuguese-first by design;
code contributions welcome.
