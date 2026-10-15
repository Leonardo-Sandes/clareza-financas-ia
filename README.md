# Clareza: dashboard de análise de gastos com Python + IA

Aplicativo local para importar extratos **CSV** ou **PDF com texto selecionável**, separar despesas de entradas, categorizar transações e explorar os resultados com gráficos interativos. Regras locais funcionam sem chave de IA; classificação por IA (Groq) é **opcional e exige consentimento**.

## Estrutura profissional

```text
financas_ia/
├── app.py                         # Interface Streamlit
├── requirements.txt               # Dependências de execução
├── requirements-dev.txt           # Dependências para testes
├── .env.example                   # Exemplo de configuração da IA
├── .gitignore
├── .streamlit/config.toml         # Tema e limite de upload
├── examples/
│   └── extrato_exemplo.csv        # Extrato sintético de demonstração
├── src/financas_ia/
│   ├── constants.py               # Categorias e identidade visual
│   ├── processing.py              # Datas, centavos, débito/crédito
│   ├── parsers/
│   │   ├── csv_parser.py
│   │   └── pdf_parser.py
│   ├── classification/
│   │   ├── rules.py               # Classificador local
│   │   └── llm.py                 # Classificador IA opcional
│   └── analytics/
│       └── summary.py             # KPIs e agregações
└── tests/                         # Testes automatizados
```

## Primeira execução (macOS/Linux)

Abra a pasta `financas_ia` no VS Code e use o terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

No **Windows (PowerShell)**:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

O navegador normalmente abre em `http://localhost:8501`. Não é necessário instalar um banco de dados ou configurar uma API para visualizar o dashboard.

## Nubank (cartão de crédito): leitura automática

O aplicativo reconhece o layout `date,title,amount`, típico da exportação
do cartão Nubank, e sugere automaticamente:

- `date` como **Data**, `title` como **Descrição** e `amount` como **Valor**;
- **positivo = gasto** para compras e parcelas da fatura;
- **negativo = crédito/ajuste** para pagamentos recebidos e ajustes da fatura.

Para outros bancos, a opção **Automático (recomendado)** assume débitos
negativos quando não há perfil reconhecido. Você pode substituir essa convenção
na barra lateral. **Confira sempre a prévia**: o formato das instituições varia,
e a identificação pelo cabeçalho não equivale a validar os lançamentos.

**Atenção:** o dashboard representa cobranças/parcelas do extrato e não
necessariamente o consumo realizado nas datas das compras originais. Pagamentos
de fatura não devem ser somados novamente como consumo.

Teste também com `examples/nubank_cartao_exemplo.csv`, um exemplo sintético
que não contém dados bancários do usuário.

## Teste com CSV de exemplo

1. Faça upload de `examples/extrato_exemplo.csv`.
2. Confira o mapeamento sugerido (`Data`, `Descrição`, `Valor`, `Tipo`).
3. Mantenha `Automático (recomendado)`; no extrato sintético genérico o padrão é débito negativo e a coluna `Tipo` prevalece.
4. Analise os indicadores, altere os filtros e revise `COMPRA XPTO 512` como `Desconhecido`.
5. Corrija a categoria na tabela e exporte os CSVs.

### Para extratos reais

- CSVs devem conter **data, descrição e valor** em colunas independentes; a coluna `Tipo` é opcional.
- Confirme se o banco representa saída como valor **negativo** ou **positivo**. Para layout `date,title,amount` o sentido positivo é sugerido automaticamente. Caso tenha coluna `Tipo` com `Débito`, `Crédito`, `D` ou `C`, ela tem prioridade.
- Débitos e créditos precisam ser conferidos. A aplicação não reconcilia transferências entre contas, faturas pagas ou estornos automaticamente.
- PDFs devem ter linhas textuais com `data descrição valor`, como `03/10/2026 RESTAURANTE -45,90` ou `04/10/2026 MERCADO 25,90 D`. Alguns bancos usam layouts de tabelas com múltiplos valores ou linhas separadas e podem exigir um parser específico.
- **PDF digitalizado (imagem):** OCR não está incluído. Exporte CSV do banco para obter melhor confiabilidade.
- Por segurança, linhas de PDF com múltiplos valores (por exemplo, valor + saldo) são ignoradas e exibem aviso. O objetivo é não inflar indicadores com o saldo da conta.
- A categoria **Desconhecido** é intencional para descrições que não permitem inferência confiável.

## IA opcional (Groq)

1. Crie uma chave de API Groq na plataforma do serviço.
2. Copie `.env.example` para `.env` e preencha `GROQ_API_KEY`:

```bash
cp .env.example .env
```

3. Reinicie o aplicativo, marque `Autorizo enviar descrições desconhecidas à Groq` e clique **Classificar com IA**. Por clique, são enviadas no máximo 200 descrições distintas ainda não analisadas, em lotes de 25.
4. O modelo padrão é `openai/gpt-oss-20b`. Você pode configurá-lo via `GROQ_MODEL`.

**Privacidade:** sem ativar a IA, o aplicativo não envia os dados à Groq. Quando ativada, envia apenas as **descrições de transações previamente desconhecidas**, não datas ou valores. O programa mascara padrões comuns de CPF, e-mail e sequências numéricas, mas **não garante anonimização** de nomes ou outros identificadores que estejam na descrição. Verifique os termos e a política do provedor antes de enviar extratos sensíveis. Os arquivos não são gravados em disco pelo app e os dados em `st.session_state` duram durante a sessão. Não publique o aplicativo sem autenticação e controles de segurança adicionais.

## Testes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Limitações importantes

- A leitura de PDF é limitada a formatos textuais simples; não é um leitor universal de extratos. PDFs de layout específico exigem adaptadores e testes.
- CSVs também variam: revise obrigatoriamente a prévia e os totais de lançamentos descartados.
- Valores são normalizados em **centavos inteiros**, evitando os problemas de precisão de somar `float` no total.
- Lançamentos idênticos não são descartados, pois podem ser compras legítimas repetidas. O app não identifica duplicidade entre vários arquivos.
- Contagem e valor por categoria incluem `Transferências`; essa categoria pode representar movimentação patrimonial e não consumo. Reveja-a antes de concluir quanto gastou efetivamente.
- Edições manuais e respostas da IA ficam na sessão e são incluídas no CSV exportado, mas não são persistidas em banco de dados.
- O app foi pensado para execução individual/local. Para acesso público, implemente autenticação, isolamento por usuário, limites de uso da API, tratamento de dados pessoais e armazenamento seguro.

## Tecnologias

Python, Streamlit, Pandas, Plotly, pdfplumber, Groq (API compatível com OpenAI), python-dotenv e Pytest.
