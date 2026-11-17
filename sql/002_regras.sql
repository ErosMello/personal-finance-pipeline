-- Insere regras de categorização para os dados sintéticos.
SET ROLE finance_owner;

INSERT INTO fin.regras_categoria (padrao, categoria_id)
SELECT v.padrao, c.id FROM (VALUES
 ('SUPERMARKET', 'Mercado'),
 ('GAS STATION', 'Transporte'),
 ('STREAMING', 'Assinaturas'),
 ('PHARMACY', 'Saúde'),
 ('RESTAURANT', 'Restaurantes e Bares'),
 ('RIDE APP', 'Transporte')
) v(padrao, cat) JOIN fin.categorias c ON c.nome = v.cat
ON CONFLICT (padrao) DO UPDATE SET categoria_id = EXCLUDED.categoria_id;

RESET ROLE;
