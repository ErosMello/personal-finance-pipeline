-- Cria uma dimensão de datas mensal, com calendário fixo para banco vazio.
SET ROLE finance_owner;

CREATE OR REPLACE VIEW fin.dim_data AS
SELECT d::date AS data, extract(year FROM d)::int AS ano, extract(month FROM d)::int AS mes,
       to_char(d,'YYYY-MM') AS ano_mes, extract(quarter FROM d)::int AS trimestre,
       extract(isodow FROM d)::int AS dia_semana,
       (ARRAY['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'])[extract(month FROM d)::int] AS mes_nome
FROM generate_series(
  COALESCE((SELECT date_trunc('month', min(data)::timestamp) FROM fin.transacoes),
           timestamp '2024-01-01'),
  COALESCE((SELECT date_trunc('month', max(data)::timestamp) + interval '1 month - 1 day' FROM fin.transacoes),
           timestamp '2030-12-31'),
  interval '1 day') d;

RESET ROLE;
