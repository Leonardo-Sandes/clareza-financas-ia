# Atualização: correção para CSV de fatura do Nubank

## O que estava errado

- Cabeçalho `date,title,amount`: o mapeamento automático não reconhecia `title` como descrição.
- O aplicativo considerava, por padrão, valores negativos como gastos, mas a exportação do cartão Nubank usa **valores positivos para compras** e negativos para pagamentos/créditos.
- Algumas descrições de compra do cartão não eram reconhecidas pelo classificador local (por exemplo, `Dl*Uberrides` e `Amazonmktplc*`).

## O que mudou

1. Mapeamento automático de `date` → Data, `title` → Descrição e `amount` → Valor.
2. Convenção de sinais selecionada automaticamente para cabeçalho `date,title,amount`: **positivo = gasto**.
3. A escolha manual na barra lateral continua disponível para outros extratos.
4. Banner acima da prévia informa a convenção identificada.
5. Ampliação das regras locais para nomes comuns de serviços de transporte, compras e alimentação.
6. Testes automatizados específicos para o layout Nubank, usando **somente dados fictícios**.

## Como atualizar o aplicativo

1. Feche a instância antiga do Streamlit no terminal (`Ctrl+C`).
2. Descompacte a nova versão e abra **essa pasta** `financas_ia` no VS Code.
3. Se possuía um `.env` com `GROQ_API_KEY`, copie-o para a nova pasta sem compartilhar sua chave.
4. Com o ambiente virtual ativo, execute `python -m pip install -r requirements.txt` e `python -m streamlit run app.py`.
5. Importe o CSV novamente. Mantenha `Automático (recomendado)` na barra lateral.
6. Confira a prévia e os indicadores. Não inclua pagamento recebido de fatura como consumo.

**Observações**

- O reconhecimento pelo cabeçalho não é prova de que qualquer CSV de três colunas tenha a mesma convenção. Revise os valores.
- O painel representa as parcelas cobradas no extrato, não a data original de cada compra.
- PDFs textuais e CSVs genéricos continuam aceitos, sujeitos ao mapeamento/convenção do extrato.
- Extratos financeiros reais não estão incluídos neste projeto/ZIP.
