[繁體中文](README.md) | [English](README.en.md)

<div align="center">
  <img src="background.png" alt="聆澳 Ponte — 聆聽澳門，連結每一段故事" width="100%" />
</div>

<div align="center">
  <h1>Ponte</h1>
  <p><strong>讓長者以自然語言，安心辦理公共服務。</strong></p>
  <p>
    <a href="https://ponte-8k6h.onrender.com/">🌐 線上體驗</a> •
    <a href="docs/PonteArch.md">📐 系統架構</a> •
    <a href="docs/render-deployment.md">🚀 部署說明</a>
  </p>
</div>

Ponte 是一個以粵語與繁體中文為核心的公共服務 AI 助理原型。使用者可以用語音或文字表達需要，由 Ponte 透過受控工作流協調醫療、一戶通與社會福利等模擬服務。任務卡呈現處理進度、可選方案及待確認操作；介面亦可切換繁體中文與英文。

> **Live Demo:** [https://ponte-8k6h.onrender.com/](https://ponte-8k6h.onrender.com/)

## 技術棧 (Tech Stack)

| 層級 | 技術 |
| --- | --- |
| **Backend / Middleware** | Python 3.13+, 標準庫 HTTP Server |
| **AI / Agent Protocol** | Model Context Protocol (MCP), OpenAI-compatible LLM API |
| **Frontend** | Vanilla JS, Web Speech API |
| **Infrastructure** | Docker, JSON-RPC, Render |

## 為何是 Ponte？

公共服務不應要求長者先知道該用哪個平台、填哪份表格或記住哪個部門。Ponte 把複雜的服務入口轉化為一段容易理解、能追蹤進度的對話流程，讓使用者核對安排、修改要求或停止操作。

| 使用者體驗 (User Experience) | 設計與控制機制 (Design and Controls) |
| --- | --- |
| **多模態輸入** — 文字 / 語音 | 前端支援大字體、高對比與語音報讀；語音及文字需求共用互動入口，正式提交另需明確確認。 |
| **狀態可視化** — 即時進度追蹤 | 採用獨立任務卡（Task Cards）追蹤步驟、結果與可執行的下一步。 |
| **人機協作確認** — Human-in-the-loop | 涉及狀態變更的關鍵操作，強制要求使用者明確確認（Explicit Confirmation）。 |
| **受控工具呼叫** — 統一服務入口 | Middleware 透過預定義的 MCP 工具與標準化工作流封裝底層邏輯。 |

## 可體驗的服務

| 服務 | 說明 |
| --- | --- |
| **醫療預約查詢** | 讀取模擬的覆診資料，顯示服務、日期、時間、地點和狀態。 |
| **醫療服務預約** | 選擇服務與日期範圍，查看可選時段，確認後建立模擬預約。 |
| **現金分享計劃** | 查詢模擬的一戶通計劃摘要。 |
| **長者文娛活動** | 啟用 agent 後，可透過查詢工具搜尋模擬活動。 |

可以從以下需求開始：

```text
我想查詢自己的醫療預約
我想預約醫療服務
我想查現金分享計劃
```

介面頂部的「繁中／EN」可切換顯示及互動語言。英文文字輸入、服務回覆及任務卡共用同一互動與確認流程，例如 `I would like to see my medical appointments.` 或 `I would like to book a medical appointment.`。語音辨識及朗讀依賴瀏覽器或已設定的語音服務，實際可用聲線因環境而異。

## 架構一覽 (Architecture)

```text
瀏覽器（文字／語音、任務工作區）
                │ HTTP
                ▼
Frontend ──► Middleware（意圖辨識、流程、確認、任務狀態）
                │ stdio JSON-RPC
                ▼
        MCP（固定工具註冊表與 REST adapter）
                │ HTTP
                ▼
Mock Backends（醫療／一戶通／社會福利）
```

LLM 負責理解需求、提出下一步並解釋結果；middleware 管理任務狀態、工具權限及確認規則。預設使用既有工作流，啟用 agent 後，模型可在相同互動入口迭代查詢工具並讀取結果。

建立預約前，server 會驗證服務、時段及必要條件，發出綁定提案的確認操作。文字「yes」或「OK」不會批准提交；需求改變會撤回待確認提案。有效批准後，server 使用 idempotency key 執行掛號，核實回執後才回報成功。具體流程及限制見 [Agent 執行架構](docs/AGENT_EXECUTION.md)。

## 快速開始 (Quick Start)

### 環境需求 (Prerequisites)

- Python 3.13+
- 現代瀏覽器（如需使用語音，請允許麥克風權限）
- 無需額外安裝前端或 Python 依賴套件

首次使用時，在專案根目錄複製設定範本；已有 `.env` 則保留原設定：

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

啟動完整服務堆疊（Stack）：

```bash
python scripts/run_stack.py
```

當終端機輸出 `Ponte stack is ready.` 後，開啟輸出的 Frontend URL（預設為 `http://127.0.0.1:5173/`）。按 `Ctrl-C` 即可停止整個服務堆疊。

### 使用 Docker Compose（可選）

```bash
docker compose up --build
```

啟動後，請前往 [http://localhost:5173](http://localhost:5173)。

## 設定 LLM (Configuration)

預設工作流在未設定 LLM 時使用內建關鍵字辨識。要啟用多輪 agent，請在本機 `.env` 設定下列欄位，並將範例值換成你的模型服務設定，再執行相同的啟動指令：

```dotenv
PONTE_AGENT_ENABLED=true
PONTE_LLM_API_URL=https://your-provider.example/v1/chat/completions
PONTE_LLM_API_KEY=your-api-key
PONTE_LLM_MODEL=your-model-id
```

`PONTE_AGENT_ENABLED` 預設為 `false`。啟用後需要完整模型設定；模型服務出錯時會暫停處理，不會自動切換執行模式。目前 agent 的寫入範圍限於經驗證的醫療預約建立。對話、待確認提案及重播紀錄保存在單一程序記憶體，服務重啟後不會恢復。

**任務復原模型（Task Recovery LLM）：**

系統另備有一組獨立的 `PONTE_TASK_RECOVERY_LLM_*` 設定。此模型僅接收經清理的後端／工具回傳結果，專門用於產生任務復原建議。

> ⚠️ **請勿將 API Key 等敏感設定提交至版本控制系統。** 完整環境變數與行為規範請參閱 [Middleware README](middleware/README.md)。

## 測試與驗證 (Testing)

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s MCP/tests -v
python -m unittest discover -s middleware/tests -v
python -m compileall -q MCP middleware mock_backends frontend scripts tests
```

英文互動與 agent 的整合測試使用本機模擬服務，不需要付費模型 API key：

```bash
python -m unittest tests.test_english_interactions tests.test_agent_full_stack -v
```

完整驗證紀錄及執行／日誌細節見 [Agent 執行文件](docs/AGENT_EXECUTION.md)。

前端靜態檢查：

```bash
python -m unittest tests.test_frontend_static -v
node --check frontend/app.js
node --check frontend/interaction-view.js
```

## 專案導覽 (Project Structure)

| 目錄／檔案 | 用途 |
| --- | --- |
| [`frontend/`](frontend/) | 無需建置工具的語音優先網頁介面與 middleware client。 |
| [`middleware/`](middleware/) | 互動控制器、workflow、確認機制、session 和 MCP process 管理。 |
| [`MCP/`](MCP/) | 固定的工具註冊表、stdio JSON-RPC server 和 REST adapter。 |
| [`mock_backends/`](mock_backends/) | 醫療、一戶通及社會福利的模擬服務。 |
| [`database/`](database/) | 本機 Demo 的 JSON Lines 模擬資料；執行時產生的資料不應提交至版本控制。 |
| [`scripts/run_stack.py`](scripts/run_stack.py) | 一鍵啟動 backend、middleware、MCP 和 frontend 的本機 runner。 |
| [`render.yaml`](render.yaml) | Render 單容器部署 Blueprint。 |

**深入閱讀：**

- [系統架構與設計原則](docs/PonteArch.md)
- [Ponte 產品定位](docs/Ponte公共服務平台.md)
- [Agent 執行流程、驗證紀錄與限制](docs/AGENT_EXECUTION.md)
- [前端互動與語言支援](frontend/README.md)
- [Render 部署指南](docs/render-deployment.md)
- 模組專屬文件：[Frontend](frontend/README.md) · [Middleware](middleware/README.md) · [MCP](MCP/README.md) · [Mock Backends](mock_backends/README.md)

## 免責聲明 (Disclaimer)

Ponte 僅作為展示用途的本機／雲端原型，**不會**連接真實的政府、醫療或社福系統，亦不執行真實的身份驗證、診斷、付款、轉介或服務提交。系統中的所有帳戶、預約、活動及持久化資料皆為 **Mock Data**；請勿輸入真實個人或醫療資料。

即使在 Demo 中，涉及變更的流程仍需明確確認。此設計旨在實踐 Ponte 的核心治理原則：

> **讓使用者看得見進度、聽得懂安排，並保有確認、修正與停止操作的權利。**
