# Ponte 第二輪 Demo：啟動與驗證

此輪已實作單一 booking task 內的草稿、查詢、撞期判定、返回重查、正式確認和批准執行。模型模式為 `scripted` 時，只有模型決策是可重現腳本；工具仍經 HTTP → ExecutionPipeline → MCP → mock backend。

## 啟動（PowerShell，repository 根目錄）

使用全新隔離資料目錄；不要指向現有使用中的 dataset。

```powershell
$demoPython = 'C:/Users/steph/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$demoData = Join-Path (Get-Location) ('.demo-round2-' + [guid]::NewGuid().ToString('N'))
& $demoPython -m scripts.run_stack --demo-agent scripted --data-dir $demoData
```

打開終端顯示的 frontend URL（預設 `http://127.0.0.1:5173/?middleware=http://127.0.0.1:8090`）。七個步驟：

1. 「幫我預約下星期二的心臟科」：P1 14:00 草稿，沒有批准按鈕。
2. 「下午三點後先得」：P2 15:30 草稿，intent revision 更新。
3. 「等等，我之前有冇其他預約？」：同一 task 查詢；保留 P2；撤銷舊卡。
4. 「咁會唔會撞時間？」：顯示 server 的 clear／overlap／unknown 及查詢時間。
5. 「好，返去頭先個預約」：重新搜尋 exact P2，不延長草稿期限。
6. 「就15:30嗰個」：只有資料完整、新鮮且不撞期時，建立正式確認卡。
7. 點「確認掛號」：此時才提交；再次送相同 action 回傳同一收據。

另開 PowerShell 可自動走完七步：

```powershell
& $demoPython -m scripts.demo_cardiology --middleware-url http://127.0.0.1:8090
```

每次完整重演使用新 dataset；先前成功掛號已佔用該 slot。啟動腳本不覆寫已有 appointments。手動演示預設隔離病人可沒有已有預約；測試另有保留既有 15:00–15:30 預約的 boundary fixture，以及 15:15–15:45 overlap fixture。

## 增量測試

```powershell
& $demoPython -m unittest middleware.tests.test_demo_medical_workflow middleware.tests.test_demo_model middleware.tests.test_demo_openai_payload middleware.tests.test_demo_conflicts middleware.tests.test_interaction_delivery middleware.tests.test_interaction_contracts -q
& $demoPython -m unittest tests.test_demo_agent_e2e tests.test_demo_round2_e2e -q
node --test tests/frontend_demo_console.test.mjs
```

HTTP/MCP 測試自建隔離 dataset，包含七 turn（Turn 7 前零 registration）、完整 tool history pairing、邊界與重疊、缺 end／時區、查詢失敗、過期／被佔用 P2、舊卡、freshness 重查後再批准、duplicate approve、query/approve lock ordering，以及原 examination／cash／voice 入口回歸。純撞期測試另涵蓋跨午夜、不同 UTC offset、取消及未知狀態。讀取分頁不完整時不得判為 clear。

## 證據與限制

- 本輪單元／projection／contract 測試：46 項通過。
- HTTP → MCP → backend：39 項通過（11 本輪 + 28 既有安全／相容性）；完整 scripted 七 turn rehearsal 通過。
- Frontend console：11 項通過。
- 真實模型 smoke：2026-10-13 23:18（Asia/Singapore）以 gpt-4.1-mini 通過完整七 turn，包含同一查詢快照、resume 重查、兩個 DRAFT_ONLY 配對及最後一次掛號，重複批准回傳同一收據。證據：`.demo-data-real-smoke-a902da70ce08/real-smoke-evidence.json`。初次測試發現模型會在控制回合提出工具，以及沿用舊 revision slots；已修正控制回合 tool_choice=none、最新 server state 指引順序並補強逐 turn 斷言。這是一次 smoke 通過，不代表模型在各種措辭下穩定；較早失敗的隔離資料亦保留供查核。
- 仍為單程序記憶體 demo。重啟不保留 pending task／approval；沒有 durable runtime、SQLite、OAuth、取消／改期或撞期 override。
- 成功只以 backend receipt 核實。timeout／receipt mismatch 保留 unknown-outcome 病人封鎖，不自動重試掛號。
- 只比較預約時間區間，不估算交通、候診或準備時間。
