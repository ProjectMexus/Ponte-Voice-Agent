# OpenAI 真實模型接線與啟動

本次驗證依據 [Ponte Demo Scope](../architecture/Ponte_Demo_Scope.md)，沿用現有 demo workflow、HTTP、MCP 與 JSON mock backend。

## 本機設定

在 repository 根目錄的 `.env` 設定以下項目，保留其他既有設定：

```ini
PONTE_DEMO_AGENT_MODE=real
PONTE_DEMO_LLM_API_URL=https://api.openai.com/v1/chat/completions
PONTE_DEMO_LLM_API_KEY=在本機填入自己的_API_key
PONTE_DEMO_LLM_MODEL=gpt-4.1-mini
```

Key 只放在本機；`.env` 已被 Git 忽略。Shell 中同名環境變數優先於 `.env`；修改後須重啟服務。本次沒有改寫已有 `.env`，已確認上述模式、網址、模型及 key 存在。

## 啟動 UI

在 PowerShell 執行。以下使用另一組 ports，並為每次演練建立新的資料目錄，保留之前的 bookings；若 ports 已被使用，請換一組。

```powershell
Set-Location 'C:/Users/steph/.codex/.chatgpt-projects/g-p-6acd21d69aa48191ba6ae60b5152a04c/ponte-demo-ui'
$ponteDemoData = '.demo-data-openai-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/run_stack.py --demo-agent real --backend-port 8180 --middleware-port 8190 --frontend-port 5273 --data-dir $ponteDemoData
```

開啟 <http://127.0.0.1:5273/?middleware=http://127.0.0.1:8190>，依序輸入「心臟科下週二下午」→「改為下午3點後」→按伺服器提供的「確認掛號」。P1 14:00 不提交；P2 15:30 須明確確認。文字或語音「確認」不會授權掛號。

也可在另一個終端執行以下腳本，代替 UI 完成同一流程，會建立一筆 mock booking。不要在已用完該時段的資料目錄重複演練：

```powershell
python scripts/demo_cardiology.py --middleware-url http://127.0.0.1:8190
```

## 獨立 real-model smoke

```powershell
python scripts/smoke_cardiology_real.py
```

此腳本會實際呼叫 OpenAI（使用 API 額度），自動配置可用的 backend/middleware ports，執行真實 HTTP → MCP subprocess → mock backend，完成後關閉自己啟動的服務。每次使用全新的 `.demo-data-real-smoke-*`，成功或失敗都保留資料；不操作其他服務或既有 bookings。缺少 key 時會明示「尚未驗證 real model」。

腳本檢查 P1 14:00 → 修改意圖 → P1 失效拒絕 → P2 15:30 → 明確確認 → 重複確認，並讀取獨立 backend 的 appointments/tasks 檔核對 `booked`、slot、日期、時間、病人、科室及 completed task。也檢查模型 HTTP payload 的 function 名稱與內部 transcript 的 call ID/result 配對，包含 `SUPERSEDED`。`real-smoke-evidence.json` 記錄模型決策及 mock booking 證據，不保存 API key 或 HTTP headers。

若出現不確定寫入結果，保留資料查核，不以重啟或刪除資料代替復原；詳細限制見 [demo 操作說明](Cardiology_Demo.md)。

## 工具名稱邊界

| 內部 MCP / registry 名稱 | OpenAI function 名稱 |
| --- | --- |
| `medical.list_departments` | `medical_list_departments` |
| `medical.search_registration_slots` | `medical_search_registration_slots` |
| `medical.create_registration` | `medical_create_registration` |

`RegistryToolNameClient` 只在 real model 邊界轉換工具定義、歷史 assistant calls、指定名稱的 `tool_choice` 與 system/developer prompt 的工具名稱；回覆轉回 MCP 名稱。Call ID、參數、工具數量及 tool results 保持原契約。未知名稱不被擅自映射成 allowlisted tool。Scripted client 仍使用原 MCP 名稱。對應 [OpenAI function 名稱規則](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。

真實模型初次演練發現中文 keyword 與多餘澄清會觸發暫停，已將 prompt 明確指定 `keyword="Cardiology"` 及有可用時段時先建立提案；保留嚴格參數驗證及按鈕批准要求。

## 2026-10-13 驗證證據

`gpt-4.1-mini` 真實模型 smoke 通過。日期 2026-10-20，P1 14:00 → P2 15:30，失效 P1 被拒，P2 明確確認及重複確認後只有一筆 booking：`APT-0001`，backend `TASK-0001` completed，`MED-REG-0001`，`booked`。

本機證據：`.demo-data-real-smoke-6964ff4f71f2/real-smoke-evidence.json`。先前未通過的隔離演練目錄也保留，沒有刪除或改寫既有資料。

最終回歸：repository 143 項（包含 scripted E2E 28 項）、middleware 186 項（包含模型邊界與 demo 單元測試 17 項）、MCP 21 項全部通過。Repository 首次執行的既有 backend logging 測試未捕捉到 `request_end`，單獨重跑與整體重跑均通過；沒有修改該測試或 logging 行為。

可重跑的測試：

```powershell
python -m unittest middleware.tests.test_demo_model middleware.tests.test_demo_openai_payload middleware.tests.test_demo_medical_workflow -q
python -m unittest tests.test_demo_agent_e2e -q
python -m unittest discover -s middleware/tests -q
python -m unittest discover -s MCP/tests -q
python -m unittest discover -s tests -q
```

需要環境允許 subprocess 與本機 loopback HTTP。Scripted 測試通過與 real-model smoke 分別記錄；scripted 成功不作為真實模型成功的證據。
