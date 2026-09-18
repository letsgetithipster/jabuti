---
name: jabuti-sobra
description: "Use quando o usuário pedir '/jabuti-sobra', 'quanto sobra este mês', 'quanto posso aportar agora', 'quanto dá para investir sem apertar a conta' ou variação sobre a sobra do mês corrente. Bônus de quem conecta a Finnest: lê pelo MCP da Finnest o saldo de hoje (get_account_balance_summary), o saldo projetado dia a dia até o fim do mês (get_daily_forecast), as contas que ainda vêm (get_upcoming_bills) e a fatura em aberto (get_card_bill_snapshot), depois de conferir a atualidade do dado (get_data_freshness_status), e mostra duas medidas da sobra para a pessoa escolher o valor que leva para a /jabuti-mes. Somente leitura: não escreve em dados/, não grava no perfil, não decide o aporte. Sem a Finnest conectada nesta sessão: para e declara."
---

# jabuti-sobra — quanto dá para aportar este mês sem apertar a conta

## Quando usar

- Antes da `/jabuti-mes`, uma vez por mês, para chegar lá com o valor do aporte medido
- Quando a pessoa quer saber quanto pode investir agora sem ficar no vermelho antes do fim do mês

Frases típicas: "/jabuti-sobra", "quanto sobra este mês?", "quanto posso aportar agora?".

## Princípio operacional

- **Sem as tools da Finnest nesta sessão, parar e declarar, sem beco.** Dizer que o valor do aporte é o que a pessoa informar na `/jabuti-mes`, e que a referência é o `capacidade-aporte-mensal` do perfil. Como conectar: `docs/finnest-skills.md`. A Finnest é atalho, nunca requisito.
- **Atualidade antes de número.** `get_data_freshness_status` é precondição. Dado velho é dito antes de qualquer número, e sobre dado velho a skill não fecha sobra.
- **A resposta não tem contrato.** O servidor não declara `outputSchema`; campo ausente é "não informado", nunca zero.
- **Números da Finnest, lado a lado; a pessoa escolhe.** A skill não projeta, não tira média e não inventa margem de segurança: a projeção é a da Finnest. A única conta é a subtração da reserva, mostrada com os termos.
- **Leitura, nunca escrita na carteira.** A skill não escreve em `dados/` e não grava no perfil: o perfil guarda a média de três meses da `/jabuti-capacidade`, e a sobra do mês é outra grandeza. Só grava o log da decisão.
- **Escolha com letra.** Opções uma por linha como `a)`, `b)`, `c)`, e a pessoa responde com a letra.

## Contexto canônico a ler antes

- `politica/00-perfil.md`: `capacidade-aporte-mensal`, `reserva-meses` e `custo-vida-mensal`, só como referência. São declaração da pessoa, não número de mercado.

## Fluxo

1. Conferir que as tools da Finnest estão na sessão. Não estão: parar como no princípio acima.
2. `get_data_freshness_status`. Fora de `fresh`: dizer o que está velho e a ação segura que a resposta recomenda, e não fechar sobra. Quem sincroniza é a pessoa, no app da Finnest.
3. Contar N, os dias de hoje até o último dia do mês corrente, no máximo 30 (o limite de `get_daily_forecast`).
4. `get_account_balance_summary` (sem argumento): o saldo de hoje.
5. `get_daily_forecast` com `days` = N: o saldo projetado de cada dia e os dias de risco.
6. `get_upcoming_bills` com `days` = N, e `get_card_bill_snapshot` (sem argumento): o que ainda vence no mês, com data e valor.
7. Uma pergunta sobre a reserva, com letra: "Sua reserva de emergência fica em alguma destas contas? a) sim; b) não". Com a), perguntar quanto dela fica ali, mostrando o `reserva-meses` e o `custo-vida-mensal` do perfil como referência. Com b), a reserva em conta é zero.
8. Montar a tela com o que veio, sem arredondar: o saldo de hoje; o pior dia projetado (data e saldo) e o último dia do mês (saldo); as contas e a fatura que ainda vêm, com data. Dizer: "confira se a fatura de R$ X que vence em D já aparece na projeção; o servidor não documenta se ela entra". Não afirmar e não somar por conta própria.
9. Oferecer, com letra e com os termos da conta à vista:
   - a) pior dia projetado − reserva em conta = R$ …
   - b) saldo projetado no fim do mês − reserva em conta = R$ …
   - c) outro valor que a pessoa informar
   Ao lado, o `capacidade-aporte-mensal` do perfil, só como comparação.
10. Pior dia menor ou igual à reserva em conta: dizer "não há sobra este mês" e não oferecer a) nem b). Com fatura ou empréstimo em aberto, oferecer a `/jabuti-divida`.
11. Com a escolha, mostrar e depois gravar `logs/decisoes/AAAA-MM-DD-sobra.md`: frontmatter `tipo: log-decisao`, `data`, `data-criacao`, `assunto: sobra`; no corpo, as tools chamadas, a atualidade do dado, os números lidos, a reserva em conta informada, as opções e a escolha.
12. Rodar `python <motor>/scripts/validar_workspace.py .` com zero erros. O caminho do motor está em `vault.config.yaml`, `caminhos.motor`. Fechar com: "leve R$ X para a `/jabuti-mes`".

## Casos especiais

- **Renda que cai em conta não conectada**: a projeção não a enxerga. Dizer isso, deixar a pessoa informar o valor e marcar no log a parte declarada.
- **Último dia do mês**: N = 1, e a sobra é o saldo de hoje menos o que ainda vence hoje.
- **A pessoa não quer registrar**: não gravar nada. A tela já vale.

## O que esta skill NÃO faz

- **Não escreve em `dados/`**: nenhum número da Finnest entra na carteira canônica
- **Não grava no perfil**: o `capacidade-aporte-mensal` é da `/jabuti-capacidade`
- **Não decide o aporte** nem escolhe bloco ou ativo (→ `/jabuti-mes`)
- **Não move dinheiro** nem sincroniza conexão: o motor pede só `read:financial`
- **Não projeta nem inventa margem**: a projeção é a da Finnest
- **Não commita** (o usuário decide quando)

Rodapé fixo de toda saída: "isto organiza a sua decisão sobre dinheiro que é seu; não é recomendação de investimento".
