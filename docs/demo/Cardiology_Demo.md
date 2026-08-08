# 心臟科 agent demo

本次實作依據 [Active Demo Scope](../architecture/Ponte_Demo_Scope.md)。保留現有 UI、canonical `/api/interactions`、語音 adapter、InteractionCore、ExecutionPipeline、MCP stdio 與 JSON mock backend。架構決策、舊 implementation plan 及兩張 SVG 屬暫緩項目。

## 啟動

在 repository 根目錄開啟 PowerShell，使用現有 Python 3：

```powershell
python scripts/run_stack.py --demo-agent scripted --data-dir .demo-data-cardiology
```

開啟 [Ponte demo](http://127.0.0.1:5173/?middleware=http://127.0.0.1:8090)。`scripted` 是可重現的模型決策替身；HTTP、MCP subprocess 與 backend 掛號均實際執行。畫面連線狀態及 runner 都明示「腳本模型示範」。預設 `off` 保留原有流程；啟用 demo 且未指定目錄時，runner 使用 `.demo-data-cardiology`，不使用原有 `database`。

Backend 以 service clock 的嚴格下一個星期二建立獨立、帶日期 ID 的心臟科 14:00／15:30 庫存，每時段一名，地點第一門診。啟動／搜尋不會重寫既有 bookings。固定測試日是 2026-10-13，下一個星期二是 2026-10-20；live 日期隨 clock。

## 展示故事

1. 輸入「心臟科下週二下午」。agent 選擇 list departments、search slots、create registration；最後一項只產生 P1，不提交。畫面顯示 14:00、日期、心臟科及第一門診。
2. 輸入「改為下午3點後」。原 P1 失效，原 assistant call 先收到 `SUPERSEDED` tool result，再加入新 user message。P2 顯示 15:30；仍未掛號。
3. 明確按「確認掛號」。伺服器驗證已發出的 action、session/task、intent revision、proposal ID、digest、expiry 與凍結參數，再以固定 proposal key 提交。
4. 畫面顯示 backend 的 `booked` 結果與 `MED-REG-*` 回執；重複確認回傳相同結果，不再掛號。文字或語音的「yes／確認」不能授權。

亦可在另一個終端對啟動中的 stack 演練相同故事（會真正建立一筆 mock 掛號）：

```powershell
python scripts/demo_cardiology.py
```

腳本會額外重播失效 P1、重複 P2，印出 mode 與實際 receipt。此時段只有一名；已完成後再演練應先查看紀錄，並使用另一個明確隔離的 demo 目錄。不要清除資料來隱藏失敗或不確定結果。

既有「我想預約醫療服務」、檢查預約、「我想查詢自己的醫療預約」及「我想查現金分享計劃」沿用原 workflow。進行中的 task 固定原 engine；可用「重新開始」建立新 session。語音轉錄進入同一 core，既有 STT/TTS 設定不變。

## Real model

設定本地 `.env` 或 shell 的 `PONTE_DEMO_LLM_API_URL`、`PONTE_DEMO_LLM_API_KEY`、`PONTE_DEMO_LLM_MODEL`，再使用 `--demo-agent real`。空值會依序使用既有 `PONTE_LLM_*`。模型每輪只能選一項 allowlisted tool，最多四個 decision；越界、多 tool、錯誤參數或無法驗證的成功宣稱會暫停。此路徑不會靜默切換至 scripted。

```powershell
python scripts/run_stack.py --demo-agent real --data-dir .demo-data-cardiology-real
```

本次環境未配置模型 credentials，因此驗證結果屬 scripted mode，未宣稱 real-model smoke 通過。

Real mode 只在模型連線邊界把三個既有 registry 名稱映射為合法 function name，例如 `medical.list_departments` → `medical_list_departments`；原始 call ID、內部 transcript、proposal 與 MCP dispatch 仍保留既有 tool contract。[OpenAI API 規格](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)限制 function name 使用英文字母、數字、底線及連字號。別名映射以 scripted transport 測試驗證，不能替代 real-model smoke。

## 驗證與保證範圍

```powershell
python -m unittest tests.test_demo_agent_e2e -v
python -m unittest discover -s tests -v
python -m unittest discover -s MCP/tests -v
python -m unittest discover -s middleware/tests -v
node --test tests/frontend_demo_console.test.mjs tests/frontend_workspace_behavior.test.mjs tests/frontend_voice_cancel.test.mjs
```

E2E 使用固定 clock、真實 middleware HTTP → MCP stdio → backend HTTP。Lost-reply timeout 與損壞 receipt 測試在真實 backend 回應之後注入故障，以確認已提交但回覆丟失也不會再次掛號。結果逐項比對病人、科室、slot、timezone-aware start、`booked`、completed backend task、receipt 類型與 ID。

每 session 整個 turn 上鎖；同一 demo 病人的寫入檢查、提交與結果分類也串行執行，避免一個 session 的不明結果封鎖與另一筆提交競爭。Medical backend 在同一程序內把 idempotency lookup、capacity、booking、replay save 上鎖。若批准先取得鎖並提交，稍後的修改不能取消該交易。瀏覽器中止等待也不會取消 server execution。

掛號回覆 timeout、transport/protocol 錯誤或不能驗證的結果會顯示「結果需要查核」並封鎖該 demo 病人在此程序的新掛號。沒有自動 write retry、沒有更換 key。操作員需查看資料目錄下 `medical/appointments.txt`、`tasks.txt` 與 `idempotency.txt`，人工確認後才決定下一步；重新啟動不代表沒有掛號，也不是恢復方法。

只保證單程序、受監督的本地 mock demo。Pending task、transcript、proposal 和 approval 在記憶體中，重啟即失效；JSON 寫入不具 crash atomicity。未實作 durable runtime、SQLite、lease/CAS、跨程序併發、真實病人身份驗證、OAuth、獨立 backend approval authority、跨 domain mutation 或取消／改期。

## 本次執行證據（2026-10-13）

- 143 個 repository tests 通過，包含 28 個 scripted HTTP→MCP→backend acceptance cases。
- 183 個 middleware tests、21 個 MCP tests、21 個 frontend Node tests 通過，共 368 個。
- 瀏覽器以 `.demo-data-cardiology-rehearsal` 走通 P1 14:00 → P2 15:30 → 明確確認，回執 `MED-REG-0001`，`APT-0001`／backend `TASK-0001`，`booked`，2026-10-20T15:30:00+08:00。
- `scripts/demo_cardiology.py` 以另一個隔離目錄 `.demo-data-cardiology-script` 走通同一故事，失效 P1 被拒、重複 P2 回傳同一回執，只有一次掛號。
- 最終版本以 `.demo-data-cardiology-final` 再次走通瀏覽器故事；JSON backend 記錄一筆 15:30 `booked`、一筆 completed task 及一筆 idempotency replay。瀏覽器保持回執畫面可查看，測試及演練目錄沒有刪除。
- 目前執行環境需要允許本機 subprocess 的 loopback HTTP；首次限制環境下 MCP 收到 `BACKEND_UNAVAILABLE`，允許本機測試連線後全數通過。這是執行環境限制，沒有用 fake transport 取代 HTTP/MCP。
- 沒有 model credentials，未執行 real-model smoke。
