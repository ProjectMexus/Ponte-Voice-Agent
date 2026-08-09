# Ponte Frontend

這是 Ponte 的零 build dependency 前端。它只負責畫面、文字輸入、瀏覽器語音能力及 middleware HTTP client；不直接呼叫 MCP 或 mock backend。

## 啟動前端

```bash
python -m frontend.server --host 127.0.0.1 --port 5173
```

開啟 [http://127.0.0.1:5173](http://127.0.0.1:5173)。前端預設連接 `http://127.0.0.1:8090` 的 middleware；middleware 尚未啟動時，頁面仍然可以載入，並會顯示可理解的連線錯誤，文字輸入仍保持可用。

完整 stack runner 會列出可直接開啟的 URL；若 middleware 使用其他 port，也可以使用 query override：

```text
http://127.0.0.1:15173/?middleware=http://127.0.0.1:18090
```

如需更換 middleware 位置，可在載入 `app.js` 前設定：

```html
<script>
  window.PONTE_MIDDLEWARE_URL = "http://127.0.0.1:8090";
</script>
```

## 已實現的互動

- 大字、高對比、適合長者閱讀的對話與服務工作區。
- 文字輸入及快捷需求按鈕。
- 支援 `SpeechRecognition` / `webkitSpeechRecognition` 時，以 `zh-HK` 取得粵語 transcript；transcript 會先回填文字框，使用者按送出後才傳給 middleware。
- 對話框保留助手的書面語 `assistant_message`；支援 `speechSynthesis` 時，會以粵語口語 `assistant_speech_message` 自動朗讀，預設開啟。按「自動朗讀：開／關」即可切換；關閉時會立即停止目前朗讀。瀏覽器不支援語音時，文字對話及其他操作仍然可用。
- Middleware response 會以獨立任務卡顯示；進行中的任務展開顯示 steps、服務資料和下一步操作，完成、取消或不可恢復失敗的任務會收合但可重新展開。已完成或已處理的步驟會自動收合，目前步驟和需要 recovery 的步驟保持展開；重試後的同名步驟會各自保留，使用者可以重新展開舊步驟查看當時的 user-safe 摘要。可恢復的 backend error（例如缺少資料、暫時 timeout 或目前沒有可預約時段）會留在同一張展開的任務卡，顯示原因、需要補充的資料和 retry／替代方案；按下方案後仍沿用同一 task。醫療查詢會顯示每筆預約的服務、日期、時間、地點和狀態；一般使用者不會看到 API 工具名稱、請求編號或原始 backend JSON。Intent LLM 只負責理解使用者需求，Task Recovery LLM 只負責理解 backend 結果並產生下一步方案；兩者分開管理。未來可讓文字／語音確認繼續同一任務。
- 可用文字輸入測試自然語言 workflow：`我想查詢自己的醫療預約` 是只讀查詢，會建立一張查詢任務卡；`我想預約醫療服務` 會建立另一張進行中的任務卡，讓使用者選擇服務和日期範圍，展示可預約時段，再經確認建立 mock 預約。預約後再次輸入前一個查詢即可建立新的查詢任務並讀回記錄；另外也可測試 `我想查現金分享計劃` 和 `我想找長者文娛活動`。
- 開發者整合測試仍保留固定 MCP tool 的 `confirm_tool` 確認 action 和既有 `sendAction` contract；這些技術細節不會出現在一般服務工作區。
- middleware 連線錯誤不會清空既有對話或停用文字輸入。

## 驗證

```bash
python -m unittest tests.test_frontend_static -v
node --check frontend/app.js
node --check frontend/mcp-client.js
node --check frontend/interaction-view.js
node --check frontend/speech.js
```

完整驗收流程請參考 repo 根目錄的 `README.md`：輸入上述任一需求並送出，畫面應顯示 middleware 已連線、對應進度，以及可讀的服務資料摘要。


## 醫療預約 UI demo

醫療預約為主要情境。點選情境只會預覽需求，按「送出」才開始。
1. 點「醫療預約」或輸入需求，送出後才顯示 agent 回傳的服務與可用時段。
2. 在確認頁核對服務、日期、時間、地點；可修改資料或取消。
3. 確認後查看回執，下載 HTML 或列印。
4. 切換「我的預約」並送出，讀回剛建立的模擬預約。
5. 「現金分享」只讀取資格與發放資料。進行中切換情境會要求重新開始。

對話與服務足跡持續保留；「重新開始」清除本次對話，但不刪除已保存的模擬預約。
朗讀按鈕可立即靜音；繁中／EN 切換介面，服務內容沿用伺服器提供的文字。
手機版上下排列，可向下捲動選擇服務。文字流程不需要語音供應商設定。
新的資料目錄會產生翌日起三天的醫療時段，既有目錄保留原本資料。

```bash
python scripts/run_stack.py --data-dir .demo-data-fresh
PONTE_LOG_LEVEL=INFO python scripts/run_stack.py
PONTE_LOG_LEVEL=DEBUG python scripts/run_stack.py
node --test tests/frontend_demo_console.test.mjs tests/frontend_workspace_behavior.test.mjs
```

PowerShell 可先設定 `$env:PONTE_LOG_LEVEL='INFO'` 再啟動。
請為新一輪展示選用未使用的 `--data-dir` 名稱。所有預約均為本機模擬資料。

## Apple-inspired visual refinement

This branch keeps the existing conversation and service workflow, with neutral paper surfaces, a deliberate system font stack, subtle layered shadows, and one blue action color. Shared presentation tokens live at the top of `styles.css`. Interactive controls have at least 44px touch targets; reduced motion, keyboard focus, and receipt printing remain supported.

The layout stacks on phones. The service workspace stays hidden until the agent returns service content, recovery guidance, or a receipt. The service trail appears only after an actual service event. Conversation-only turns preserve existing results; an explicit workspace clear or session reset closes the panel. There is no preset booking introduction or forecast of future steps. Errors remain visible outside the workspace, including before any service starts.

Run an isolated preview from this worktree:

```bash
python scripts/run_stack.py --backend-port 18185 --middleware-port 18195 --frontend-port 16175 --data-dir .demo-data-agentic-20261014 --demo-agent scripted
```

Open `http://127.0.0.1:16175/?middleware=http://127.0.0.1:18195`.

The bounded cardiology agent now projects actual service events and current time constraints. The trail distinguishes lookups, replacement drafts, clarification, revalidation, explicit approval and verified receipts. See `docs/demo/Cardiology_Demo.md` for the six-capability walkthrough and evidence limits.

The simplified interface uses one service heading and one task state. Secondary connection details and processing history use native expandable sections. The workspace remains response-driven; receipt access, server-issued actions and confirmation requirements are preserved.

Quick request suggestions live inside the conversation above the composer. They prefill a request without sending or clearing the current task, so an appointment lookup can interrupt and resume a draft. The right column contains only response-driven service content and its processing history.
