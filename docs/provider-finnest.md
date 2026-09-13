# Provider: Finnest (MCP de open finance)

Documento de integração que a Finnest não publica. Tudo aqui foi **medido em 12/09/2026** contra
o servidor real, com uma conta de verdade conectada. O que não foi medido está marcado como não
medido — a razão de esta task existir é que um adaptador escrito sem isto seria invenção.

O esquema completo das tools está em `tests/fixtures/openfinance/finnest-tools.json`, e a forma
das respostas em `tests/fixtures/openfinance/finnest-transacoes.json`. Este documento explica o
que as fixtures não dizem sozinhas: o que cada coisa significa, e onde estão as armadilhas.

## Endpoint e autenticação

| | |
|---|---|
| Endpoint | `https://mcp.finnest.com.br/mcp` |
| Transporte | MCP sobre HTTP |
| Autenticação | OAuth 2.1 com PKCE; bearer token no `Authorization` |
| Registro de cliente | dinâmico, RFC 7591 |
| Tools publicadas | 116, todas declaradas `Stability: stable` |

### Escopos

São **seis**, medidos no token deste workspace:

| Escopo | O que libera |
|---|---|
| `read:financial` | contas, saldos, transações, cartões, investimentos, empréstimos, orçamentos, tags, análises |
| `read:profile` | nome, e-mail, idioma, avatar, plano de assinatura |
| `manage:connections` | ler a saúde das conexões **e também** sincronizar, desconectar, remover e revogar consentimento |
| `manage:automations` | criar, editar, pausar e apagar automações de Smart Transfer |
| `manage:boletos` | ler e validar boleto |
| `execute:transfers` | mover dinheiro |

**A granularidade é ruim, e isso tem consequência para o motor.** Não existe `read:connections`.
Conferir se uma conta sincronizou — que é a precondição da ingestão, e é leitura pura — exige
`manage:connections`, o mesmo escopo que permite `remove_connection` e `revoke_data_consent`.
Ou seja: para saber que a conta está saudável, o token precisa poder desconectá-la.

Consequência prática: **peça só `read:financial`** para a rodada de ingestão. O motor não executa
transferência (spec §7), não gerencia automação e não precisa desconectar nada. Se a conferência
de status exigir `manage:connections`, ela é um segundo token, de uso deliberado — não um escopo
que viaja junto na rodada diária. Token que carrega escopo que o produto não usa é superfície de
ataque sem contrapartida.

## Vocabulário de status de conexão

A Task 6 tratava status como precondição e só conhecia `"OK"`. **`"OK"` não existe.** O valor real
é `"CONNECTED"`, medido em `get_connected_institutions`.

Isso não era um erro de leve: `STATUS_OK = "OK"` reprovava *toda* conexão saudável, abortava toda
rodada, e mandava o usuário reconectar uma conta que estava conectada. Corrigido em
`scripts/po/ingestao/provider.py`, com teste que prende as duas pontas.

Há **dois eixos independentes**, e confundi-los é fácil porque ambos se chamam `status`:

| Eixo | Onde | Valores conhecidos |
|---|---|---|
| Saúde da conexão | `status` em `get_connected_institutions` | `CONNECTED` (medido); `ERROR` e `DISCONNECTED` (declarados na descrição da tool e em `refresh_all_connections.include_error_status`) |
| Atualidade do dado | `freshness_status` em `get_data_freshness_status` | `fresh` (medido); os contadores `stale_count`, `degraded_count`, `disconnected_count` implicam `stale`, `degraded`, `disconnected` |

Só `CONNECTED` conta como sincronizado. **Desconhecido continua degradado** — a regra não mudou, e
não deve mudar: o vocabulário é do provider, os dois valores acima não foram vistos em produção
neste workspace (a conta estava saudável), e a lista pode crescer sem aviso.

Cuidado de forma: a resposta é `{"items": [...]}`, não uma lista nua, e cada linha usa `name` —
não `nome`. `conferir_status(resposta)` cai no ramo de "nenhuma conexão configurada", que é uma
frase errada para um problema que não é esse. Passe `resposta["items"]`.

## Correspondência com o Open Finance Brasil

Conferido contra a especificação Accounts v2.1.0. **A Finnest não devolve OFB**: ela devolve um
remodelamento próprio. Isso é exatamente o motivo do invariante de que nenhum campo de `dados/`
pode herdar nome ou semântica de fornecedor — herdar daqui seria herdar de duas camadas de
renomeação, não da norma.

| Campo Finnest | Campo OFB | Observação |
|---|---|---|
| `id` | `transactionId` | UUID; cabe no padrão OFB (`^[a-zA-Z0-9][a-zA-Z0-9-]{0,99}$`) |
| `description` | `transactionName` | o literal da instituição, o mais próximo do bruto |
| `type` (`debit`/`credit`) | `creditDebitType` (`DEBITO`/`CREDITO`) | mesma semântica, vocabulário renomeado |
| `payment_data.operationType` | `type` (`EnumTransactionTypes`) | `PIX`, `BOLETO` e `RESGATE_APLIC_FINANCEIRA` passam **verbatim** do enum OFB |
| `amount` | `transactionAmount.amount` + `.currency` | ver "sinal" e "precisão" abaixo |
| `date` | `transactionDateTime` | OFB exige sufixo `Z`; a Finnest manda `+00:00` |
| `display_name` | — | enriquecimento do fornecedor, sem contrapartida na norma |
| `category` | — | taxonomia do fornecedor (`Pagamentos`, `Investimentos`, `Saúde`, `Outros`, `Transporte`, `Assinaturas`) |
| `merchant_domain` | — | enriquecimento; presente só em parte das linhas de cartão |
| `is_internal_transfer` | — | derivado pelo fornecedor; cobre transferência entre contas do mesmo titular, inclusive entre instituições |
| `status` (`POSTED`/`PENDING`) | — | não é o vocabulário de liquidação da norma |

`payment_data.operationType` passa valores do enum OFB verbatim, **mas não só eles**: foram vistos
`PAGAMENTO` e `OTHER`, que não estão no enum da norma (cujo coringa é `OUTROS`). Tratar
`operationType` como se fosse o enum OFB quebra na primeira linha de cartão.

## Armadilhas medidas

### 1. O sinal de `amount` diverge entre escopos — não leia direção pelo sinal

Medido no mesmo dia, na mesma chamada só mudando `account_type`:

| Escopo | Despesa vem como | `type` |
|---|---|---|
| `BANK` | `-240` (negativo) | `"debit"` |
| `CARD` | `70` (positivo) | `"debit"` |

Um adaptador que inferir direção do sinal de `amount` **inverte toda despesa de cartão**, e o erro
é silencioso: o número existe, a linha entra, o patrimônio sobe quando devia descer.

O OFB não tem esse problema porque lá o valor é sempre positivo e a direção mora em
`creditDebitType`. O sinal é invenção da Finnest, e ela não a aplica de forma consistente.

**Regra para o adaptador: a direção é `type`. O sinal de `amount` é ruído.**

### 2. Só 90 dias por chamada, e a mensagem de erro mente

Medido por bisseção, com `page_size=1` para descartar o tamanho como causa:

| `from` → `to` | Dias | Resultado |
|---|---|---|
| 2026-06-14 → 2026-09-12 | 90 | OK |
| 2026-06-13 → 2026-09-12 | 91 | `VALIDATION_ERROR` |

Acima de 90 dias a chamada é recusada **antes** de buscar, com a mensagem genérica
`"Parâmetros de busca inválidos"` e o `recovery_hint` *"Use get_account_overview to find valid
account IDs"* — que aponta para o lugar errado: o account_id estava certo, e nem era obrigatório.

Dentro dos 90 dias ainda há um teto de tamanho: `RESPONSE_TOO_LARGE`, `95000` bytes, e esse erro
**diz a verdade** e traz `retryable: true`.

O motor promete erro como frase acionável. Nenhuma das duas mensagens é utilizável como veio: o
adaptador tem que traduzir `VALIDATION_ERROR` numa janela de datas para "peça no máximo 90 dias
por chamada", porque o texto do provider manda o usuário conferir o que não está errado.

### 3. Histórico longo existe — ao contrário do que o plano supunha

O plano listava "histórico acima de doze meses" como algo que a API não devolve. **Devolve.** Uma
janela de 90 dias em setembro de 2025 retornou transações normalmente.

O limite real não é de retenção, é de **janela por chamada**: histórico longo se obtém fatiando em
trechos de até 90 dias. Isso muda o desenho do adaptador — de "não dá" para "dá, paginando" — e é
o tipo de suposição que só cai medindo.

Detalhe associado: numa janela histórica o `sourceAsOf` volta antigo (a sincronização daquele
trecho), não "agora". `sourceAsOf` velho em consulta histórica é normal, não é sinal de conexão
degradada.

### 4. Envelope, caixa e nomes de parâmetro variam entre tools irmãs

- **Chave do envelope**: `items` em transações e contas, `investments` em `get_investments`,
  `sources` em `get_data_freshness_status`.
- **Caixa**: `get_data_freshness_status` devolve `snake_case` (`last_synced_at`) e
  `get_data_coverage_summary` devolve `camelCase` (`lastSyncedAt`) — para o **mesmo dado**.
- **Cache**: uma parte das tools aceita `max_age_seconds` + `refresh`; outra aceita `force_refresh`.
- **Datas**: `from`/`to` na maioria; `from_date`/`to_date` em `get_category_spending`,
  `get_cashflow_insights`, `get_pix_graph` e `list_enriched_merchants`; `month`+`year` inteiros em
  outras; `period`/`month` em `YYYY-MM` em outras ainda.

Nada disso é opinável pelo adaptador: é normalização que ele tem que fazer, tool a tool, com a
fixture do esquema na mão.

### 5. Precisão: o valor vem como número JSON

O OFB especifica `amount` como **string** decimal com 2 a 4 casas, mais `currency` explícito. A
Finnest devolve número JSON (`-3005.02`, `79.9`, `70`) e **nenhum campo de moeda por linha** — a
moeda só aparece no nível da conta.

Para um motor de patrimônio, ler dinheiro como float binário é problema conhecido. Converter para
`Decimal` a partir do texto bruto, antes de qualquer soma.

### 6. `get_investments` esconde posições, e promete taxa que não entrega

A resposta medida trouxe `excluded_withdrawn_count: 100` ao lado de 3 posições. Cem posições
foram excluídas por serem resgatadas, **em silêncio**, sem que nada além desse contador diga.
Lacuna nunca é zero: quem somar `investments` sem ler esse campo está somando um subconjunto e
chamando de total.

Além disso, a descrição da tool promete "valores atuais (BRL), **taxas de retorno** e tipos de
ativo". As linhas devolvidas têm só `id`, `name`, `type`, `balance` e `institution_name`. **Não há
campo de taxa de retorno.** A descrição promete mais do que o payload entrega.

## O que a API não devolve

Medido, salvo onde indicado:

- **Preço médio, quantidade e custo de aquisição de posição.** As linhas de investimento têm
  apenas saldo. Sem preço médio não há apuração de ganho de capital.
- **Taxa de retorno**, apesar da descrição da tool prometê-la.
- **As posições já resgatadas**, que saem só como um contador.
- **Moeda por transação** — só no nível da conta.
- **Saldo após a transação.**
- **O payload OFB cru e os ids internos do provedor**, mantidos do lado do servidor por desenho
  (`detect_subscriptions` diz isso explicitamente).
- **Mais de 90 dias por chamada** (ver armadilha 2).

**Não medido, e por isso não afirmado:** como é a linha de uma posição de **renda variável**. As
três posições deste workspace são `FIXED_INCOME`, então nenhuma linha de ação ou fundo foi
observada. A ausência de preço médio está afirmada acima para o que foi visto; se o payload de
renda variável tem campos a mais, isso continua em aberto e precisa de uma conta com esse tipo de
posição para ser respondido.

## As 116 tools, por família

Nomes só; descrição e esquema de entrada completos estão em `finnest-tools.json`.

- **Contas e transações (10)** — `get_account_overview`, `get_account_balance_summary`,
  `list_transactions`, `list_recent_transactions`, `list_transactions_by_category`,
  `list_transactions_by_tag`, `get_transaction_details`, `get_top_transactions`,
  `list_upcoming_charges`, `get_upcoming_bills`
- **Conexão e consentimento (14)** — `get_connected_institutions`, `get_data_freshness_status`,
  `get_data_coverage_summary`, `list_open_finance_institutions`, `connect_bank_account`,
  `sync_connection`, `sync_connection_accounts`, `sync_connection_credit_cards`,
  `sync_connection_investments`, `sync_connection_transactions`, `refresh_connection`,
  `refresh_all_connections`, `disconnect_connection`, `remove_connection`
- **Consentimento de dados (4)** — `create_data_consent`, `list_data_consents`,
  `get_data_consent_status`, `revoke_data_consent`
- **Cartão de crédito (12)** — família `get_card*`, `list_card*`, `get_limit_summary`
- **Investimento e dívida (4)** — `get_investments`, `get_investment_summary`, `get_loans`,
  `get_loan_summary`
- **Análise de gastos (16)** — famílias `get_spending*`, `get_category*`, `*merchant*`,
  `get_counterparty_spending`, `get_temporal_profile`
- **Fluxo de caixa e projeção (11)** — famílias `get_cashflow*`, `get_daily_forecast`,
  `get_smart_projection`, `get_financial_snapshot`, `get_financial_checkup`, `get_wealth_signals`
- **Orçamento, tags, assinaturas, insights, perfil e PIX agregado (16)**
- **Pagamentos e boleto (5)** — `list_payments`, `get_payment_activity`, `get_payment_history`,
  `parse_boleto`, `validate_boleto`
- **Transferência e automação (24)** — **fora do alcance do motor**, por decisão de produto:
  `execute_pix_transfer`, as seis de `*scheduled_transfer`/`get_transfer_status`, as duas de
  pré-autorização de pagamento e as dezesseis de `*automation*`. Movem dinheiro ou mudam
  configuração de movimentação.

A soma das famílias fecha em 116, conferida contra a fixture e não contada de cabeça.

## Para o adaptador

Checklist derivado do que está acima, para o plano do adaptador não reabrir cada ponto:

1. Pedir só `read:financial`. Status de conexão exige `manage:connections` — decidir se vale um
   segundo token de uso deliberado ou se a precondição passa a se apoiar em `sourceAsOf`/`stale`.
2. Direção pelo campo `type`, nunca pelo sinal de `amount`.
3. `Decimal` a partir do texto, nunca aritmética em float.
4. Fatiar janelas em no máximo 90 dias, e traduzir `VALIDATION_ERROR` numa frase que diga isso.
5. Ler `excluded_withdrawn_count` e recusar chamar de total o que exclui posição em silêncio.
6. Normalizar envelope (`items`/`investments`/`sources`) e caixa por tool, não globalmente.
7. `description` é o literal da instituição; `display_name` é enriquecimento do fornecedor. Para
   `dados/`, o literal — enriquecimento é semântica herdada de fornecedor, que é o que o
   invariante proíbe.
8. `conferir_status` recebe `resposta["items"]`, não a resposta.
