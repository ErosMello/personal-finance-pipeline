-- Concede acesso à aplicação e ao BI depois da criação de todos os objetos.
SET ROLE finance_owner;

GRANT USAGE ON SCHEMA fin TO finance_app, finance_bi;

-- Somente leitura: a aplicação não altera usuários, categorias nem regras.
GRANT SELECT ON fin.usuarios, fin.categorias, fin.regras_categoria
  TO finance_app;

-- Leitura e gravação: tabelas carregadas pelo ETL e atualizadas na categorização.
-- UPDATE é necessário por causa de ON CONFLICT ... DO UPDATE no ETL.
GRANT SELECT, INSERT, UPDATE ON fin.bancos, fin.contas, fin.faturas,
  fin.transacoes TO finance_app;

-- Somente USAGE: permite nextval, mas não setval nem leitura direta.
GRANT USAGE ON ALL SEQUENCES IN SCHEMA fin TO finance_app;

GRANT SELECT ON fin.dim_categoria, fin.dim_conta, fin.dim_data,
  fin.fato_transacoes, fin.fato_faturas TO finance_bi;

RESET ROLE;
