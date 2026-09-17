---
name: jabuti-divida
description: "Use quando o usuário pedir '/jabuti-divida', 'tenho dívida, posso investir?', 'quanto devo no cartão', 'vale a pena aportar com fatura rotativa' ou variação sobre dívida antes de aporte. Lê a dívida em aberto pelo MCP da Finnest (get_loan_summary, get_cards, get_card_interest), depois de conferir a atualidade do dado (get_data_freshness_status), põe o custo declarado da dívida ao lado do aporte do mês e abre três alternativas para a pessoa decidir. Somente leitura: não escreve em dados/, não move dinheiro, não decide. Sem a Finnest conectada nesta sessão: para e declara."
---

# jabuti-divida — a dívida cara vem antes do aporte

## Quando usar

- Antes de decidir o aporte do mês, quando existe fatura de cartão ou empréstimo em aberto
- Quando a pessoa pergunta se investe ou quita primeiro

Frases típicas: "/jabuti-divida", "devo quitar o cartão antes de aportar?", "quanto eu devo hoje".

## Princípio operacional

- **Sem as tools da Finnest nesta sessão, parar e declarar.** Mesmo princípio da cotação sem rede: número de memória contamina a decisão. Como conectar está em `docs/provider-finnest.md`.
- **Atualidade antes de número.** `get_data_freshness_status` é precondição: consentimento de Open Finance expira e conta que parou de sincronizar devolve lista vazia sem erro.
- **A resposta não tem contrato.** O servidor não declara `outputSchema`; a forma é observação de uma medição. Campo ausente é "não informado" — nunca zero, nunca estimativa.
- **A unidade é a do provedor.** Taxa ao mês fica ao mês. O método do jabuti não tem parâmetro de custo de dívida, e a skill não inventa limiar: ela põe os dois números na tela e quem decide a ordem é a pessoa.
- **Leitura, nunca escrita.** A skill não escreve em `dados/`: nada da Finnest entra na carteira canônica.

## Contexto canônico a ler antes

- `politica/00-perfil.md`: `capacidade-aporte-mensal` e `reserva-meses` — declaração da pessoa, não número de mercado.
- `estado/ESTADO.md`: a foto da carteira, se a conversa for comparar com o aporte do mês.

## Fluxo

1. Conferir que as tools da Finnest estão na sessão (o prefixo é o nome do servidor MCP, ex. `mcp__finnest__get_loan_summary`). Não estão: parar, dizer como conectar e oferecer o caminho sem Finnest — a pessoa dita os números e a skill só organiza a decisão, marcando no log que foram declarados, não medidos.
2. `get_data_freshness_status`. Fora de `fresh`, dizer o que está velho e a ação segura que a própria resposta recomenda, e **não afirmar número sobre dado velho**. Quem sincroniza é a pessoa, no app da Finnest: sincronizar exige escopo fora do teto do motor.
3. `get_loan_summary` (sem argumento): saldo em aberto e próximos pagamentos.
4. `get_cards` (sem argumento): faturas, vencimentos e pagamento mínimo. Para cada cartão, `get_card_interest` com o `card_id` daquele cartão (é o único argumento obrigatório de toda a rodada).
5. Sem dívida e sem fatura em aberto: dizer isso em uma linha e encerrar. Não inventar tarefa.
6. Montar a tabela: dívida, saldo em aberto, custo declarado **na unidade em que veio**, próximo vencimento. Ao lado, o `capacidade-aporte-mensal` do perfil.
7. Abrir três alternativas com racional, e uma frase sobre o que cada uma faz com o aporte do mês: conservadora (quitar antes de aportar), equilibrada (dividir entre quitação e aporte), agressiva (manter o aporte e pagar o mínimo). A decisão é da pessoa.
8. Gravar `logs/decisoes/AAAA-MM-DD-divida.md` com frontmatter `tipo: log-decisao`, `data`, `data-criacao`, `assunto: divida`, e no corpo: quais tools foram chamadas, a atualidade do dado, os números lidos, as três alternativas e a escolha com o racional **da pessoa**. Mostrar antes de gravar.
9. Rodar `python <motor>/scripts/validar_workspace.py .` — zero erros. O caminho do motor está em `vault.config.yaml`, `caminhos.motor`. O que sobrar para aportar entra pelo `/jabuti-mes`, que decide o bloco.

## Casos especiais

- **`get_cards` devolve erro de "sem cartões"**: é resposta válida, não falha. Seguir com empréstimo.
- **Taxa não veio no payload**: dizer "não informado" e pedir a taxa na fatura. Não estimar a partir do tipo de produto.
- **Dívida com terceiro, fora do Open Finance** (família, consignado antigo): não aparece na Finnest. Perguntar, e registrar no log como declarada.
- **Dívida barata** (consignado, financiamento subsidiado): a decisão muda de figura, e o rodapé continua o mesmo: a skill não classifica o que é caro.

## O que esta skill NÃO faz

- **Não escreve em `dados/`** — nenhum número da Finnest entra na carteira canônica, que só recebe operação conciliada contra documento
- **Não move dinheiro**: pagar, transferir, agendar e automatizar estão fora do teto de escopo do motor, que pede só `read:financial`
- **Não sincroniza, desconecta nem revoga conexão** (exige `manage:connections`, fora do teto)
- **Não decide**: apresenta alternativas com racional; a escolha e o log são da pessoa
- **Não estima taxa nem classifica dívida como cara ou barata** — o método não tem esse parâmetro
- **Não altera o perfil** nem a política
- **Não commita** (o usuário decide quando)

Rodapé fixo de toda saída: "isto organiza a sua decisão sobre dinheiro que é seu; não é recomendação de investimento".
