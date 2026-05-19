<div align="center">
  <br>
  <h1>⚖️ INQUISIDOR JURÍDICO</h1>
  <p><strong>v7.0 — V.victor Digital Flow</strong></p>
  <p><em>Sistema Multi-Agente para Estratégia de Contraditório</em></p>
  <br>
</div>

---

## Visão Geral

O **Inquisidor Jurídico v7.0** é um sistema de IA multi-agente que analisa petições adversárias e constrói estratégias de defesa robustas. Utiliza três agentes especializados (Estrategista, Auditor, Revisor) trabalhando em sequência para produzir relatórios jurídicos completos.

## Funcionalidades

- **Análise de petições:** identifica pontos fracos em argumentos adversários
- **Geração de teses:** elabora parágrafos de contestação com fundamentação
- **Precedentes internacionais:** busca normas e jurisprudência aplicáveis
- **Revisão de consistência:** elimina contradições e polimento final
- **Memória persistente:** armazena análises anteriores em SQLite
- **Integração Obsidian:** salva relatórios automaticamente no vault
- **Redundância dupla:** NVIDIA Llama como primário + Gemini como fallback
- **UI responsiva:** interface redimensionável com barra de progresso

## Arquitetura

```
Petição Adversária
       ↓
┌──────────────────┐
│   Estrategista   │  ← Identifica vulnerabilidades
│   (Agente 1)     │
└────────┬─────────┘
         ↓
┌──────────────────┐
│    Auditor       │  ← Verifica precedentes e leis
│   (Agente 2)     │
└────────┬─────────┘
         ↓
┌──────────────────┐
│    Revisor       │  ← Polimento e consistência
│   (Agente 3)     │
└────────┬─────────┘
         ↓
   Relatório Final
         ↓
   ┌──────────┐
   │ Obsidian │  ← Arquivamento automático
   └──────────┘
```

## Pré-requisitos

- Python 3.10+
- Pip

## Setup

```bash
# 1. Clone ou entre na pasta do projeto
cd inquisidor-juridico

# 2. Crie o ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as chaves de API
cp .env.example .env
# Edite o .env com suas chaves

# 5. Teste a conectividade
python test_motors.py

# 6. Execute
python Inquisidor_V_Victor.py
```

## Configuração

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `NVIDIA_API_KEY` | Sim | Chave da API NVIDIA (`meta/llama-3.3-70b-instruct`) |
| `GOOGLE_API_KEY` | Opcional | Chave da API Gemini (fallback) |
| `OBSIDIAN_VAULT_PATH` | Não | Caminho para o vault Obsidian (opcional) |

## Chaves de API

- **NVIDIA:** [build.nvidia.com](https://build.nvidia.com/) → criar conta → API Keys
- **Gemini:** [aistudio.google.com](https://aistudio.google.com/) → Get API Key

## Uso

1. Execute `python Inquisidor_V_Victor.py`
2. Cole a petição adversária no campo de texto
3. Clique em **"INICIAR ATAQUE COORDENADO"**
4. Os três agentes processam em sequência:
   - **Estrategista:** analisa e identifica pontos fracos
   - **Auditor:** adiciona precedentes e fundamentação
   - **Revisor:** unifica e polimenta o relatório
5. O resultado é exibido em uma nova janela e salvo no Obsidian

## Scripts Auxiliares

| Script | Função |
|--------|--------|
| `test_motors.py` | Testa conectividade NVIDIA e Gemini |
| `claude_cli.py` | CLI simples para testar a API NVIDIA |
| `teste_bloco_a_bloco.py` | Diagnóstico detalhado do ambiente |

## Estrutura do Projeto

```
inquisidor-juridico/
├── Inquisidor_V_Victor.py    # Aplicação principal (UI Tkinter)
├── claude_cli.py              # CLI de teste
├── test_motors.py             # Teste de conectividade
├── teste_bloco_a_bloco.py     # Diagnóstico do ambiente
├── runtime_hook.py             # Hook para PyInstaller
├── config/
│   └── memory.db              # Banco de memória persistente
├── .env.example               # Template de chaves de API
├── .gitignore
├── requirements.txt
└── README.md
```

## Build (PyInstaller)

```bash
pip install pyinstaller
pyinstaller Inquisidor_V_Victor.spec
```

O executável será gerado em `dist/Inquisidor_V_Victor/`.

## Tecnologias

- **CrewAI** — Orquestração multi-agente
- **LiteLLM** — Interface unificada com LLMs
- **NVIDIA API** — Motor principal (Llama 3.3 70B)
- **Gemini API** — Fallback
- **SQLite** — Memória persistente
- **Tkinter** — Interface gráfica
- **Pillow** — Processamento de imagens
- **PyInstaller** — Empacotamento

---

<div align="center">
  <p><strong>INQUISITOR UNIT</strong> — Justiça é cega. O Inquisidor não.</p>
</div>

---

## Licença

```
MIT License
Copyright (c) 2026 ROONDOW
```

Este projeto é licenciado sob MIT — veja o arquivo [LICENSE](LICENSE) para detalhes.

**© 2026 ROONDOW. Todos os direitos reservados.**
