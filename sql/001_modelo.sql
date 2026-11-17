-- Define o schema financeiro, as tabelas, as categorias e as views de consulta.
-- A role finance_owner é proprietária dos objetos, não a role de aplicação.
SET ROLE finance_owner;

CREATE TABLE fin.usuarios (
  id         serial PRIMARY KEY,
  nome       text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fin.bancos (
  id   serial PRIMARY KEY,
  nome text NOT NULL UNIQUE
);

-- Uma conta ou cartão pertence a uma pessoa e a um banco.
CREATE TABLE fin.contas (
  id         serial PRIMARY KEY,
  usuario_id int NOT NULL REFERENCES fin.usuarios(id),
  banco_id   int NOT NULL REFERENCES fin.bancos(id),
  apelido    text NOT NULL,
  tipo       text NOT NULL DEFAULT 'cartao_credito'
             CHECK (tipo IN ('cartao_credito','conta_corrente','dinheiro','outro')),
  UNIQUE (usuario_id, banco_id, apelido)
);

CREATE TABLE fin.categorias (
  id    serial PRIMARY KEY,
  nome  text NOT NULL UNIQUE,
  grupo text NOT NULL
);

CREATE TABLE fin.faturas (
  id          serial PRIMARY KEY,
  conta_id    int NOT NULL REFERENCES fin.contas(id),
  vencimento  date NOT NULL,
  valor_total numeric(12,2) NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (conta_id, vencimento)
);

CREATE TABLE fin.transacoes (
  id               bigserial PRIMARY KEY,
  conta_id         int NOT NULL REFERENCES fin.contas(id),
  fatura_id        int REFERENCES fin.faturas(id) ON DELETE CASCADE,
  data             date NOT NULL,
  descricao        text NOT NULL,
  valor            numeric(12,2) NOT NULL,      -- Positivo para compras; negativo para estornos ou créditos.
  linha            int NOT NULL DEFAULT 1,      -- Diferencia compras iguais feitas no mesmo dia.
  origem           text NOT NULL DEFAULT 'pdf' CHECK (origem IN ('pdf','manual')),
  categoria_id     int REFERENCES fin.categorias(id),   -- NULL indica que não há categoria.
  categoria_fonte  text CHECK (categoria_fonte IN ('regra','llm','manual')),
  categoria_conf   numeric(3,2),
  categorizada_em  timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (conta_id, data, descricao, valor, linha)
);
CREATE INDEX ON fin.transacoes (data);
CREATE INDEX ON fin.transacoes (categoria_id);
CREATE INDEX ON fin.transacoes (fatura_id);

-- As regras são aplicadas antes de enviar transações sem correspondência ao LLM.
CREATE TABLE fin.regras_categoria (
  id           serial PRIMARY KEY,
  padrao       text NOT NULL UNIQUE,
  categoria_id int NOT NULL REFERENCES fin.categorias(id)
);

INSERT INTO fin.categorias (nome, grupo) VALUES
 ('Moradia','Essencial'),('Mercado','Essencial'),('Saúde','Essencial'),
 ('Transporte','Essencial'),('Educação','Essencial'),('Contas e Serviços','Essencial'),
 ('Restaurantes e Bares','Estilo de vida'),('Lazer','Estilo de vida'),
 ('Compras','Estilo de vida'),('Assinaturas','Estilo de vida'),
 ('Viagem','Estilo de vida'),('Cuidados Pessoais','Estilo de vida'),
 ('Impostos e Taxas','Financeiro'),('Investimentos','Financeiro'),
 ('Outros','Outros');

-- Views de consulta.
CREATE VIEW fin.dim_categoria AS
  SELECT id AS categoria_id, nome AS categoria, grupo FROM fin.categorias
  UNION ALL SELECT 0, 'Não categorizada', 'Outros';

CREATE VIEW fin.dim_conta AS
SELECT c.id AS conta_id, c.apelido AS conta, c.tipo, b.nome AS banco, u.nome AS usuario
FROM fin.contas c JOIN fin.bancos b ON b.id=c.banco_id JOIN fin.usuarios u ON u.id=c.usuario_id;

CREATE VIEW fin.fato_transacoes AS
SELECT t.id AS transacao_id, t.conta_id, COALESCE(t.categoria_id,0) AS categoria_id,
       t.fatura_id, t.data, t.descricao, t.valor, t.origem,
       t.categoria_fonte, t.categoria_conf, t.categoria_id IS NULL AS sem_categoria
FROM fin.transacoes t;

CREATE VIEW fin.fato_faturas AS
SELECT f.id AS fatura_id, f.conta_id, f.vencimento, f.valor_total FROM fin.faturas f;

RESET ROLE;
