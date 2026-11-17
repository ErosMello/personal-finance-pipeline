# Faturas sintéticas

Todos os dados deste diretório são fictícios. Os PDFs não contêm dados reais de
contas, titulares, endereços, estabelecimentos ou transações.

- `fatura_01.pdf`: compras duplicadas, um estorno, um pagamento anterior
  ignorado, correspondências por regra e uma descrição sem correspondência.
- `fatura_02.pdf`: correspondências de assinatura e farmácia, além de uma
  descrição sem correspondência.
- `fatura_03.pdf`: correspondências de restaurante e transporte, além de uma
  descrição sem correspondência.

Gere ou confira os arquivos com `python3 -B tools/gerar_amostras.py`. O gerador
usa apenas a biblioteca padrão do Python e valida os totais, as datas e a
cobertura dos casos sem extrair texto dos PDFs. Use `--force` para substituir
amostras existentes de forma intencional. O verificador independente
`python3 -B tools/verificar_amostras.py` requer `pdftotext` ou o pacote Python
`pypdf`. Nenhum desses comandos inicia os serviços.
