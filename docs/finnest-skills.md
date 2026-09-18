# As skills Finnest — o que dá para fazer, e o que elas nunca fazem

> O jabuti conhece a **sua carteira**. A Finnest conhece **o seu mês**: renda, despesa, cartão e
> dívida. Quem a conecta ganha duas skills de bônus, que medem o que, sem ela, você calcula à
> mão no app do banco: o custo de vida, quanto sobra por mês e quanto custa a dívida em aberto.
>
> Duas skills, opcionais, somente leitura. Nenhuma escreve na sua carteira, e a rotina mensal
> (`/jabuti-mes`) funciona inteira sem elas.

## Em trinta segundos

| Skill | A pergunta que responde | O que lê na Finnest | O que escreve no seu workspace |
|---|---|---|---|
| `/jabuti-capacidade` | quanto eu gasto e quanto sobra por mês, medido em vez de estimado | `get_data_freshness_status`, `get_loan_summary`, `get_cashflow_period_summary` (três meses fechados) | `politica/00-perfil.md` (custo de vida, capacidade, degrau) e um log de decisão |
| `/jabuti-divida` | tenho fatura ou empréstimo em aberto: aporto ou quito primeiro? | `get_data_freshness_status`, `get_loan_summary`, `get_cards`, `get_card_interest` | um log de decisão em `logs/decisoes/` |

`custo-vida-mensal` e `capacidade-aporte-mensal` são campos que o `/jabuti-init` exige **medidos,
não chutados** — e, sem a Finnest, o jabuti não tem como medi-los: você abre o app do banco e faz a
conta. É essa conta que a `/jabuti-capacidade` faz por você. E há uma ordem que o método
brasileiro exige e o motor
sozinho não consegue cumprir: **dívida cara antes de aportar**. Quem tem rotativo de cartão e compra
ação está perdendo dinheiro, e só a Finnest sabe que o rotativo existe. Onde o aporte do
mês entra continua sendo decidido pelo `/jabuti-mes`, com ou sem esses números.

## Conectar leva dois minutos

No Claude Code (em outro cliente MCP, o equivalente dele):

```powershell
claude mcp add --transport http finnest https://mcp.finnest.com.br/mcp
```

A autorização é OAuth 2.1 com PKCE e registro de cliente dinâmico. As tools aparecem na sessão com o
prefixo do nome que você deu ao servidor (`mcp__finnest__get_loan_summary`, se você o chamou de
`finnest`). Sem elas na sessão, cada skill **para e declara** — nunca responde de memória.

## O teto de escopo, e por que ele é duro

O token da Finnest declara seis escopos. **O motor pede um.**

| Escopo | Situação | Por quê |
|---|---|---|
| `read:financial` | **usado** | é tudo que as duas skills precisam |
| `read:profile` | não usado | o motor não precisa saber o seu nome |
| `manage:connections` | fora | o mesmo escopo que permite `remove_connection` e `revoke_data_consent` |
| `manage:automations` | fora | muda configuração de movimentação de dinheiro |
| `manage:boletos` | fora | idem |
| `execute:transfers` | fora | move dinheiro |

Um motor que "zela, não decide" não pode ter no cinto a capacidade de executar transferência. **O
pior que uma alucinação pode fazer aqui é ler** — e é isso que torna a integração segura de
divulgar. Não é postura: `tests/test_skills_finnest.py` deriva do esquema medido a lista de tools
fora do teto e quebra o build se uma delas aparecer numa skill.

Consequência prática, medida em `provider-finnest.md`: conferir a saúde de uma conexão exigiria
`manage:connections`. Por isso as skills usam `get_data_freshness_status`, que cabe em
`read:financial`, e **nunca sincronizam nada**: quem sincroniza é você, no app da Finnest.

## Os limites que toda skill declara

1. **Sem `outputSchema`.** O servidor não publica contrato de resposta; o que sabemos da forma dela é
   observação de uma medição (`provider-finnest.md`). Campo ausente vira "não informado", nunca zero
   e nunca estimativa.
2. **Consentimento de Open Finance expira**, e conta que parou de sincronizar devolve lista vazia sem
   erro. Por isso a atualidade é conferida **antes** de qualquer número, e lacuna nunca é zero.
3. **A Finnest é atalho, nunca requisito.** Rode o mês inteiro sem ela e nada muda: o caminho CSV
   continua sendo o default, e quem não quiser conectar banco nenhum usa o produto do começo ao fim.
4. **Nada de dado pessoal no repo.** O que está versionado aqui é esquema e fixture anonimizada.

## Privacidade

O que a skill lê passa pela sua sessão de LLM, como qualquer coisa que você cola nela. Nada disso é
gravado em `dados/`: o único número que fica no workspace é o que **você mandou** gravar no perfil,
com o log de decisão ao lado dizendo de onde ele veio e em que data. A carteira canônica só recebe
operação conciliada contra documento — nenhum caminho liga a Finnest a ela, nem por bug.

## O que ainda não existe, e é convite

Das 116 tools, só **2 leem investimento** (`get_investments` e `get_investment_summary`), e nenhuma
das duas traz quantidade nem preço médio: por isso a Finnest não alimenta a carteira. As outras 114
são o mês da pessoa: conta, cartão, dívida, fluxo de caixa, gasto, orçamento, assinatura, e a gestão
da própria conexão. As duas skills acima usam cinco. O que mais caberia no método, e **não está
implementado**:

- **Onde o dinheiro vaza**, para aumentar a capacidade de aporte: `detect_subscriptions` e
  `get_category_spending`.
- **O veredito do mês** ao lado do fechamento da carteira: `get_monthly_review`.
- **Fôlego de liquidez e contas próximas**, para testar a reserva de emergência declarada no perfil:
  `get_financial_checkup` e `get_upcoming_bills`.

São bordas, que é onde a contribuição é bem-vinda. O núcleo do método não entra por PR.

## Para quem vai escrever adaptador

A medição completa do servidor — endpoint, escopos, vocabulário de status, as seis armadilhas
(inclusive o sinal de `amount` que diverge entre conta e cartão) e o que a API **não** devolve — está
em [provider-finnest.md](provider-finnest.md). Nada disso é repetido aqui de propósito.

**Declaração de vínculo:** o autor deste repositório é co-founder da Finnest. Ver o README.
