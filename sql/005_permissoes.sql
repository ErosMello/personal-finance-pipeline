-- Concede acesso à aplicação e ao BI depois da criação de todos os objetos.
SET ROLE finance_owner;

GRANT USAGE ON SCHEMA fin TO finance_app, finance_bi;

GRANT SELECT, INSERT, UPDATE ON fin.usuarios, fin.bancos, fin.contas,
  fin.categorias, fin.faturas, fin.transacoes, fin.regras_categoria
  TO finance_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA fin TO finance_app;

GRANT SELECT ON fin.dim_categoria, fin.dim_conta, fin.dim_data,
  fin.fato_transacoes, fin.fato_faturas TO finance_bi;

RESET ROLE;
