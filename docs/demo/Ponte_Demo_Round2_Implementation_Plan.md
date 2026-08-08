# Ponte 第二輪 Demo Implementation Plan

本輪以已完成 demo 為基線，實作 [第二輪 Scope](Ponte_Demo_Round2_Scope.md) 的七回合對話。只新增任務內查詢、恢復、撞期判定和正式確認的區別；保留上一輪既有安全邊界和相容流程。以下為待實作計劃，不代表功能已完成。

## 交付順序和預估

| Phase | 交付 | 估計人日 |
|---|---|---:|
| 1 | Candidate、approval 和 inquiry 的最小狀態模型 | 1–1.5 |
| 2 | 模型決策、預約查詢和完整 tool history | 1–1.5 |
| 3 | 撞期判定與 P2 resume revalidation | 1–1.5 |
| 4 | 正式確認和現有畫面整合 | 0.5–1 |
| 5 | 七 turn E2E、分支驗收和展示腳本 | 1.5–2.5 |

合計約 5–8 人日，包含測試與修改；假設沿用目前可工作的上一輪 adapter，無新基礎設施。這是規劃估算，模型語義穩定性和既有 adapter 的修改幅度會影響進度。每階段只執行與增量變更相關的測試；不重新做上一輪 repository architecture audit。

## Phase 1 保留同一任務的最小狀態

修改 `middleware/demo_medical_workflow.py`，在現有 session-owned state 中增加以下欄位；可用同檔的 dataclasses，毋須建立另一個 manager、store 或服務。

```text
booking_task_id                       原 task identity
booking_intent_revision               只有有效 constraints 改變時增加
phase                                 planning | inquiry | resume_check |
                                      awaiting_selection | awaiting_approval |
                                      executing | completed | needs_recovery
candidate                             immutable P1/P2/P3，或空
candidate_validation                  slot snapshot、verified_at、candidate_id
approval                              A2、actions、generation、expiry、結果，或空
appointments_snapshot                 records、fetched_at、patient、request_id
conflict_result                       clear | overlap | unknown，加來源 metadata
dialogue_generation                   對話／action 過時檢查，與 intent revision 分開
```

候選保留 exact input、slot identity/time/location、intent revision、digest、created/expiry。Approval 綁 candidate ID、task/session、intent revision、digest、generation 和允許的 decision。正式 action payload 使用既有 `confirmation_decision` 事件；`confirmation_id` 指向 approval ID，另附 candidate metadata。不得接受從 client 傳來的 body 覆寫 frozen input。

在 `DemoMedicalWorkflow` 實作以下小方法；名稱為計劃中的 private interfaces，可配合既有命名整合，但責任不可拆成另一套 runtime：

```python
_suspend_for_inquiry(state, *, reason, logs) -> None
_invalidate_approval(state, *, reason, logs) -> None
_resume_booking(state, *, logs) -> None
_issue_confirmation(state, *, logs) -> None
```

`_suspend_for_inquiry` 撤銷尚未執行的 approval/actions，保留候選與 intent revision；若有 open booking tool call，關閉為 `DEFERRED_FOR_QUERY`。`_resume_booking` 進入 revalidation，不發批准。`_issue_confirmation` 只接受當前有效候選、fresh verification 和 clear conflict。

沿用完整 turn 的 per-session lock。`dialogue_generation` 和持久存在於該 session 的 issued action records 防止舊 callback；不引入 CAS／lease。若 code 已採用同步鎖，維持它，不為此功能新增平行背景查詢。

測試 R01：Turn 2 增加 intent revision；Turn 3–6 不增加。R02：暫停／恢復 task ID 不變。R03：舊 approval 及其 action 在 inquiry 立刻失效；P2 仍存在。R04：intent change 才替換候選；inquiry 不重新建立 booking task。Phase 1 不呼叫 booking tool。

## Phase 2 模型決策和預約查詢

修改 `middleware/demo_model.py` 和 `middleware/demo_medical_workflow.py`；更新對應 scripted client 及模型 payload tests。Agent tool allowlist 加上 `medical.get_my_appointments`；其模型 input 為 `{}`，server context 使用同一病人。沿用現有 `ExecutionPipeline`，不新增 MCP registry／backend endpoint。

讓模型可提出 `query_appointments`、`answer_question`、`resume_booking`、`select_slot`、`update_constraints` 或 `clarify` 的語義；可以擴充現有 strict decision schema，由 workflow 驗證。若沿用 native tools，查詢以真實 `medical.get_my_appointments` tool call 表達；其餘控制意圖使用 schema 中的非工具決策。不要另起一個通用 routing agent，也不要靠固定 turn number 推進。

`update_constraints` 只能修改 server allowlist 的 booking fields；inquiry、answer 和 resume 不可透過附加 arguments 變更科室／日期／時間。`select_slot` 必須指向 server 曾提供且重新驗證的候選；多工具回應維持整體拒絕。對模糊的「返去」在只有一個 suspended booking 時可恢復；沒有可恢復 task 時澄清，不自建新掛號。

新增或整合：

```python
_query_appointments(state, *, call_id, logs) -> None
_record_deferred_call(state, *, reason: str) -> None
```

查詢結果保存 records 和來源 timestamp/request ID，正常 assistant-call／tool-result 配對。不得在 unresolved booking assistant call 後直接插入 query prompt。若原 planning call 已以 `SUPERSEDED` 或 `DEFERRED_FOR_QUERY` 結束，之後 receipt 使用新的 execution call ID，不能回填第二個 tool result。Resume 的 server validation read 也記錄為獨立的配對工具交換。

測試 R05：Turn 3 真正調用 MCP 的 `medical.get_my_appointments` 且零掛號。R06：Turn 4 使用相同 candidate 和查詢 facts，snapshot fresh 時不重查。R07：query error 保留 P2 並回答無法核實，不產生「沒有其他預約」的假事實。R08：tool history 全部唯一配對且在每次 model call 前無 dangling call。R09：模型不同措辭仍能提出 query/resume/select；非法 phase decision、額外 mutation tool 或外來 patient/context 被拒絕。

## Phase 3 撞期和恢復時重新驗證

小型純函式放在 `middleware/demo_medical_workflow.py`，避免為一個規則新增 domain service。需要時沿用既有日期解析 helper，使用 aware datetimes。

```python
evaluate_conflicts(candidate, appointments_snapshot) -> ConflictResult
validate_candidate(candidate, returned_slots, constraints, *, now) -> ValidationResult
```

`evaluate_conflicts` 使用 `[start,end)` 重疊規則，明確處理 timezone、有效狀態、取消紀錄和缺失欄位。回傳具體 conflicting appointment IDs／區間或 unknown reason；不要只回 boolean。模型只解釋此結果，不自行決定時間算術。第一個成功展示 fixture 使用既有 15:00–15:30、候選 15:30–15:45，回答端點相接不撞期；另備 15:15–15:45 的 overlap fixture。

`_resume_booking` 無論 cached availability 多新，都重新調用 `medical.search_registration_slots`，使用原科室、日期及合法搜尋欄位；after-3 constraint 仍由 runtime 用返回的 aware `start` 過濾。匹配 exact P2 slot 及所有確認內容，不可只找「另一個 15:30」。

候選期限 300 秒不因詢問而刷新；過期或內容／availability 改變則 invalidate P2，建立新的 P3 草稿，再要求選擇。Slot validation 和 appointments snapshot 的 freshness 上限均為 60 秒；appointments 過舊則重新 `get_my_appointments` 後重算。只有兩者有效且 conflict clear 才到 awaiting_selection。

測試 R10：clear、真重疊、相鄰端點、跨午夜／不同 offset 表達同一瞬間、取消紀錄、缺少 end／timezone、未知狀態。R11：Turn 5 調用 search，保留同一 task、constraints 和仍有效的 P2。R12：P2 過期／slot 被佔用／slot details 改變 → 不沿用授權，提出 P3 或恢復選擇。R13：freshness 超限重新讀取；已知 overlap/unknown 不發 approval。R14：查詢或 revalidation error 不清空候選、不聲稱已掛號。

## Phase 4 正式確認與畫面

修改 `middleware/interaction_delivery.py` 的 composer/projector，及必要的 `frontend/interaction-view.js`／`frontend/demo-console.js`。`frontend/app.js` 只在 action forwarding 或舊 response 防護需要時調整。保留目前布局、文字輸入、語音流程、receipt drawer 和 `/api/interactions`。

草稿畫面顯示 P1/P2 建議和「尚未確認／未掛號」，沒有可執行 Approve。Inquiry 畫面同時保留原 booking 的摘要和既有預約列表，提供 server-issued「返回原預約」action；action 可送 `recovery_action` 或現有允許的 opaque event，由 server 解讀，不能由 frontend 重組 booking input。細節採現有事件機制，不另開新 endpoint。

Turn 6 建立 A2 時，確認卡顯示病人 demo identity、科室、日期、時間、地點，以及已查詢的撞期結果／資料時間，並明示「點擊批准才提交」。任何 inquiry/change 使舊 action 失效，畫面移除或停用舊按鈕；server 的驗證才是最後權威。

Approval handler 在 per-session lock 內驗證 phase、issued action、candidate、revision、digest、expiry 和 freshness。若 freshness 過期，撤銷 A2，重新查驗並回新卡要求再按一次，不透明地沿用舊批准。正確批准才調用既有 `medical.create_registration` 路徑，保持 proposal/candidate 綁定的穩定 idempotency key。重複 A2 回傳已記錄結果；與執行中 side query 的排序遵守上一輪鎖的行為。

Receipt 成功驗證沿用上一輪；新增任何 candidate／approval metadata 只強化關聯，不改成相信 LLM。若 response mismatch 或 timeout，走 unknown outcome／禁止新掛號，不自動重試。

測試 R15：Turn 1–5 無 Approve action，Turn 6 有正式 A2 且零 booking。R16：Turn 7 必須提交 exact P2；雙擊最多一次。R17：A1、被 suspension 撤銷的 A2、另一 task/action/revision/digest 一律不執行。R18：查詢卡和確認卡交替時沒有可用舊 action，frontend opaque event 保留 binding metadata。R19：query/approve 競爭以鎖的先後決定；已開始 booking 不能被查詢假裝取消。

## Phase 5 端到端驗收和交付

擴充 `middleware/tests/test_demo_medical_workflow.py`、`test_demo_model.py`、`test_demo_openai_payload.py`、`tests/test_demo_agent_e2e.py` 及相關 frontend behavior tests。純 conflict tests 可放 `middleware/tests/test_demo_conflicts.py`。更新 `scripts/demo_cardiology.py` 的七 turn 展示和新增 fixture；如既有 real-model smoke 支援此能力，擴充 `scripts/smoke_cardiology_real.py`。不刪除上一輪測試或改弱安全斷言。上一輪若有「提出 P1 便直接帶 Approve」的 demo assertion，明確更新成 draft→使用者選定→正式卡，保留原本無批准不執行、失效拒絕、重複提交及 receipt 驗證斷言；原 legacy examination/cash 路徑維持其既有互動。

| 驗收 | 必須觀察到的證據 |
|---|---|
| R20 完整主線 | 真實 HTTP→MCP→backend；工具 trace 包含 department/search、query、resume search、最後一次 registration；Turn 7 前 registration=0，最後 receipt 匹配 15:30。 |
| R21 恢復分支 | P2 在查詢中過期或被佔用；恢復後不直接執行、不靜默換 slot，顯示 P3／選擇提示。 |
| R22 Side query 分支 | query failure、重複追問、在 query 中再修改 constraints、未 suspended 時 resume，均不遺失任務或錯誤沿用 approval。 |
| R23 執行不確定 | timeout 或 receipt 不匹配 → 未核實結果及禁止新掛號；不因返回原任務而解除此阻擋。 |
| R24 相容性 | 上一輪 cardiology、原 examination/query/cash flows、文字和既有 voice transcript 入口、confirmation/receipt projections 維持正確。 |

示範資料用隔離 dataset；不改寫使用中的 appointments。Scripted client 只負責可重現模型決策，所有工具呼叫仍走真實 pipeline/MCP/backend。若有可用 credentials 再跑同一七 turn 的 real-model smoke，回報模型決策是否穩定；沒有 credentials 時清楚標示未驗證 real-model，不能把 scripted evidence 當模型理解能力證明。

交付包含增量程式、測試結果、七 turn 可重現啟動／展示步驟和已知 demo 限制。前兩份完整架構 SVG 不需要為本輪重繪；本輪不擴大到 durable workflow 或通用多任務 runtime。

## Capability 對應

| 能力 | 預計實作位置 | 驗收 |
|---|---|---|
| P1→constraints→P2 | demo workflow/model，沿用上一輪 | R01/R04/R20 |
| 任務中途 read-only query | demo workflow/model + existing MCP get-my tool | R05–R09/R22 |
| 查詢結果與候選聯合判斷 | conflict pure function + composer | R06/R10/R13 |
| 暫停與同一 task 恢復 | memory state/private methods | R02/R03/R11/R12 |
| Resume availability/expiry驗證 | demo workflow → existing search tool | R11–R14/R21 |
| 草稿與正式批准分離 | candidate/approval state + delivery/actions | R15/R17/R18 |
| Exact authorized execution / receipt | existing pipeline/backend + approval validation | R16/R19/R20/R23 |
| 原有應用保留 | canonical delivery/voice/frontend regression | R24 |

本輪完成後，Ponte 可以展示在一個真實服務任務中插入查詢、運用上下文、返回原意圖及安全確認。它仍是受監督、單程序、記憶體狀態的 mock demo。
