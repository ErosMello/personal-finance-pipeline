# Execução isolada

Este procedimento inicia apenas o projeto Docker Compose `pfp-test`, usando as
faturas fictícias em `samples/`. Nunca monte o diretório de um projeto pessoal,
um arquivo `.env` real, backups ou dados financeiros reais.

## Requisitos

- Linux ou WSL2 (Windows). Os comandos usam ferramentas GNU, como `sha256sum`, e
  não foram testados no macOS. No Windows, execute tudo dentro do WSL2; os
  arquivos `.sh` precisam ter finais de linha LF, o que `.gitattributes` garante.
- Docker com Docker Compose v2 e Git.
- Python 3, curl e sha256sum.
- Cerca de 8 GB de disco livre (imagens, volumes e o modelo de 2,5 GB) e vários
  GB de RAM livres para o modelo.
- Acesso à internet para baixar o modelo.
- As portas locais `15432` (PostgreSQL) e `15679` (n8n) livres. Se não estiverem
  livres, escolha outras portas e altere `POSTGRES_PORT` e `N8N_PORT` no arquivo
  de ambiente de teste.

## Preparar a área de teste

Confirme que `$HOME/pfp-test` ainda não existe. Crie esse diretório com permissão `700`.
Copie o endereço HTTPS do botão **Code** na página do repositório publicado e
substitua o marcador no comando abaixo. Execute os comandos seguintes a partir
do clone:

```bash
set -euo pipefail
mkdir -m 700 "$HOME/pfp-test"
git clone --branch main <URL_HTTPS_COPIADA_DO_REPOSITORIO> "$HOME/pfp-test/repo"
cd "$HOME/pfp-test/repo"
mkdir -m 700 "$HOME/pfp-test/models"
MODEL_DIRECTORY="$HOME/pfp-test/models" ./scripts/baixar_modelo.sh
```

O script baixa o GGUF e verifica seu SHA-256. O diretório criado para o teste
contém somente esse arquivo e será montado como somente leitura.

Crie `$HOME/pfp-test/.env` e `$HOME/pfp-test/llama_key` com valores
aleatórios novos. O diretório e os arquivos ficam fora do clone; não mostre seus
conteúdos. O diretório `models` contém somente o GGUF escolhido e é montado como
leitura; não monte um diretório de modelos compartilhado:

```bash
python3 -B - <<'PY'
import os
import secrets
from pathlib import Path

root = Path.home() / "pfp-test"
model_directory = Path.home() / "pfp-test" / "models"
llm_key = secrets.token_hex(32)
values = {
    "POSTGRES_DB": "finance",
    "POSTGRES_USER": "finance_admin",
    "POSTGRES_PASSWORD": secrets.token_hex(32),
    "FINANCE_APP_PASSWORD": secrets.token_hex(32),
    "FINANCE_BI_PASSWORD": secrets.token_hex(32),
    "N8N_ENCRYPTION_KEY": secrets.token_hex(32),
    "LLM_API_KEY": llm_key,
    "LLM_API_KEY_FILE": "../llama_key",
    "POSTGRES_PORT": "15432",
    "N8N_PORT": "15679",
    "PDF_DIRECTORY": "./samples",
    "MODEL_DIRECTORY": str(model_directory.resolve()),
}
(root / ".env").write_text(
    "".join(f"{key}={value}\n" for key, value in values.items()),
    encoding="utf-8",
)
(root / "llama_key").write_text(llm_key + "\n", encoding="utf-8")
os.chmod(root / ".env", 0o600)
os.chmod(root / "llama_key", 0o600)
PY
```

O Compose monta somente `$HOME/pfp-test/models` em modo de leitura; nenhum
diretório de dados pessoais deve ser usado. Confira a configuração antes de
iniciar qualquer serviço:

```bash
docker compose -p pfp-test --env-file ../.env config --quiet
```

Revise o projeto, as portas, os volumes e os caminhos montados. Inicie os
serviços somente depois que você aprovar explicitamente este plano:

```bash
docker compose -p pfp-test --env-file ../.env up -d
docker compose -p pfp-test --env-file ../.env ps
```

O projeto cria apenas os volumes `pfp-test_pgdata` e `pfp-test_n8n_data`, a rede
`pfp-test_internal` e os serviços definidos neste Compose. Os arquivos PDF são
montados como somente leitura em `/data/pdfs`; o diretório de modelos é montado
como somente leitura em `/models`.

## Conferir a inicialização do banco

Confira os logs do serviço `postgres` e confirme que os scripts `000_roles.sh`,
`001_modelo.sql`, `002_regras.sql`, `003_dim_data.sql`, `004_seed.sql` e
`005_permissoes.sql` foram executados nessa ordem, sem erros:

```bash
docker compose -p pfp-test --env-file ../.env logs --no-color postgres
```

No banco de teste, confirme que `finance_owner` é NOLOGIN; `finance_app` e
`finance_bi` são roles de login sem atributos administrativos; o schema e todos
os objetos pertencem a `finance_owner`; `finance_bi` lê apenas as cinco views;
e `finance_app` não tem permissão para excluir, truncar ou alterar objetos.
Use as consultas abaixo como `finance_admin`. Os resultados mostram somente
atributos, permissões e contagens:

```bash
docker compose -p pfp-test --env-file ../.env exec -T postgres \
  psql -X -U finance_admin -d finance -At -F '|' -c "
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_roles
WHERE rolname IN ('finance_owner', 'finance_app', 'finance_bi')
ORDER BY rolname;
SELECT pg_get_userbyid(nspowner)
FROM pg_namespace
WHERE nspname = 'fin';
SELECT count(*), count(*) FILTER (WHERE pg_get_userbyid(c.relowner) <> 'finance_owner')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'fin' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'i', 'I', 'f');
SELECT
  (SELECT count(*) FROM unnest(ARRAY['fin.dim_categoria', 'fin.dim_conta', 'fin.dim_data',
    'fin.fato_transacoes', 'fin.fato_faturas']::text[]) AS v(nome)
   WHERE has_table_privilege('finance_bi', v.nome, 'SELECT')),
  (SELECT count(*) FROM unnest(ARRAY['fin.usuarios', 'fin.bancos', 'fin.contas',
    'fin.categorias', 'fin.faturas', 'fin.transacoes', 'fin.regras_categoria']::text[]) AS t(nome)
   WHERE has_table_privilege('finance_bi', t.nome, 'SELECT')),
  (SELECT count(*) FROM unnest(ARRAY['fin.dim_categoria', 'fin.dim_conta', 'fin.dim_data',
    'fin.fato_transacoes', 'fin.fato_faturas']::text[]) AS v(nome)
   WHERE has_table_privilege('finance_bi', v.nome, 'INSERT')
      OR has_table_privilege('finance_bi', v.nome, 'UPDATE')
      OR has_table_privilege('finance_bi', v.nome, 'DELETE')
      OR has_table_privilege('finance_bi', v.nome, 'TRUNCATE'));
SELECT has_table_privilege('finance_app', 'fin.transacoes', 'SELECT'),
       has_table_privilege('finance_app', 'fin.transacoes', 'INSERT'),
       has_table_privilege('finance_app', 'fin.transacoes', 'UPDATE'),
       has_table_privilege('finance_app', 'fin.transacoes', 'DELETE'),
       has_table_privilege('finance_app', 'fin.transacoes', 'TRUNCATE'),
       has_schema_privilege('finance_app', 'fin', 'CREATE'),
       pg_has_role('finance_app', 'finance_owner', 'MEMBER');
"
```

## Importar os fluxos de trabalho e a credencial

Crie uma credencial PostgreSQL de teste com host `postgres`, porta `5432`, banco
`finance`, usuário `finance_app` e a senha `FINANCE_APP_PASSWORD` do arquivo
`../.env`. Use conexão sem SSL. O script abaixo cria o JSON da credencial e
cópias temporárias dos fluxos de trabalho com todos os nós Postgres associados a ela.
O CLI espera um array JSON com um objeto de credencial.
Os arquivos ficam fora do clone e recebem permissão `600`; não os imprima nem os
adicione ao repositório:

```bash
python3 -B - <<'PY'
import json
import os
import uuid
from pathlib import Path

root = Path.home() / "pfp-test"
repo = root / "repo"
env = dict(
    line.split("=", 1)
    for line in (root / ".env").read_text(encoding="utf-8").splitlines()
    if line and not line.startswith("#")
)
credential_id = str(uuid.uuid4())
credential_name = "pfp-test finance_app"
credential = {
    "id": credential_id,
    "name": credential_name,
    "type": "postgres",
    "data": {
        "host": "postgres",
        "port": 5432,
        "database": env["POSTGRES_DB"],
        "user": "finance_app",
        "password": env["FINANCE_APP_PASSWORD"],
        "ssl": "disable",
        "allowUnauthorizedCerts": False,
    },
}
(root / "credential.json").write_text(
    json.dumps([credential], ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
os.chmod(root / "credential.json", 0o600)

workflows_directory = root / "workflows"
workflows_directory.mkdir(mode=0o700, exist_ok=True)
total_postgres_nodes = 0
for filename in ("Finance_ETL_Core.json", "Finance_Categorizar.json"):
    source = repo / "n8n" / filename
    data = json.loads(source.read_text(encoding="utf-8"))
    workflows = data if isinstance(data, list) else [data]
    for workflow in workflows:
        for node in workflow.get("nodes", []):
            if node.get("type") == "n8n-nodes-base.postgres":
                node["credentials"] = {
                    "postgres": {"id": credential_id, "name": credential_name}
                }
                total_postgres_nodes += 1
    target = workflows_directory / filename
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(target, 0o600)
if total_postgres_nodes != 5:
    raise ValueError("A quantidade de nós PostgreSQL não é a esperada.")
PY
```

Copie os arquivos temporários para o contêiner n8n e importe a credencial e os
fluxos de trabalho pelo CLI. Não altere os arquivos de fluxo de trabalho do clone:

```bash
n8n_id=$(docker compose -p pfp-test --env-file ../.env ps -q n8n)
docker cp ../credential.json "$n8n_id:/tmp/pfp-credential.json"
docker compose -p pfp-test --env-file ../.env exec -T n8n \
  n8n import:credentials --input=/tmp/pfp-credential.json
docker cp ../workflows/Finance_ETL_Core.json "$n8n_id:/tmp/Finance_ETL_Core.json"
docker cp ../workflows/Finance_Categorizar.json "$n8n_id:/tmp/Finance_Categorizar.json"
docker compose -p pfp-test --env-file ../.env exec -T n8n \
  n8n import:workflow --input=/tmp/Finance_ETL_Core.json
docker compose -p pfp-test --env-file ../.env exec -T n8n \
  n8n import:workflow --input=/tmp/Finance_Categorizar.json
```

Antes de executar os fluxos, aguarde o modelo terminar de carregar. Se ele ainda
não responder, `Finance_Categorizar` conclui sem erro, mas sem categorias do LLM.
Repita a consulta abaixo até que responda (o resultado esperado inclui
`"status":"ok"`); ela precisa do serviço n8n em execução. Se `wget` não existir
na imagem, o laço repete indefinidamente: interrompa com `Ctrl+C` e use a
alternativa pelos logs descrita abaixo:

```bash
until docker compose -p pfp-test --env-file ../.env exec -T n8n \
  wget -qO- http://llm:8080/health; do sleep 5; done
```

Se o comando não estiver disponível na imagem, aguarde a mensagem
`server is listening` nos logs com
`docker compose -p pfp-test --env-file ../.env logs llm`.

Depois, pare apenas o serviço n8n do projeto de teste. Execute cada fluxo de
trabalho em um contêiner temporário, sem dependências, para evitar concorrência
com o processo n8n que usa o mesmo banco SQLite. Execute primeiro
`Finance_ETL_Core`, depois `Finance_Categorizar` e, por fim, o ETL novamente para
conferir a idempotência:

```bash
docker compose -p pfp-test --env-file ../.env stop n8n
docker compose -p pfp-test --env-file ../.env run --rm -T --no-deps n8n \
  execute --id=xWdSQhzZIT996VBR1A57l
docker compose -p pfp-test --env-file ../.env run --rm -T --no-deps n8n \
  execute --id=catFinWf0000001
docker compose -p pfp-test --env-file ../.env run --rm -T --no-deps n8n \
  execute --id=xWdSQhzZIT996VBR1A57l
docker compose -p pfp-test --env-file ../.env start n8n
```

Se uma execução falhar antes do último comando, inicie novamente o serviço de
teste com `docker compose -p pfp-test --env-file ../.env start n8n`.

## Conferir dados e views

Confira que os três PDFs foram processados, que os totais conferem ao centavo,
que as compras repetidas receberam valores distintos de `linha`, que o estorno
foi armazenado como negativo e que o pagamento anterior foi ignorado. Repita o
ETL e confirme que não foram criadas linhas duplicadas. Registre apenas
contagens e tempos, sem descrições, nomes de estabelecimentos ou valores.

Consulte as contagens do ETL e os casos de borda como `finance_admin`. Com as
amostras sintéticas, o primeiro `SELECT` deve retornar `3|11|8|3|0` (faturas,
transações, por regra, por LLM e sem categoria). Se a coluna de LLM for `0` e a
de sem categoria for `3`, o modelo não estava pronto: aguarde-o e execute
`Finance_Categorizar` de novo.

```bash
docker compose -p pfp-test --env-file ../.env exec -T postgres \
  psql -X -U finance_admin -d finance -At -F '|' -c "
SELECT
  (SELECT count(*) FROM fin.faturas),
  (SELECT count(*) FROM fin.transacoes),
  (SELECT count(*) FROM fin.transacoes WHERE categoria_fonte = 'regra'),
  (SELECT count(*) FROM fin.transacoes WHERE categoria_fonte = 'llm'),
  (SELECT count(*) FROM fin.transacoes WHERE categoria_id IS NULL);
SELECT
  (SELECT count(*) FROM (
    SELECT conta_id, data, descricao, valor
    FROM fin.transacoes
    GROUP BY conta_id, data, descricao, valor
    HAVING count(*) > 1 AND count(DISTINCT linha) = count(*)
  ) duplicatas),
  (SELECT count(*) FROM fin.transacoes WHERE valor < 0),
  (SELECT count(*) FROM fin.transacoes WHERE descricao ILIKE 'Pagamento%'),
  (SELECT count(*) FROM fin.faturas f
   WHERE f.valor_total = COALESCE(
     (SELECT sum(t.valor) FROM fin.transacoes t WHERE t.fatura_id = f.id), 0)),
  (SELECT count(*) FROM (
    SELECT conta_id, data, descricao, valor, linha
    FROM fin.transacoes
    GROUP BY conta_id, data, descricao, valor, linha
    HAVING count(*) > 1
  ) duplicatas);
"
```

Conecte-se como `finance_bi` usando a senha de teste e consulte as cinco views.
As contagens são retornadas nesta ordem: `dim_categoria`, `dim_conta`,
`dim_data`, `fato_transacoes` e `fato_faturas`.

```bash
docker compose -p pfp-test --env-file ../.env exec -T postgres sh -c \
  'PGPASSWORD="$FINANCE_BI_PASSWORD" psql -w -h 127.0.0.1 -U finance_bi -d "$POSTGRES_DB" -At -c "SELECT count(*) FROM fin.dim_categoria; SELECT count(*) FROM fin.dim_conta; SELECT count(*) FROM fin.dim_data; SELECT count(*) FROM fin.fato_transacoes; SELECT count(*) FROM fin.fato_faturas;"'
```

## Encerrar

Depois das verificações, encerre somente o projeto de teste e remova somente os
volumes desse projeto:

```bash
docker compose -p pfp-test --env-file ../.env down -v
```

Confirme que nenhum outro contêiner ou volume foi alterado. Mantenha
`$HOME/pfp-test` para você remover depois; não apague arquivos fora dessa área.
