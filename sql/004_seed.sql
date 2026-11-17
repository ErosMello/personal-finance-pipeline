-- Insere o usuário sintético do ETL sem criar faturas ou transações.
SET ROLE finance_owner;

INSERT INTO fin.usuarios (nome) VALUES ('sample_user')
ON CONFLICT (nome) DO NOTHING;

RESET ROLE;
