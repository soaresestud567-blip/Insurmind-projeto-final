# Sistema Inteligente para Análise Comparativa de Apólices D&O

## 1. Sobre o projeto

Este projeto é um MVP acadêmico para análise automatizada de documentos de seguro D&O (Directors and Officers Liability Insurance).

O sistema utiliza processamento de documentos, OCR e Inteligência Artificial Generativa para auxiliar na extração, estruturação, consulta e comparação de informações presentes em apólices e documentos contratuais de seguro D&O.

Entre as funcionalidades disponíveis estão:

- upload de documentos PDF e imagens;
- extração de texto nativo de arquivos PDF;
- OCR de páginas digitalizadas;
- extração estruturada de informações com IA;
- identificação do tipo de documento;
- armazenamento local das análises;
- consulta de documentos já processados;
- comparação entre dois documentos D&O;
- identificação de diferenças contratuais;
- geração de relatório comparativo em Markdown;
- recuperação de processamento por cache em documentos extensos.

> Este sistema é um MVP acadêmico. Os resultados produzidos automaticamente devem ser conferidos com os documentos originais e não constituem aconselhamento jurídico, securitário ou profissional.

---

## 2. Arquitetura

O sistema foi desenvolvido utilizando uma arquitetura modular baseada em agentes especializados.

Fluxo principal:

```text
Upload
  ↓
ReceptionAgent
  ↓
OCRAgent
  ↓
ExtractionAgent
  ↓
StructureAgent
  ↓
SQLite
  ↓
Consulta / ComparisonAgent
  ↓
ReportAgent
  ↓
Interface Streamlit
```

### Agentes principais

**ReceptionAgent**

Responsável pelo recebimento e validação inicial dos documentos enviados pelo usuário.

**OCRAgent**

Responsável pela extração do conteúdo textual. PDFs com camada de texto utilizam extração nativa e páginas digitalizadas podem ser processadas pelo Tesseract OCR.

**ExtractionAgent**

Utiliza IA generativa por meio do OpenRouter para transformar o conteúdo textual em dados estruturados relevantes para análise D&O.

Documentos extensos são divididos em blocos e possuem mecanismo de cache para reduzir a necessidade de repetir blocos já processados.

**StructureAgent**

Normaliza os dados extraídos e auxilia na classificação do documento, diferenciando, por exemplo, Condições Gerais e documentos individualizados.

**ComparisonAgent**

Realiza uma comparação híbrida. Campos objetivos são comparados localmente, enquanto aspectos contratuais e semânticos podem ser analisados por IA.

**ReportAgent**

Organiza o resultado da comparação e produz um relatório comparativo em Markdown.

---

## 3. Tecnologias utilizadas

- Python
- Streamlit
- OpenAI Python SDK
- OpenRouter
- PyMuPDF
- Tesseract OCR
- pytesseract
- Pillow
- SQLite
- pandas
- python-dotenv

---

## 4. Pré-requisitos

Para executar o projeto é necessário possuir:

- Python instalado;
- Tesseract OCR instalado;
- conexão com a internet para as funcionalidades de IA;
- uma chave válida do OpenRouter.

O Tesseract pode ser instalado no caminho padrão do Windows:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Também é necessário possuir os idiomas utilizados pelo OCR. O projeto utiliza:

```text
por
eng
```

---

## 5. Instalação

Abra o terminal na pasta do projeto.

### Criar ambiente virtual

```powershell
python -m venv venv
```

### Ativar o ambiente virtual no Windows PowerShell

Caso o ambiente virtual esteja dentro da pasta atual:

```powershell
.\venv\Scripts\Activate.ps1
```

Caso esteja utilizando a estrutura em que o ambiente virtual está um nível acima da aplicação:

```powershell
..\venv\Scripts\Activate.ps1
```

### Instalar dependências

```powershell
pip install -r requirements.txt
```

---

## 6. Configuração

Copie o arquivo:

```text
.env.example
```

e crie um arquivo chamado:

```text
.env
```

Configure as variáveis:

```text
OPENROUTER_API_KEY=sua_chave_aqui
OPENROUTER_MODEL=openrouter/free
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Nunca publique ou compartilhe o arquivo `.env` contendo uma chave real.

O projeto foi configurado para utilizar:

```text
openrouter/free
```

e possui proteção no código contra a seleção acidental de outro modelo.

---

## 7. Execução

Com o ambiente virtual ativado e dentro da pasta que contém `app.py`, execute:

```powershell
streamlit run app.py
```

O Streamlit disponibilizará a aplicação no navegador.

---

## 8. Utilização

### Analisar documento

Na área de análise:

1. selecione um arquivo compatível;
2. envie o documento;
3. inicie a análise;
4. aguarde a extração de texto e o processamento;
5. confira os dados estruturados e as evidências apresentadas.

O sistema pode processar documentos com texto nativo e documentos digitalizados que necessitem de OCR.

### Consultar documentos

Os documentos processados podem ser consultados posteriormente através dos registros armazenados localmente no SQLite.

### Comparar documentos

Na área de comparação:

1. selecione o Documento A;
2. selecione o Documento B;
3. clique em **Comparar apólices**;
4. analise as diferenças, pontos de atenção e similaridades;
5. opcionalmente, baixe o relatório comparativo em Markdown.

---

## 9. Comparação híbrida

A comparação utiliza duas estratégias.

### Comparação objetiva local

Campos estruturados, como:

- seguradora;
- segurado;
- moeda;
- limites;
- franquia;
- prêmio;
- vigência;

podem ser comparados deterministicamente sem necessidade de IA.

### Comparação semântica

Aspectos como:

- coberturas;
- exclusões;
- extensões;
- definições;
- cláusulas;
- condições contratuais;

podem ser analisados pela IA.

Caso a cota gratuita da IA esteja temporariamente indisponível, a comparação objetiva local ainda pode ser utilizada.

---

## 10. Cache e documentos extensos

Para melhorar a robustez do processamento, o sistema utiliza cache dos blocos analisados.

Os dados são armazenados em:

```text
data/extraction_cache/
```

Caso o processamento de um documento extenso seja interrompido, os blocos concluídos podem ser reaproveitados em uma nova tentativa.

Isso é especialmente útil quando há indisponibilidade temporária ou limitação da API.

---

## 11. Banco de dados

Os documentos analisados são armazenados localmente utilizando SQLite.

Arquivo padrão:

```text
data/policies.db
```

O banco contém dados estruturados e texto extraído dos documentos analisados.

Por esse motivo, o arquivo não deve ser publicado quando contiver documentos ou informações confidenciais.

---

## 12. Segurança e privacidade

O arquivo `.gitignore` impede que determinados dados locais sejam incluídos acidentalmente no repositório, incluindo:

```text
.env
data/policies.db
data/uploads/
data/extraction_cache/
```

O OCR com Tesseract é executado localmente.

Entretanto, para realizar a extração e determinadas análises semânticas, conteúdo textual dos documentos pode ser enviado ao serviço de IA configurado através do OpenRouter.

Portanto, documentos confidenciais somente devem ser processados quando houver autorização e quando o tratamento das informações pelo provedor utilizado for considerado adequado.

---

## 13. Limitações

Este MVP possui limitações inerentes ao uso de OCR e modelos generativos.

Entre elas:

- erros de OCR em documentos de baixa qualidade;
- possibilidade de erros ou omissões na extração por IA;
- diferenças de estrutura entre seguradoras;
- informações que dependem de Especificações, Endossos ou outros documentos complementares;
- limites de utilização do serviço gratuito de IA;
- interpretação semântica sujeita a imprecisões.

Em documentos classificados como **Condições Gerais**, a existência de uma cobertura ou cláusula no texto não significa necessariamente que ela tenha sido efetivamente contratada por um segurado específico.

A ausência de determinada informação nos dados extraídos também não significa necessariamente que a informação esteja ausente do documento original.

---

## 14. Tratamento de erros

O sistema possui tratamento para situações como:

- arquivo inválido;
- texto insuficiente;
- falha de OCR;
- chave de API ausente;
- modelo configurado incorretamente;
- limite gratuito da API atingido;
- resposta inválida da IA;
- registros indisponíveis ou inválidos durante consultas e comparações.

---

## 15. Estrutura simplificada do projeto

```text
dao_policy_ai_mvp/
│
├── app.py
├── pipeline.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── agents/
│   ├── reception_agent.py
│   ├── ocr_agent.py
│   ├── extraction_agent.py
│   ├── structure_agent.py
│   ├── comparison_agent.py
│   └── report_agent.py
│
├── services/
│   └── database.py
│
└── data/
    ├── uploads/
    ├── extraction_cache/
    └── policies.db
```

Alguns arquivos e diretórios da pasta `data` são gerados durante a execução e podem não estar presentes em uma instalação limpa.

---

## 16. Solução de problemas

### Tesseract não encontrado

Confirme o caminho configurado no `.env`:

```text
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Limite gratuito da IA

Se o serviço retornar erro relacionado a limite diário ou HTTP 429, aguarde a renovação da cota gratuita.

Em documentos extensos, blocos já processados podem permanecer armazenados no cache e serem reaproveitados posteriormente.

### Chave do OpenRouter não encontrada

Confirme se existe um arquivo `.env` na pasta da aplicação contendo:

```text
OPENROUTER_API_KEY=sua_chave_aqui
```

Não inclua aspas desnecessárias ou espaços ao redor do `=`.

---

## 17. Aviso

Este software foi desenvolvido para fins acadêmicos e demonstrativos.

As análises produzidas pelo sistema são ferramentas auxiliares e não substituem a leitura integral dos documentos originais nem a avaliação de profissionais especializados.