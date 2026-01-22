# AI Specialist Agent Framework

A production-grade agentic AI system with RAG, multi-agent collaboration (Warroom), and advanced knowledge management.

## Features

- **🧠 ReAct Loop**: Reasoning + Acting agent architecture
- **📚 3x3 RAG Matrix**: Domain-aware knowledge retrieval with multi-layer query expansion
- **🤝 Warroom System**: Multi-agent consensus engine using LangGraph
- **💾 Vector Memory**: Persistent semantic memory with pgvector
- **🛡️ Safety Guardrails**: Cost governor, smart context slicing, sanitization
- **🔧 Extensible Tools**: File operations, document generation, RAG corpus management

## Architecture

```
User → CLI → Agent (ReAct Loop) → Tools (RAG, File Ops, Warroom)
                 ↓
         LLM (Gemini 3) → Response
                 ↓
         Supabase (DB + Vector Memory)
```

## Tech Stack

- **Python 3.10+**
- **LiteLLM** - Multi-provider LLM abstraction
- **Vertex AI** - RAG corpus and model serving
- **Supabase** - PostgreSQL + pgvector for persistence
- **LangGraph** - Multi-agent orchestration

## Setup

1. **Clone the repository**
```bash
git clone https://github.com/LinckK/ai_specialist-.git
cd ai_specialist-
```

2. **Create .env file** (CRITICAL - DO NOT COMMIT)
```env
GEMINI_API_KEY=your_key_here
GEMINIFLASH_API_KEY=your_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_key_here
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the agent**
```bash
python -m agent_project.cli
```

## Documentation

Comprehensive technical documentation available in `Documentation/`:
- `00_Architecture_Overview.md` - System architecture and debugging flowcharts
- `01_Core_Engine.md` - ReAct loop, smart slicing, cost governor
- `02_Hive_Mind.md` - Warroom multi-agent system
- `03_Knowledge_Engine.md` - RAG 3x3 matrix and vector memory
- `04_Tool_Suite.md` - File operations and capabilities

## Key Concepts

- **Smart Slicing**: Context window management preserving System + Memory + Recent
- **3x3 RAG Matrix**: Query expansion across Philosophy → Strategy → Tactics layers
- **Persona Active**: Domain-specific RAG retrieval based on agent personality
- **Writing Plan System**: Multi-turn document generation with state tracking
- **Council Protocol**: Inter-agent grounding verification

## Project Structure

```
agent_project/
├── agent.py              # Main ReAct loop
├── config.py             # System configuration
├── warroom.py            # Multi-agent orchestration
├── db.py                 # Supabase client
├── memory_store.py       # Vector memory
├── tools/
│   ├── rag_tool.py       # 3x3 Matrix RAG
│   ├── file_operations_tool.py
│   ├── document_tool.py
│   └── upload_tool.py
└── cli.py                # Command-line interface
```

## License

MIT

## Contributing

Pull requests welcome. For major changes, please open an issue first.
