# Otimizar Arquivos

> Este projeto foi desenvolvido em colaboração com inteligência artificial (IA), inclusive na geração e revisão de código e documentação.

Conjunto de ferramentas Python para organizar arquivos e diretórios, com
interface gráfica Tkinter e comandos de terminal.

- Separar duplicatas em quarentena.
- Remover pastas vazias, dissolver subpastas e mesclar diretórios.
- Organizar arquivos por ano ou extensão.
- Consultar e desfazer operações registradas no histórico local.

## Executar

Requer Python 3.10 ou mais recente com Tkinter. Usa a biblioteca padrão do
Python e não precisa instalar pacotes adicionais.

Na pasta do projeto, abra a interface:

```powershell
python assistente_maestro.pyw
```

Ou consulte os comandos disponíveis:

```powershell
python maestro.py --help
python maestro.py pastas --help
python maestro.py pastas redundancias "C:\pasta-de-teste"
```

O último comando simula a operação. As alterações dependem de `--executar`.
Faça uma cópia dos arquivos antes de executar operações de movimentação ou
exclusão. O histórico em `.maestro_historico/` permanece somente no computador.

## Arquivos locais

O Git acompanha código, documentação e recursos gráficos do aplicativo. O
`.gitignore` usa uma lista de tipos e arquivos permitidos: ambientes virtuais,
caches, fotos de usuários, relatórios, históricos, bancos de dados e chaves
locais não são incluídos. Não use `git add -f` para esses arquivos.
