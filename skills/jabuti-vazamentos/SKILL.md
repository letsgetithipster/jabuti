---
name: jabuti-vazamentos
description: "Use quando o usuário pedir '/jabuti-vazamentos', 'onde o dinheiro vaza', 'onde estou gastando demais', 'quais assinaturas eu tenho' ou variação sobre cortar gasto recorrente para aportar mais. Bônus de quem conecta a Finnest: lê pelo MCP da Finnest as cobranças recorrentes (list_insight_subscriptions, ou detect_subscriptions), a carga de assinaturas (get_subscription_stack_load) e, como contexto, as categorias e os estabelecimentos do último mês fechado (get_category_spending, list_top_merchants), depois de conferir a atualidade do dado (get_data_freshness_status). A pessoa marca o que quer cortar e vê o total mensal liberado. Somente leitura: não cancela nada, não escreve em dados/, não grava no perfil. Sem a Finnest conectada nesta sessão: para e declara."
---

# jabuti-vazamentos — onde o dinheiro vaza, para liberar aporte

## Quando usar

- A cada três meses, ou quando aparece cobrança nova no extrato
- Quando a pessoa quer aportar mais e não sabe de onde tirar

Frases típicas: "/jabuti-vazamentos", "quais assinaturas eu pago?", "onde estou gastando demais?".

## Princípio operacional

- **Sem as tools da Finnest nesta sessão, parar e declarar.** Como conectar: `docs/finnest-skills.md`. Sem ela, a pessoa pode listar as cobranças de cabeça, e a skill só organiza, marcando no log que foram declaradas, não medidas.
- **Atualidade antes de número.** `get_data_freshness_status` é precondição: conta que parou de sincronizar some da lista sem erro.
- **A resposta não tem contrato.** O servidor não declara `outputSchema`; campo ausente é "não informado", nunca zero.
- **Mostrar, não julgar.** A skill não diz que um gasto é demais nem sugere corte: lista o que a Finnest detectou, e quem marca é a pessoa.
- **Corte é intenção.** A skill não cancela nada (o cancelamento é da pessoa, no fornecedor ou no banco), não escreve em `dados/` e não grava no perfil: o efeito aparece sozinho na próxima `/jabuti-sobra` e na próxima medição de três meses da `/jabuti-capacidade`.
- **Escolha com letra, item com número.** Opções uma por linha como `a)`, `b)`, `c)`; itens de lista, pelo número.

## Fluxo

1. Conferir que as tools da Finnest estão na sessão. Não estão: parar como no princípio acima.
2. `get_data_freshness_status`. Fora de `fresh`: dizer o que está velho, a ação segura que a resposta recomenda, e que cobrança de conta parada não aparece na lista. Quem sincroniza é a pessoa, no app da Finnest.
3. `list_insight_subscriptions` (sem argumento). Resposta vazia ou sem valor: `detect_subscriptions` (sem argumento; nunca com `refresh`, que exige `institution_id`).
4. `get_subscription_stack_load` (sem argumento): a carga total e a contagem de inativas.
5. Tabela numerada com o que veio, sem arredondar: nome, cadência, valor típico, status, última cobrança. As inativas primeiro. Abaixo, a carga total que a Finnest informou.
6. Perguntar: "Quais você quer cortar? Responda com os números." O que não for marcado fica.
7. Mostrar o total mensal liberado como soma dos marcados, termo a termo. Cobrança que não é mensal aparece com a conversão ao lado, com os termos: semanal, valor × 52 ÷ 12; anual, valor ÷ 12.
8. Contexto do último mês fechado: `get_category_spending` com `from_date` e `to_date` no primeiro e no último dia do mês anterior, e `list_top_merchants` com `from`, `to` (as mesmas datas) e `limit` = 5. Mostrar as cinco maiores categorias e os cinco maiores estabelecimentos, sem juízo de valor, e perguntar: "a) marcar algum para acompanhar; b) encerrar".
9. Mostrar e depois gravar `logs/decisoes/AAAA-MM-DD-vazamentos.md`: frontmatter `tipo: log-decisao`, `data`, `data-criacao`, `assunto: vazamentos`; no corpo, as tools chamadas, a atualidade do dado, a tabela lida, o que foi marcado para cortar, o total mensal com os termos e o que foi marcado para acompanhar.
10. Rodar `python <motor>/scripts/validar_workspace.py .` com zero erros. O caminho do motor está em `vault.config.yaml`, `caminhos.motor`. Fechar com: "o que você cortar aparece na próxima `/jabuti-sobra`".

## Casos especiais

- **Nada detectado**: dizer isso em uma linha e encerrar. Não inventar tarefa.
- **Cobrança que a pessoa não reconhece**: dizer "confira com o banco ou com o emissor do cartão" e marcar no log. Não afirmar que é fraude.
- **Cobrança paga em dinheiro ou em conta não conectada**: não aparece. A pessoa pode acrescentar, e o log marca a linha como declarada.
- **A pessoa não marca nada**: é resposta válida. Gravar o log só se ela pedir.

## O que esta skill NÃO faz

- **Não cancela nada**: cancelar é da pessoa; pagamento, PIX e automação estão fora do teto `read:financial`
- **Não escreve em `dados/`**: nenhum número da Finnest entra na carteira canônica
- **Não grava no perfil**: o efeito do corte é medido depois, pela `/jabuti-capacidade`
- **Não julga categoria de gasto** nem sugere o que cortar
- **Não commita** (o usuário decide quando)

Rodapé fixo de toda saída: "isto organiza a sua decisão sobre dinheiro que é seu; não é recomendação de investimento".
