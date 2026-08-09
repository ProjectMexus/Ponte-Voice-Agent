[繁體中文](README.md) | [English](README.en.md)

<div align="center">
  <img src="background.png" alt="Ponte — Listening to Macau. Connecting people's stories." width="100%" />
</div>

<div align="center">
  <h1>Ponte</h1>
  <p><strong>Helping older adults access public services through natural conversation.</strong></p>
  <p>
    <a href="https://ponte-8k6h.onrender.com/">🌐 Live Demo</a> •
    <a href="docs/PonteArch.md">📐 Architecture</a> •
    <a href="docs/render-deployment.md">🚀 Deployment</a>
  </p>
</div>

Ponte is a public-service AI assistant prototype built around Cantonese and Traditional Chinese. Users describe what they need by voice or text, and controlled workflows connect them to simulated healthcare, Macau One Account (一戶通), and social services. Task cards show progress, available options, and actions awaiting approval. The interface also supports English.

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend / middleware | Python 3.13+, standard-library HTTP server |
| AI / agent protocol | Model Context Protocol (MCP), OpenAI-compatible LLM API |
| Frontend | Vanilla JavaScript, Web Speech API |
| Infrastructure | Docker, JSON-RPC, Render |

## Why Ponte?

Accessing public services should not require knowing which platform to open, which form to fill in, or which department to contact. Ponte brings those service entry points into a conversation users can follow, with opportunities to review arrangements, change requirements, and stop an operation.

| User experience | Design and controls |
| --- | --- |
| Voice and text input | Large text, high contrast, and spoken readouts; voice and text share the interaction flow, with separate explicit approval for submissions. |
| Visible progress | Separate task cards show steps, results, and available next actions. |
| Explicit approval | Key operations that change service data require user confirmation. |
| Controlled tool access | Middleware routes operations through predefined MCP tools and workflows. |

## Services to explore

| Service | What Ponte does |
| --- | --- |
| Appointment enquiries | Show mock appointments with their service, date, time, location, and status. |
| Medical bookings | Find available slots and create a mock appointment after approval. |
| Cash-sharing scheme | Retrieve a simulated Macau One Account scheme summary. |
| Activities for older adults | Search simulated activities through registered read tools when agent mode is enabled. |

Select **EN** in the header for English interaction. Try `I would like to see my medical appointments.` or `I would like to book a medical appointment.` English text input, service responses, and task cards share the same interaction and approval flow as Chinese. Speech recognition and readouts depend on the browser or configured voice service; available voices vary by environment.

## Architecture at a glance

```text
Browser: voice / text and task workspace
                  │ HTTP
                  ▼
Middleware: intent, workflows, approvals, task state
                  │ stdio JSON-RPC
                  ▼
MCP: fixed tool registry and REST adapters
                  │ HTTP
                  ▼
Mock backends: medical / One Account / social welfare
```

The model interprets requests, proposes next steps, and explains results. Middleware owns task state, tool permissions, and confirmation rules. Existing workflows run by default; enabling the agent lets the model select tools and observe results through the same interaction entry point.

Before booking, the server validates the service, slot, and prerequisites, then issues a confirmation action bound to that proposal. Text such as “yes” or “OK” does not authorize submission. Changed requests withdraw pending proposals. After valid approval, the server executes with an idempotency key and verifies the receipt before reporting success. See the [implemented agent architecture](docs/AGENT_EXECUTION.md) for the execution flow and limitations.

## Quick start

### Requirements

- Python 3.13+
- A modern browser; allow microphone access if using voice input
- No additional Python packages or frontend build tools required

On first setup, copy the configuration template. Keep your existing `.env` if you already have one.

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

Start the stack:

```bash
python scripts/run_stack.py
```

When `Ponte stack is ready.` appears, open the printed frontend URL, normally `http://127.0.0.1:5173/`. Press `Ctrl-C` to stop the stack.

Docker Compose is also available:

```bash
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173). For hosted setup, see the [Render deployment guide](docs/render-deployment.md).

## LLM configuration

The default workflows use keyword recognition when no LLM is configured. To enable the multi-turn agent, set the following fields in your local `.env`, replace the example values with your provider settings, and use the same startup command:

```dotenv
PONTE_AGENT_ENABLED=true
PONTE_LLM_API_URL=https://your-provider.example/v1/chat/completions
PONTE_LLM_API_KEY=your-api-key
PONTE_LLM_MODEL=your-model-id
```

`PONTE_AGENT_ENABLED` defaults to `false`. Enabled mode requires complete model configuration. Provider errors pause processing without silently switching execution modes. The agent currently permits validated medical appointment creation as its only write operation. Conversation history, pending proposals, and replay records stay in one process's memory and do not recover after a server restart.

Separate `PONTE_TASK_RECOVERY_LLM_*` settings configure a model that receives sanitized tool results and proposes task recovery guidance. Keep API keys out of version control. Full settings are documented in the [middleware README](middleware/README.md).

## Testing

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s MCP/tests -v
python -m unittest discover -s middleware/tests -v
python -m compileall -q MCP middleware mock_backends frontend scripts tests
```

English interaction and agent integration tests use local mock services and need no paid model API key:

```bash
python -m unittest tests.test_english_interactions tests.test_agent_full_stack -v
```

Frontend checks:

```bash
python -m unittest tests.test_frontend_static -v
node --check frontend/app.js
node --check frontend/interaction-view.js
```

Verification records, execution details, and logging behavior are in the [agent execution document](docs/AGENT_EXECUTION.md).

## Project structure

| Path | Purpose |
| --- | --- |
| [`frontend/`](frontend/) | Voice-first interface and middleware client, with no build step. |
| [`middleware/`](middleware/) | Interaction routing, workflows, confirmations, sessions, and MCP process management. |
| [`MCP/`](MCP/) | Fixed tool registry, stdio JSON-RPC server, and REST adapters. |
| [`mock_backends/`](mock_backends/) | Simulated medical, One Account, and social services. |
| [`database/`](database/) | Local JSON Lines mock data; generated runtime data should stay out of version control. |
| [`scripts/run_stack.py`](scripts/run_stack.py) | Local stack launcher. |
| [`render.yaml`](render.yaml) | Render deployment blueprint for a single container. |

Further reading:

- [Architecture and design principles](docs/PonteArch.md)
- [Product vision](docs/Ponte公共服務平台.md)
- [Implemented agent execution and verification](docs/AGENT_EXECUTION.md)
- [Frontend interaction and language support](frontend/README.md)
- [Render deployment](docs/render-deployment.md)
- Module guides: [Middleware](middleware/README.md) · [MCP](MCP/README.md) · [Mock backends](mock_backends/README.md)

## Demo scope

Ponte is a local and hosted prototype using mock services. It does not connect to real government, medical, or welfare systems, or perform real identity verification, diagnosis, payment, referrals, or service submissions. Accounts, appointments, activities, and stored records are simulated. Do not enter real personal or medical information.

Users should be able to see the progress, understand the arrangement, and retain control over approval, changes, and cancellation.
