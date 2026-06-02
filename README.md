# FakeCheck AI — Sistema de Análise de Confiabilidade de Notícias e Conteúdo Digital

**Projeto Integrador (PI)**

O **FakeCheck AI** é uma plataforma desenvolvida para auxiliar usuários na análise de confiabilidade de conteúdos encontrados na internet. O sistema permite analisar notícias, artigos, publicações e textos extraídos de imagens, retornando uma pontuação de confiabilidade baseada em critérios objetivos definidos pelo backend.

A proposta do projeto é combater a disseminação de desinformação por meio de uma análise automatizada que combina técnicas de extração de conteúdo, OCR e Inteligência Artificial.

---

## Equipe de Desenvolvimento

- José Fernando de Lima Amorim
- Marcello Henrique
- Carlos Eduardo
- Glewbber Spindolla

---

## Objetivo do Projeto

Desenvolver uma API capaz de analisar conteúdos digitais e gerar um indicador de confiabilidade baseado em evidências presentes no texto.

O sistema recebe uma **URL** ou uma **imagem** e retorna:

- Score de confiabilidade (0 a 100)
- Classificação do conteúdo
- Indicadores de evidência
- Indicadores de sensacionalismo
- Resumo do conteúdo
- Pontos positivos
- Pontos de atenção
- Possíveis inconsistências

> Importante: a Inteligência Artificial auxilia na interpretação semântica do conteúdo, porém o **score final é calculado exclusivamente por regras implementadas no backend**.

---

## Tecnologias Utilizadas

### Backend

- Python 3.11+
- FastAPI
- Pydantic
- Uvicorn

### Extração de Conteúdo

- BeautifulSoup4
- Trafilatura

### OCR (Reconhecimento de Texto)

- EasyOCR
- Pillow

### Inteligência Artificial

- OpenRouter
- DeepSeek Chat

---

## Arquitetura da Solução

**Usuário**

↓

**Frontend (em desenvolvimento)**

↓

**Backend (FastAPI)**

- Extração de URLs
- OCR de Imagens
- OpenRouter (IA)
- Sistema de Scoring (regras objetivas)

↓

**Resultado Final**

---

## Funcionalidades

### Análise de URLs

O sistema:

1. Recebe uma URL.
2. Extrai o conteúdo textual da página.
3. Identifica autor, data e referências.
4. Solicita uma análise semântica da IA.
5. Calcula o score de confiabilidade.
6. Retorna um relatório completo.

### Análise de Imagens

O sistema:

1. Recebe uma imagem.
2. Extrai o texto utilizando OCR.
3. Solicita uma análise semântica da IA.
4. Calcula o score de confiabilidade.
5. Retorna um relatório completo.

---

## Estrutura do Projeto

- `backend/`
  - `app/`
    - `main.py`
    - `routes/`
      - `analysis.py`
    - `services/`
      - `url_extractor.py`
      - `image_analyzer.py`
      - `ai_service.py`
      - `scoring_service.py`
    - `models/`
      - `schemas.py`
    - `utils/`
      - `helpers.py`

---

## Configuração do Ambiente

### 1) Criar arquivo `.env`

```env
OPENROUTER_API_KEY=sk-xxxxxxxx
OPENROUTER_MODEL=deepseek/deepseek-chat

LOG_LEVEL=INFO
APP_ENV=development
CORS_ORIGINS=*
```

### 2) Instalar dependências

```bash
pip install -r requirements.txt
```

### 3) Executar o projeto

```bash
uvicorn app.main:app --reload
```

A API ficará disponível em:

- `http://localhost:8000`

Documentação Swagger:

- `http://localhost:8000/docs`

---

## Endpoints Disponíveis

### `POST /api/analyze/url`

**Request**

```json
{
  "url": "https://exemplo.com/noticia"
}
```

### `POST /api/analyze/image`

**Request**

- `multipart/form-data`
- `file: imagem.jpg`

### `GET /api/health`

**Response**

```json
{
  "status": "online"
}
```

---

## Sistema de Pontuação

O score final é calculado pelo arquivo:

- `backend/app/services/scoring_service.py`

### Critérios Utilizados

| Critério | Pontuação |
|---|---:|
| Credibilidade da Fonte | até 40 |
| Autor Identificado | 10 |
| Data de Publicação | 5 |
| Referências Externas | 15 |
| Evidências Detectadas (sinal da IA) | até 20 |
| Ausência de Sensacionalismo (sinal da IA) | até 10 |
| **Total Máximo** | **100** |

### Classificação dos Resultados

| Score | Classificação |
|---:|---|
| 80 a 100 | Alta Confiabilidade |
| 60 a 79 | Confiabilidade Moderada |
| 40 a 59 | Conteúdo Duvidoso |
| 0 a 39 | Possível Desinformação |

### Exemplo de Resposta

```json
{
  "score": 88,
  "classificacao": "Alta Confiabilidade",
  "tipo": "url",
  "titulo": "Título da notícia",
  "resumo": "Resumo gerado pela IA",
  "fonte": {
    "nome": "gov.br",
    "credibilidade": 95
  }
}
```

---

## Docker

### Build

```bash
docker build -t fakecheck-ai .
```

### Executar

```bash
docker run -p 8000:8000 --env-file .env fakecheck-ai
```

---

## Repositórios do Projeto

- **Backend**: contém toda a lógica de análise, integração com IA, OCR e cálculo de confiabilidade.
- **Frontend**: em desenvolvimento.

Link do repositório:

- A definir

---

## Considerações Finais

O **FakeCheck AI** foi desenvolvido como Projeto Integrador com o objetivo de explorar técnicas modernas de processamento de texto, Inteligência Artificial e análise de conteúdo digital, oferecendo uma ferramenta capaz de auxiliar usuários na identificação de possíveis conteúdos enganosos ou pouco confiáveis.

