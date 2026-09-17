---
name: jabuti-estrategia
description: "Use quando o usuário pedir '/jabuti-estrategia', 'definir minha estratégia', 'montar as bandas', 'declarar minha política' ou abrir uma sessão num workspace cujo estado/SETUP.md tem a linha do jabuti-estrategia aberta. Etapa 2 de 5: abre perguntando se a pessoa JÁ TEM estratégia; captura a dela como política declarada ou apresenta as três alternativas da rubrica (metodo/bandas.yaml) para o perfil; grava a tabela de bandas e caps em politica/01-alocacao-alvo.md e o log de decisão em logs/decisoes/. Quanto por bloco, não em quê. Nunca 'recomendo': sempre 'sua política aponta'. Não escolhe ativo, não olha dados/, não altera o perfil."
---

# jabuti-estrategia — qual é a sua política

## Quando usar

- Depois do `/jabuti-init`, com `estado/SETUP.md` apontando para cá
- Para revisar as bandas depois (decisão estrutural fora de cadência: histórico mais log novo, nunca edição silenciosa)

Frases típicas: "/jabuti-estrategia", "vamos definir as bandas", "quero declarar minha política".

## Princípio operacional

- **Abre perguntando se a pessoa já tem estratégia.** Quem já investe costuma ter, de cabeça ou em planilha; o que falta é processo. A casa dá o processo, não substitui a estratégia dela.
- **Quanto, não em quê.** Esta etapa decide o tamanho de cada bloco (mín, alvo, máx) e os caps de concentração. Qual ativo entra em cada bloco é escolha sua, fora desta skill.
- **Executor de política declarada.** A skill apresenta alternativas com racional e a pessoa escolhe. O output nunca diz "recomendo"; diz "sua política aponta". A escolha é dela e é logada como dela.
- **A rubrica é dado, lida como está.** As três alternativas saem de `metodo/bandas.yaml` sem ajuste silencioso; a regra de reserva (`parametros.reserva`) é aplicada e dita. Se a pessoa quer números diferentes, ela ajusta, e o log registra.
- **A LLM escreve; o validador confere.** Tabela de bandas, caps, histórico e log são escritos pela skill; `check_politica` cobra vocabulário, mín ≤ alvo ≤ máx, alvos somando 100 e classe vetada em zero. Mostrar tudo antes de gravar.

## Contexto canônico a ler antes

- `politica/00-perfil.md`: frontmatter preenchido? Sem ele, parar e mandar ao `/jabuti-init`. Ler `horizonte-anos`, `risco-testado`, `reserva-meses`, `classes-vetadas`.
- `metodo/bandas.yaml` do motor (caminho em `vault.config.yaml`, `caminhos.motor`): a faixa cujo `horizonte-anos` contém o do perfil e cujo `risco-testado` é o do perfil; `parametros.reserva`.
- `politica/01-alocacao-alvo.md`: tabela vazia (criação) ou preenchida (revisão)?

## Fluxo

1. "Você já tem uma estratégia de alocação, de cabeça ou em planilha?"
2. **Já tem**: pedir como ela é (bloco por bloco, em % da carteira). Transcrever para a forma mín/alvo/máx; sem mín e máx declarados, usar alvo ± 10, dito. Seguir ao passo 4.
3. **Não tem**: selecionar a faixa pelo perfil. Aplicar a regra de reserva quando `reserva-meses` for menor que `parametros.reserva.minimo-meses` (o alvo de `caixa` sobe até `caixa-minimo-sem-reserva` e a diferença sai de `rf-br`, deslocando as três colunas), e dizer que foi aplicada. Apresentar as três alternativas numa tabela, bloco por bloco, com uma linha de racional por bloco. Quando o risco declarado divergir do testado, dizer que a faixa usou o testado, e por quê.
4. Em qualquer entrada, mostrar **as três alternativas da faixa ao lado** da política em discussão, como comparação: "a rubrica, para o seu perfil, sugeriria isto; a sua política diz aquilo". Nada mais que isso.
5. Classe vetada no perfil já chega em `[0, 0, 0]`, com o motivo dito. A pessoa escolhe uma alternativa, ou mantém a dela, ou ajusta o que quiser; caps por ativo e por setor com os defaults da alternativa mais próxima.
6. Conferir a aritmética em voz alta: alvos somam 100, cada bloco com mín ≤ alvo ≤ máx. Se não fecha, dizer onde e pedir o ajuste; a skill não redistribui por conta própria.
7. Montar e mostrar: a tabela `## Bandas por bloco` de `politica/01-alocacao-alvo.md`, a seção `## Caps de concentração`, uma linha no `## Histórico de revisões`, e o log `logs/decisoes/AAAA-MM-DD-estrategia.md` com frontmatter `tipo: log-decisao`, contexto, as três alternativas consideradas, a escolhida e o racional **da pessoa**, mais a divergência da casa quando houver. Gravar depois do "de acordo".
8. Rodar `python <motor>/scripts/validar_workspace.py .`. Erro de `politica:` é da skill: corrigir e rodar de novo.
9. Com zero erros: no `SETUP.md`, marcar `- [x]` na linha do `/jabuti-estrategia` e trocar `Próximo:` para `` `/jabuti-importar` ``. **Não acrescente linha nenhuma ao `SETUP.md`**: ele sequencia só skill instalada.
10. Rodar `python <motor>/scripts/gerar_harness.py .` (regenera o harness; quando as personas por classe existirem, é aqui que entram) e emitir o bloco de handoff.

## Casos especiais

- **Perfil com função objetivo provisória**: a estratégia segue normal; a tabela não depende do degrau. Dizer que o degrau fica para quando o custo for medido.
- **Revisão de bandas já declaradas**: perguntar o que mudou e por quê; tabela nova, linha no histórico, log novo. Nunca sobrescrever o log anterior.
- **Pessoa quer um bloco fora do vocabulário** ("ouro"): é `commodities`; explicar o vocabulário fechado e por quê (o validador e o ESTADO leem por ele).
- **Só ETF, sem picking**: legítimo, e é caminho previsto. As bandas continuam iguais; a diferença aparece na hora de escolher o que comprar, que é sua e fica fora desta skill.

## O que esta skill NÃO faz

- **Não escolhe ativo**: ela decide quanto por bloco, nunca em quê
- **Não olha `dados/`** nem calcula gap: o gap por bloco é do `estado/ESTADO.md`, gerado depois do `/jabuti-importar`
- **Não recomenda**: apresenta e registra a escolha da pessoa
- **Não altera o perfil** (→ `/jabuti-init` em modo revisão)
- **Não redistribui alvos por conta própria** para fechar 100
- **Não commita**

## Próximo passo

Só com o validador em zero erros. Formato fixo:

```
✔ jabuti-estrategia concluído — política declarada e validada.

Próximo: abra uma thread nova e cole
    /jabuti-importar

Tenha à mão: o export de posições da sua corretora, salvo em inbox/.
```
