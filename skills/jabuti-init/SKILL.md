---
name: jabuti-init
description: "Use quando o usuário pedir '/jabuti-init', 'começar', 'instalar o jabuti', 'começar o onboarding', 'montar meu perfil', 'primeira vez no jabuti' ou abrir uma sessão numa pasta cujo estado/SETUP.md tem a linha do jabuti-init aberta. Na pasta clonada ainda sem vault.config.yaml, o passo 0 instala o jabuti ali mesmo (ambiente, dependências, uma pergunta, criar_workspace.py .) e segue na mesma conversa. Etapa 1 de 5: uma conversa de 15 a 17 perguntas, uma por vez, que produz politica/00-perfil.md — quem a pessoa é, para onde vai, quanto aguenta. Só fatos e uma conta aritmética; zero conversa sobre alocação. Não pergunta onde instalar, não propõe banda (/jabuti-estrategia), não olha dados/."
---

# jabuti-init — quem você é

## Quando usar

- Na pasta recém-clonada do jabuti, ainda sem `vault.config.yaml`: o passo 0 instala ali mesmo, e a conversa segue para o perfil
- Primeira thread de um workspace recém-criado (`estado/SETUP.md` com `/jabuti-init` aberto)
- Para revisar o perfil depois de uma mudança de vida (renda, dependente, meta), com o histórico de revisões registrando o que mudou

Frases típicas: "/jabuti-init", "vamos começar", "monta meu perfil".

## Princípio operacional

- **Uma pergunta por vez**, com racional curto. Quando houver opções, uma por linha como `a)`, `b)`, `c)`, e a pessoa responde com a letra. A pessoa responde, a skill segue; nunca um questionário inteiro de uma vez.
- **Fatos, não alocação.** Esta etapa produz quem a pessoa é. Qualquer conversa sobre "quanto em ações" é da etapa seguinte, e a skill diz isso se a pessoa puxar o assunto.
- **Número medido, não chutado.** Custo de vida e capacidade de aporte são o que a pessoa mede. Se ela não sabe o custo de vida, o perfil grava `custo-vida-mensal: null` e `funcao-objetivo-provisoria: true`; a skill não aceita estimativa como se fosse medição.
- **A LLM escreve o perfil; o validador confere.** Os campos do frontmatter são a fonte de verdade; a prosa das seções é para o humano. Os dois derivados (degrau e risco testado) são conferidos por `check_perfil` contra `metodo/bandas.yaml`: a skill os calcula, o validador recalcula, e divergência é erro.
- **Mostrar antes de gravar.** O `00-perfil.md` inteiro aparece na tela e só é gravado depois do "de acordo".

## Contexto canônico a ler antes

- A raiz tem `vault.config.yaml`? Sem ele, e com `scripts/criar_workspace.py` na raiz, é a pasta clonada ainda sem instalação: começar pelo passo 0.
- `estado/SETUP.md`: a linha do `/jabuti-init` está aberta? Se está fechada e o perfil tem frontmatter preenchido, é revisão, não criação.
- `politica/00-perfil.md`: existe (o `criar_workspace.py` cria)? Sem ele e com `vault.config.yaml`, a instalação está pela metade: rodar `python <motor>/scripts/validar_workspace.py .` e seguir a frase.
- `metodo/bandas.yaml` do motor (caminho em `vault.config.yaml`, `caminhos.motor`; `.` quando a instalação está na pasta clonada): `parametros.taxa-retirada-real` para a função objetivo e `parametros.risco-testado` para classificar os cenários.

## Passo 0 — instalar aqui, se ainda não está

Condição: a pasta atual tem `scripts/criar_workspace.py` e não tem `vault.config.yaml`. É o jabuti recém-clonado, e a pasta clonada vira a da pessoa. Não perguntar onde instalar.

1. Conferir o ambiente: `python --version` (no macOS e no Linux, `python3 --version`). Ausente ou abaixo de 3.11: parar e mandar instalar por https://www.python.org/downloads/. Depois `git --version`; ausente: https://git-scm.com/downloads.
2. Instalar as dependências: `python -m pip install -r requirements.txt -r requirements-xlsx.txt`. Recusa por "externally-managed-environment" (Python do sistema no Linux ou no macOS): `python3 -m venv .venv`, instalar com `.venv/bin/python -m pip install -r requirements.txt -r requirements-xlsx.txt` e usar `.venv/bin/python` no lugar de `python` daqui em diante (a `.venv` fica fora do git).
3. Identificar em que agente esta conversa roda e escolher o id: `claude-code`, `codex` ou `cursor`. Em dúvida, perguntar.
4. Uma pergunta: como a pessoa quer ser chamada nas conversas. Sem preferência, não passar `--usuario`.
5. Rodar `python scripts/criar_workspace.py . --harness <id> --usuario "<nome>"`. Ele copia as pastas pessoais para esta raiz, fora do git do jabuti, e liga os hooks que bloqueiam commit e push aqui. Frase de erro: ler, corrigir a causa e rodar de novo, nunca contornar.
6. Com código 0, dizer em duas linhas o que mudou: o jabuti está instalado nesta pasta, os dados dela ficam fora do git, e o jabuti se atualiza com `git pull`. Seguir direto para o passo 1 do Fluxo, nesta mesma conversa, sem mandar abrir outra pasta nem outra sessão.

## Fluxo

1. Idade e número de dependentes.
2. Horizonte para o grosso da carteira, **em anos**. As faixas 5-10 / 10-20 / 20-30 / 30+ guiam a pergunta, não o campo. Meta de prazo curto não encurta o horizonte: vira meta segregada no passo 3.
3. Metas, uma por vez até "chega": tipo (`independencia`, `imovel`, `renda-passiva`, `outra`), valor e ano-prazo.
4. Custo de vida mensal **medido**. Não sabe? `null`, função objetivo provisória, e a skill diz que o degrau fica em aberto até medir.
5. Capacidade de aporte mensal, medida, não aspirada.
6. Reserva de emergência hoje, **em meses** de custo de vida cobertos (nenhuma / menos de 3 / 3 a 6 / mais de 6 guiam a pergunta).
7. Risco declarado: `conservador`, `moderado` ou `arrojado`, como a pessoa se vê.
8. Risco testado, três cenários com as mesmas quatro opções (`vende-tudo` / `para-de-aportar` / `mantem` / `aporta-mais`): "a carteira caiu 30% no ano 2, o que você faz?"; "um bloco inteiro ficou 18 meses no vermelho, e o resto subiu"; "uma notícia diz que a classe que mais pesa na sua carteira acabou". Classificar pela tabela `parametros.risco-testado` (duas ou mais `vende-tudo` = baixo; duas ou mais `aporta-mais` sem nenhuma `vende-tudo` = alto; o resto = médio) e gravar as três respostas em `risco-testado-base`. Declarado e testado divergindo é informação registrada, não conflito a resolver.
9. Restrições: liquidez mínima em meses, classes vetadas (do vocabulário `acoes-br, fiis, rv-int, reits-us, rf-br, cripto, caixa, commodities`), limites pessoais em prosa.
10. Calcular o degrau: `custo-vida-mensal × 12 ÷ taxa-retirada-real`, inteiro. Com custo `null`, `degrau-if: null`.
11. Montar o `00-perfil.md`: frontmatter com todos os campos (`idade`, `dependentes`, `horizonte-anos`, `custo-vida-mensal`, `funcao-objetivo-provisoria`, `capacidade-aporte-mensal`, `reserva-meses`, `risco-declarado`, `risco-testado`, `risco-testado-base`, `metas`, `classes-vetadas`, `liquidez-minima-meses`, `degrau-if`) e as seções em prosa preenchidas com as respostas. `data-revisao` = hoje. Mostrar inteiro; gravar depois do "de acordo".
12. Rodar `python <motor>/scripts/validar_workspace.py .`. Erro de `perfil:` é da skill: corrigir e rodar de novo. Com zero erros, marcar `- [x]` na linha do `/jabuti-init` do `SETUP.md`, trocar `Próximo:` para `` `/jabuti-estrategia` `` e emitir o bloco de handoff.

## Casos especiais

- **Revisão** (frontmatter já preenchido): perguntar o que mudou, alterar só isso, acrescentar linha no histórico de revisões com data e motivo, recalcular o degrau se custo mudou.
- **Pessoa desiste no meio**: gravar nada. Perfil parcial no disco é aviso do validador e confunde a próxima thread. Dizer: "guardei nada; quando voltar, começamos do ponto zero ou você me diz as respostas de uma vez".
- **Meta sem valor** ("quero morar melhor"): pedir valor aproximado e ano; sem os dois, a meta não entra no frontmatter e fica só na prosa, com essa ressalva dita.
- **Dependente que é meta** (faculdade de filho): é meta do tipo `outra`, com valor e ano.

## O que esta skill NÃO faz

- **Não pergunta onde instalar** nem cria pasta separada: na pasta clonada, o passo 0 instala ali mesmo
- **Não propõe banda nem fala de alocação** (→ `/jabuti-estrategia`)
- **Não olha `dados/`** nem pergunta corretora (→ `/jabuti-importar`)
- **Não escolhe LLM**: grava no `harness` do config o agente em que a conversa já roda
- **Não edita arquivo do motor** (`scripts/`, `skills/`, `rules/`, `metodo/`): ele só muda por `git pull`
- **Não aplica taxa de memória**: a taxa vem de `metodo/bandas.yaml`, e o validador recalcula
- **Não commita** (na pasta clonada, commit e push ficam bloqueados; numa pasta separada, o usuário decide quando)

## Próximo passo

Só com o validador em zero erros. Formato fixo:

```
✔ jabuti-init concluído — perfil gravado e validado.

Próximo: abra uma thread nova e cole
    /jabuti-estrategia

Tenha à mão: se você já tem uma estratégia (de cabeça ou em planilha), as bandas que usa hoje.
```
