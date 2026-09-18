---
name: jabuti-capacidade
description: "Use quando o usuário pedir '/jabuti-capacidade', 'qual é o meu custo de vida', 'medir minha capacidade de aporte' ou variação sobre quanto sobra por mês nas contas. Bônus de quem conecta a Finnest: decidir o aporte do mês é da /jabuti-mes, que não depende dela. Lê três meses fechados de fluxo de caixa pelo MCP da Finnest (get_cashflow_period_summary), depois de conferir a atualidade do dado (get_data_freshness_status) e a dívida em aberto (get_loan_summary), e grava custo-vida-mensal e capacidade-aporte-mensal medidos em politica/00-perfil.md, com log de decisão. Somente leitura na Finnest: não escreve em dados/, não decide o aporte, não escolhe ativo. Sem a Finnest conectada nesta sessão: para e declara."
---

# jabuti-capacidade — o número que o perfil exigia, medido

## Quando usar

- Com a Finnest conectada, para trocar um `custo-vida-mensal` declarado à mão por um medido
- Uma vez por semestre, ou quando renda ou despesa mudarem de patamar
- Quando o `/jabuti-init` gravou `custo-vida-mensal: null` e a função objetivo ficou provisória

Frases típicas: "/jabuti-capacidade", "quanto sobra por mês nas minhas contas?", "quanto eu gasto por mês de verdade?".

Decidir o aporte do mês é da `/jabuti-mes`, que funciona sem a Finnest. Esta skill só mede o que o perfil guarda.

## Princípio operacional

- **Sem as tools da Finnest nesta sessão, parar e declarar.** O caminho declarado continua valendo: o `/jabuti-init` grava o que a pessoa mede à mão. A Finnest é atalho, nunca requisito.
- **Atualidade antes de número.** `get_data_freshness_status` é precondição. Dado velho vira alerta de primeira classe, não nota de rodapé.
- **A resposta não tem contrato.** O servidor não declara `outputSchema`; campo ausente é "não informado", nunca zero.
- **Três números medidos, uma escolha da pessoa.** A skill não tira média, não projeta e não arredonda: ela mostra os três meses e oferece o menor, o do meio e o maior. Média esconde o mês ruim, que é justamente o que sustenta a capacidade.
- **A LLM escreve o perfil; o validador confere.** `check_perfil` recalcula o degrau contra `metodo/bandas.yaml` e erra com o número certo se divergir.
- **Leitura na Finnest; escrita só no perfil e no log**, depois do "de acordo". A skill não escreve em `dados/`.

## Contexto canônico a ler antes

- `politica/00-perfil.md`: frontmatter preenchido? Então é revisão, não criação.
- `metodo/bandas.yaml` do motor (caminho em `vault.config.yaml`, `caminhos.motor`): `parametros.taxa-retirada-real`, usada no degrau.

## Fluxo

1. Conferir que as tools da Finnest estão na sessão (o prefixo é o nome do servidor MCP). Não estão: parar, dizer como conectar (`docs/finnest-skills.md`) e oferecer o caminho declarado.
2. `get_data_freshness_status`. Fora de `fresh`: dizer o que está velho e a ação segura que a resposta recomenda, e não fechar número sobre dado velho. Quem sincroniza é a pessoa, no app da Finnest.
3. `get_loan_summary`. Com dívida em aberto, dizer isto **antes** de qualquer número de aporte e oferecer `/jabuti-divida`: a ordem do método é dívida cara antes de aporte.
4. Escolher os **três meses fechados** anteriores ao mês corrente e chamar `get_cashflow_period_summary` uma vez por mês, com `from` e `to` no formato `AAAA-MM-DD` (primeiro e último dia do mês).
5. Montar a tabela, verbatim: mês, receitas, despesas, líquido. Campo que não veio: "não informado".
6. Oferecer as três alternativas de capacidade **por seleção**: conservadora = o menor líquido; equilibrada = o do meio; agressiva = o maior. Dizer qual mês sustenta cada uma. Para renda variável ou autônomo, a conservadora é a sugerida, com o racional.
7. `custo-vida-mensal` = a despesa do mês escolhido, pela mesma regra e no mesmo passo, para que custo e capacidade venham da mesma janela.
8. Mostrar o diff do perfil antes de gravar: `custo-vida-mensal`, `capacidade-aporte-mensal`, `funcao-objetivo-provisoria` para `false`, `degrau-if` recalculado (`custo-vida-mensal × 12 ÷ taxa-retirada-real`, inteiro), `data-revisao` de hoje, a seção `## Capacidade` reescrita e uma linha no `## Histórico de revisões` dizendo de onde veio o número.
9. Gravar depois do "de acordo", e gravar junto `logs/decisoes/AAAA-MM-DD-capacidade.md` com frontmatter `tipo: log-decisao`, `data`, `data-criacao`, `assunto: capacidade`, e no corpo: tools chamadas, a janela dos três meses, a atualidade do dado, a tabela lida, as três alternativas e a escolha com o racional da pessoa.
10. Rodar `python <motor>/scripts/validar_workspace.py .`. Erro de `perfil:` é da skill: o validador recalcula o degrau e imprime o número certo — corrigir e rodar de novo. Com zero erros, fechar: com o número medido, cole `/jabuti-mes` para decidir onde ele entra.

## Casos especiais

- **Conta conectada há menos de três meses**: usar as janelas que existem, dizer quantas são e registrar a limitação no log. Menos de um mês fechado: não fechar número; declarar e voltar no mês que vem.
- **Mês atípico** (13º, bônus, mudança, viagem): a pessoa marca, a skill usa outro mês e o log registra a exclusão e o motivo.
- **Gasto fora do Open Finance** (dinheiro vivo, conta não conectada): a despesa medida fica subestimada. Dizer isso e deixar a pessoa somar o que falta, marcando no log a parte declarada.
- **Revisão** (perfil já preenchido): trocar só o que mudou, com linha nova no histórico, e recalcular o degrau se o custo mudou.
- **A pessoa não quer gravar**: não gravar nada. A tabela na tela já vale; perfil pela metade confunde a próxima thread.

## O que esta skill NÃO faz

- **Não escreve em `dados/`** — nenhum número da Finnest entra na carteira canônica
- **Não decide onde aportar** nem escolhe ativo: ela responde *quanto*, não *em quê* (→ `/jabuti-mes`)
- **Não move dinheiro** nem sincroniza conexão: o motor pede só `read:financial`
- **Não tira média, não projeta e não estima**: seleciona entre meses medidos
- **Não altera bandas nem política** (são do `/jabuti-estrategia`)
- **Não commita** (o usuário decide quando)

Rodapé fixo de toda saída: "isto executa a política que você declarou; não é recomendação de investimento".
