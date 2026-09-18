---
name: jabuti-init
description: "Use quando a pessoa pedir '/jabuti-init', 'começar', 'instalar o jabuti', 'primeira vez' ou qualquer pedido de uso (perfil, carteira, aporte) com o Claude Code aberto na pasta do MOTOR, a que tem scripts/criar_workspace.py. Aqui não é a pasta da pessoa: esta conversa confere o ambiente, instala as dependências, cria a pasta pessoal com scripts/criar_workspace.py e entrega os dois comandos que continuam nela, onde o /jabuti-init de lá pergunta quem a pessoa é. Duas perguntas, nenhuma sobre dinheiro."
---

# jabuti-init, na pasta do motor: a instalação

Esta pasta é o motor: o método, os scripts e as skills. Os dados da pessoa vivem numa pasta separada, que esta conversa cria. Lá dentro, o `/jabuti-init` de verdade pergunta quem ela é. As outras skills (`/jabuti-estrategia`, `/jabuti-importar`, `/jabuti-mes`) também só existem lá: qualquer pedido de uso feito aqui começa por esta instalação.

## Princípio operacional

- **Duas perguntas, uma por vez**: onde fica a pasta, e como a pessoa quer ser chamada. Nada sobre dinheiro, renda ou carteira: isso é da pasta nova, e aqui não se grava dado pessoal.
- **A pasta nunca fica dentro do motor.** O `criar_workspace.py` recusa; sugerir sempre a pasta vizinha.
- **Comando que falha diz o que fazer.** Ler a frase do script, corrigir e rodar de novo. Nunca contornar.
- Quem já tem a pasta criada não precisa desta conversa: basta abrir o Claude Code nela.

## Fluxo

1. Conferir o ambiente: `python --version` (no macOS e no Linux, `python3 --version`). Ausente ou abaixo de 3.11: parar e mandar instalar por https://www.python.org/downloads/. Depois `git --version`; ausente: https://git-scm.com/downloads.
2. Instalar as dependências, da raiz do motor: `python -m pip install -r requirements.txt -r requirements-xlsx.txt`. A segunda lista só serve para extrato em xlsx e para o cockpit em planilha; instalar as duas agora evita voltar aqui.
3. Perguntar onde criar a pasta, já com a sugestão: a pasta vizinha do motor chamada `meu-jabuti` (o caminho absoluto, montado a partir da pasta-mãe do motor). Aceitar outro caminho, desde que fora do motor. Caminho dentro de OneDrive, Dropbox ou iCloud: avisar que o conteúdo sincroniza para a nuvem (`PRIVACIDADE.md`) e deixar a pessoa decidir.
4. Perguntar como ela quer ser chamada nas conversas. Sem preferência: não passar `--usuario`.
5. Rodar `python scripts/criar_workspace.py "<pasta>" --usuario "<nome>"`.
6. Com o script em código 0, emitir o bloco de handoff.

## Handoff

Formato fixo, com o caminho real no lugar de `<pasta>`:

```
✔ Instalado. A sua pasta está em <pasta>.

Para continuar nesta mesma sessão, cole um de cada vez:
    /cd <pasta>
    /jabuti-init

Se o /cd não existir no seu Claude Code, saia com /exit e rode no terminal:
    cd "<pasta>"
    claude
Depois cole /jabuti-init.
```

## Casos especiais

- **`pip` recusa por "externally-managed-environment"** (Python do sistema no Linux ou no macOS): criar um ambiente no motor com `python3 -m venv .venv`, instalar com `.venv/bin/python -m pip install -r requirements.txt -r requirements-xlsx.txt` e rodar o passo 5 com `.venv/bin/python`. Dizer à pessoa que, nas skills da pasta nova, `python` é esse `.venv/bin/python`.
- **A pasta já existe e não está vazia**: o script recusa. Perguntar se ela já é uma pasta do jabuti (tem `estado/SETUP.md`); se for, pular direto para o handoff.
- **A pessoa quer começar pela carteira ou pelo aporte**: a ordem é a mesma. Primeiro a pasta, depois o perfil, a política e a carteira.

## O que esta skill NÃO faz

- **Não pergunta nada sobre dinheiro** nem monta perfil (→ `/jabuti-init` dentro da pasta nova)
- **Não grava nada no motor** além das dependências do Python
- **Não cria a pasta dentro do motor**
- **Não commita** e não faz push
