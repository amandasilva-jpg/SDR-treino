# Treino SDR — Chat de Treinamento e Pré-Qualificação

App Flask que simula um chat estilo WhatsApp onde candidatos fazem um treino de SDR (prospecção comercial). O app avalia silenciosamente 4 critérios e gera um dashboard de pré-qualificação.

## Como rodar

```bash
pip install -r requirements.txt
python app.py
```

O app sobe na porta definida pela variável de ambiente `PORT` (padrão 8080).

## Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `PORT`   | 8080    | Porta do servidor |

## Estrutura

- `app.py` — Aplicação completa (chat, motor de conversa, avaliação, admin)
- `requirements.txt` — Dependências (Flask)
- `Procfile` — Comando de start (`web: python app.py`)

## Rotas

| Rota | Descrição |
|------|-----------|
| `/`          | Chat do candidato (interface WhatsApp) |
| `/admin`     | Dashboard de resultados (candidatos, notas, observações) |
| `/admin/export.json` | Exportação de todos os dados em JSON |

## Avaliação

4 critérios (0–10), avaliados silenciosamente a cada etapa:

- Clareza de comunicação (peso 25%)
- Raciocínio comercial (peso 25%)
- Resiliência a objeção (peso 30%)
- Engajamento (peso 20%)

Nota geral = média ponderada. Observações qualitativas geradas automaticamente.

## Notas

- Estado em memória (reseta ao reiniciar). Para persistência, conectar a um banco.
- Sem dependências externas (CDN, APIs). Tudo inline.
- Linguagem: pt-BR.
