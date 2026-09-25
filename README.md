# Importador de Cameras -> Zabbix

Importacao em lote de hosts de camera de CFTV para o Zabbix, a partir de uma
planilha (`.xlsx` ou `.csv`). Serve tanto para quem prefere linha de comando
quanto para quem quer uma interface grafica - os dois fluxos usam exatamente a
mesma logica de login, normalizacao e criacao de hosts.

A criacao de hosts usa o **frontend web** do Zabbix (login + POST do formulario
`host.create`), e nao a API por token. Assim funciona tambem em ambientes onde a
API HTTP esta bloqueada ou o token nao e disponivel.

## Destaques do projeto

- **Core unico:** `zabbix_web_batch_import.py` concentra a regra de negocio e e
  reaproveitado pela CLI, pelos scripts de lote e pela interface grafica.
- **Interface desktop (PySide6):** login, busca de grupos/templates/proxies no
  servidor, preview da planilha com validacao linha a linha e importacao com
  barra de progresso.
- **Validacao antes de importar:** nomes sao normalizados para ASCII (o Zabbix
  rejeita acentos e alguns caracteres) e duplicados apos a normalizacao bloqueiam
  a importacao, para voce corrigir na planilha.
- **Relatorios:** cada execucao gera log + relatorio `.json` e `.csv`, e o
  `consolidate.py` junta o resumo de varias execucoes.
- **Sem credenciais em disco:** usuario e senha sao pedidos em tempo de execucao.
- **Empacotavel:** `.exe` unico (PyInstaller) e instalador por usuario (Inno Setup).
- **Testes automatizados** das funcoes puras, usando apenas a stdlib (`unittest`).

## Arquivos

| Arquivo | Funcao |
| --- | --- |
| `zabbix_web_batch_import.py` | Importador principal (login web + `host.create`). |
| `run_batches.py` | Executa o importador em lotes de 25; layout configuravel por opcoes. |
| `consolidate.py` | Consolida os relatorios JSON de varias execucoes em um resumo. |
| `xlsx_to_csv.py` | Converte a planilha de origem em CSV normalizado. |
| `validate_camera_names.py` | Normaliza a coluna `Name` (ASCII) e valida duplicados. |
| `exemplo_cameras.csv` | CSV de exemplo com dados ficticios (demo e testes rapido). |
| `requirements.txt` | Dependencias Python do projeto. |
| `reports/` | Logs e relatorios (JSON/CSV) gerados a cada execucao. |
| `app/` | Interface grafica (PySide6) para quem nao usa linha de comando. |
| `app/paths.py` | Resolve caminhos no codigo-fonte e no .exe (assets e relatorios). |
| `app/session.py` | Sessao unica com o Zabbix, executada em thread dedicada. |
| `app/spreadsheet.py` | Leitura e validacao de planilhas (xlsx/csv) no app. |
| `app/toast.py` | Notificacoes (toasts) nao invasivas. |
| `run_app.py` | Ponto de entrada do executavel e do atalho de desenvolvimento. |
| `ImportadorCameras.spec` | Configuracao do build do PyInstaller. |
| `instalador.iss` | Configuracao do instalador (Inno Setup). |
| `version_info.txt` | Metadados do `.exe` (nome, versao). |
| `app/assets/` | Icone do app e fonte Inter (`assets/fonts/`). |
| `Iniciar App.bat` | Atalho para abrir o app grafico (sem console). |

## Requisitos

- Python 3.10 ou superior.
- Acesso de rede ao servidor Zabbix.

```powershell
pip install -r requirements.txt
```

## App grafico

Interface desktop para subir cameras sem usar linha de comando: voce baixa um
modelo de planilha, preenche, carrega no app e a importacao usa exatamente a
mesma logica do `zabbix_web_batch_import.py`.

Para abrir:

```powershell
python -m app.main
```

ou duplo clique em `Iniciar App.bat`.

Fluxo no app:

1. Entre com usuario e senha na tela de login. A URL do Zabbix e a porta da
   interface ficam em "Configuracoes" (canto do card de login; tambem ha
   "Encerrar sessao" la quando conectado).
2. Ao conectar, o app **busca no servidor os grupos, templates e proxies
   disponiveis** e preenche os seletores. Grupos e templates aceitam multipla
   selecao e **comecam sem nenhuma marcacao** (marque manualmente; sem grupo a
   importacao fica bloqueada). O botao "Atualizar listas" reconsulta a qualquer
   momento.
3. Baixe o modelo de exemplo: um popup permite **escolher as colunas opcionais**
   (Fabricante, Modelo, Firmware, Endereco MAC, Unidade, Etiqueta, Descricao). As
   colunas fixas do modelo sao apenas **Nome do host** e **IP**. Preencha uma
   linha por camera e carregue a planilha.
4. A tela mostra o preview do que sera criado (nomes ja normalizados) e
   **bloqueia a importacao enquanto houver linhas com erro** (IP vazio, nome
   invalido, duplicados).
5. Prefixo/sufixo sao opcionais. Importar usa a **mesma sessao** ja conectada: o
   progresso aparece por camera e, ao final, um relatorio e salvo em `reports/`
   no mesmo formato do CLI (o `consolidate.py` continua funcionando).

Observacoes:

- A criacao de hosts usa o login web; a **listagem** de grupos/templates/proxies
  usa o JSON-RPC da propria sessao (`api_jsonrpc.php` com cookie), sem token.
- A sessao fica aberta entre importacoes; se expirar no meio de uma execucao
  longa, o app reloga automaticamente uma vez e continua.
- "Sair" encerra a sessao e limpa as listas.
- Linhas ignoradas (sem nome ou marcadas como "troca realizada") nao sao
  importadas.
- A normalizacao de nomes e a mesma do CLI: acentos e caracteres invalidos sao
  removidos; nomes que colidem apos a normalizacao sao tratados como erro para
  voce ajustar na planilha.

## Linha de comando

O importador cria hosts para um intervalo do CSV. E **obrigatorio** informar ao
menos um grupo de destino:

```powershell
python .\zabbix_web_batch_import.py --url "https://seu-zabbix" --group-id 1 --offset 0 --limit 5
```

Hosts ja existentes sao detectados e contabilizados como "exists" no relatorio,
sem interromper o lote.

Execucao em lotes (fluxo padrao), pedindo usuario e senha no terminal:

```powershell
python .\run_batches.py --group-id 1
```

Para um layout diferente, passe as opcoes de layout do importador:

```powershell
python .\run_batches.py --group-id 1 --host-prefix "CAM - " --visible-name-prefix "CAM "
```

Roda o importador web em lotes de 25 registros, avisando (sem parar) se algum
lote terminar com erro. Cada execucao gera em `reports/` um log e relatorios
`zabbix-web-import-YYYYMMDD-HHMMSS.{log,json,csv}`.

Para revisar o resumo de varias execucoes:

```powershell
python .\consolidate.py
```

## Layout aplicado no Zabbix

Valores usados na criacao do host:

- `host` tecnico: `<Name do CSV>` (prefixo/sufixo opcionais)
- nome visivel: `<Name do CSV>` (prefixo/sufixo opcionais)
- interface: `agent`, IP da camera, porta configuravel (default `10051`)
- inventario: `name` = fabricante, `hardware` = modelo,
  `hardware_full` = modelo + firmware, `macaddress_a` = MAC
- status: monitorado, sem inventario automatico

**Grupo de host, template e proxy nao tem default no codigo**: sao escolhidos na
tela do app ou informados por `--group-id` / `--template-id` / `--proxy-id`.
Prefixo/sufixo de host e nome visivel tambem sao configuraveis por
`--host-prefix`, `--visible-name-prefix`, `--host-suffix` e
`--visible-name-suffix`.

## Campos lidos da planilha

`Nome do host`, `IP`, `Fabricante`, `Modelo`, `Firmware`, `Endereço MAC`,
`Unidade`, `Etiqueta`, `Descrição`.

- **Grupo de host, template e proxy NAO vem da planilha**: sao escolhidos na tela
  do app (secao "Opcoes de criacao") ou por argumento no CLI, e aplicados a todas
  as linhas.
- `Etiqueta` usa o formato `chave:valor` (varias separadas por `;`), ex.:
  `site:MATRIZ`.
- `Descrição` vai para o campo Description do host no Zabbix.
- `Unidade` e apenas orientacao para quem preenche (nao vai para o Zabbix).

Cabecalhos antigos tambem sao aceitos como alternativa (ex.: `Name`, `IP/Nome`,
`Fabricante:`, `MAC`), porque a planilha de cameras existe em mais de um formato
de exportacao.

## Preparacao dos dados

1. Atualize a planilha de cameras (`.xlsx`).
2. Gere o CSV normalizado:

```powershell
python .\xlsx_to_csv.py --input caminho\da\planilha.xlsx --output cameras_normalized.csv
```

3. Valide nomes e ausencia de duplicados (com `--in-place`, normaliza o proprio
   CSV):

```powershell
python .\validate_camera_names.py .\cameras_normalized.csv
```

Os dados de entrada (`*.xlsx` e `cameras_normalized.csv`) **nao sao
versionados**: contem informacoes do ambiente do cliente. O
`exemplo_cameras.csv` existe apenas com dados ficticios, para testar o fluxo:

```powershell
python .\zabbix_web_batch_import.py --url "https://seu-zabbix" --group-id 1 --csv .\exemplo_cameras.csv
```

## Credenciais

Nenhuma credencial fica salva em disco. Os dois fluxos pedem os dados na hora:

- **App grafico**: tela de login (a senha nao e gravada em lugar nenhum).
- **Linha de comando** (`run_batches.py`): pede usuario e senha no terminal ao
  iniciar; a senha e digitada sem eco (`getpass`). Nada de arquivo `.env`.

O importador `zabbix_web_batch_import.py` tambem aceita `--username`/`--password`
para quem quiser automatizar (nesse caso a senha fica visivel na linha de
comando).

## Testes automatizados

Testes das funcoes puras (normalizacao de nome, leitura da resposta do Zabbix,
montagem do formulario, colunas da planilha, validacao linha a linha, resolucao
de caminhos e regras de UX das notificacoes). Usam apenas a stdlib (`unittest`) -
nao exigem rede nem instalar nada:

```powershell
python -m unittest discover -s tests -v
```

Rode antes de alterar o importador ou o modulo de planilha: sao esses testes que
protegem contra a volta de erros ja corrigidos (nome duplicado, IP invalido,
proxy omitido, coluna obrigatoria ausente).

## Distribuicao (instalador)

Para quem vai usar, basta baixar **`ImportadorCamerasSetup-x.y.z.exe`** na pagina
de *Releases* do repositorio e executar. Nao precisa de Python nem de nenhuma
outra coisa.

O instalador:

- instala **por usuario**, sem pedir administrador, em
  `%LOCALAPPDATA%\Programs\Importador de Cameras`;
- cria atalho no Menu Iniciar (e, opcionalmente, na Area de Trabalho);
- inclui desinstalador (aparece em "Aplicativos instalados").

## Build (executavel e instalador)

Gere o executavel (testado com PyInstaller 6.x):

```powershell
pip install "pyinstaller>=6,<7"
python -m PyInstaller --clean --noconfirm ImportadorCameras.spec
```

E depois o instalador (requer o [Inno Setup 6](https://jrsoftware.org/isdl.php)):

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" instalador.iss
```

Resultados em `dist\`: `ImportadorCameras.exe` (~55 MB) e
`ImportadorCamerasSetup-1.0.0.exe` (~57 MB).

- **Icone**: aparece no arquivo, na janela e na barra de tarefas.
- **Relatorios**: gravados na pasta `reports\` ao lado do executavel, junto com o
  `app_error.log` em caso de falha. Se a pasta do executavel **nao** for gravavel
  (ex.: instalado em `Program Files`), o app passa a usar
  `%LOCALAPPDATA%\ImportadorCameras` automaticamente.
- **Assets**: icone e fonte Inter vao embutidos (via `app/paths.py`).

Atencao ao editar o `.spec`: nao exclua da stdlib modulos que as dependencias
usam. `email` (usado por `requests`/`urllib3`) e `xml` (usado por `openpyxl`) ja
quebraram o executavel quando foram excluidos.

Ao lancar uma nova versao: atualize `AppVersion` no `instalador.iss`, a versao no
`version_info.txt` e gere uma nova Release. **Nunca mude o `AppId`** do
instalador - e ele que permite atualizar por cima e desinstalar corretamente.

## Controle de versao

O projeto esta sob git. O `.gitignore` exclui `reports/`, `__pycache__/`,
`app_error.log`, `build/`, `dist/`, `*.xlsx`, `cameras_normalized.csv`,
`.commandcode/` e saidas de build. Nenhuma credencial nem dado de cliente e
versionado.
