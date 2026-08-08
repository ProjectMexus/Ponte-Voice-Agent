# Ponte 第二輪 Demo Scope

本輪讓 agent 在同一個掛號任務中處理臨時查詢、回答撞期問題，再回到原先選擇，最後取得明確批准才執行。上一輪 demo 已完成，作為本輪基線；本文件是下一輪規格草案，不重新開啟上一輪工作，也不啟動實作。完整 durable architecture 維持 future work。

## 七個回合的驗收主線

| Turn | User | Agent 和 server 必須展示的能力 | 可執行掛號嗎 |
|---|---|---|---|
| 1 | 幫我預約下星期二的心臟科 | 調用 `medical.list_departments` 和 `medical.search_registration_slots`，提出 14:00 的 P1 草稿。畫面顯示日期、科室、時間和地點。 | 不可 |
| 2 | 下午三點後先得 | 更新原任務 constraints；P1 失效；重新搜尋或評估，提出 15:30 的 P2 草稿。 | 不可 |
| 3 | 等等，我之前有冇其他預約？ | 暫停掛號選擇，保留原 task、constraints 和 P2；調用 `medical.get_my_appointments`，展示目前病人的既有預約。 | 不可 |
| 4 | 咁會唔會撞時間？ | 結合 P2 的時間區間及 Turn 3 的結果回答；指出比較的日期、時間和資料時間，不憑空推斷。 | 不可 |
| 5 | 好，返去頭先個預約 | 恢復同一個 task；用 `medical.search_registration_slots` 重新驗證 P2 的同一 slot 是否仍可用及符合 constraints，檢查草稿期限與撞期結果。 | 不可 |
| 6 | 就 15:30 嗰個 | 選定已驗證的 P2，建立新的 approval A2，顯示正式確認卡。卡片明確寫出尚未掛號。 | 不可 |
| 7 | 點擊 Approve | Server 驗證 A2、task、P2、revision、期限及目前狀態；經 pipeline/MCP 調用 `medical.create_registration`，驗證 backend 結果與 receipt 後顯示成功。 | 此時才可 |

主要展示資料使用不撞期的既有預約，讓七個回合可完整走完。Turn 1 尚未限制下午，不能提前加入 after-3 constraint；主線 fixture 在目標日期提供 14:00、15:30 兩個可用選項，因此可提出 14:00 的 P1。另以獨立測試及展示分支涵蓋真正撞期、資料不足、P2 過期和 slot 被佔用。

## 本輪新增能力

只擴充現有 `DemoMedicalWorkflow`、模型 adapter、canonical delivery 和測試。沿用現有 server-memory demo、每 session 鎖、backend process 內鎖、固定 MCP registry、明確批准、idempotency 和 receipt 驗證。

Agent 必須理解每個新 turn 是修改 constraints、查詢、追問、恢復、選時間或不確定。這些語義由模型提出，runtime 驗證其是否符合當前階段。不能用固定回合編號或七句文字的精確匹配假裝 agent 已理解；scripted mode 仍可用於可重現測試，但必須標示。

查詢是原任務中的一段對話，不建立第二個可執行的業務任務。只支援一個 active booking task、一個 P2 候選和一份最近的 appointments snapshot。可以在查詢階段繼續問相關問題，不要求使用者恰好說出驗收表的文字。

## 草稿和正式批准分開

P1、P2 是 immutable booking candidates，包含 server 提供的病人、科室、slot、時間、地點、constraints revision、digest 和建立／到期時間。P2 存在不代表使用者已批准。

正式確認卡使用獨立 approval ID，例如 A2；`confirmation_id` 在 wire 上代表 A2，並綁定 `candidate_id=P2`。Turn 1、2 顯示草稿建議，不發出可執行 Approve。Turn 6 才發出 A2 和 server-issued action ID。既有欄位名稱保持相容，新增 candidate 與 revision metadata 由 frontend 原樣轉送。

若使用者在已出正式確認卡後改問其他預約，立即撤銷 A2 和其 actions，但可保留 P2 草稿。返回後必須重新驗證和發新確認卡；不能恢復舊 action、延長舊 approval 或把「返去」當批准。

| 事件 | 主任務 identity | Intent revision | P2 草稿 | 正式 approval |
|---|---|---|---|---|
| 修改下午三點後 | 不變 | 增加 | 用新 P2 取代 P1 | 舊的全部失效 |
| 問既有預約或撞期 | 不變 | 不變 | 暫停保留 | 撤銷任何尚未執行的卡 |
| 返回掛號 | 不變 | 不變 | 重新驗證同一 slot | 不自動發出或恢復批准 |
| 選定 15:30 | 不變 | 不變 | 選定通過驗證的候選 | 新建 A2，尚未執行 |
| Approve A2 | 不變 | 不變 | 使用 exact frozen input | 由 server 決定是否可執行 |

## 查詢和對話記錄

工具 allowlist 在上一輪三個工具之外，只新增既有的 **`medical.get_my_appointments`**。呼叫使用 `input:{}`，病人／authorization context 由 server 供應；不接受使用者或模型指定別人的 patient。沿用既有資料回應格式，不新增 backend endpoint。

Turn 3 前若 history 留有尚未完成的 booking assistant tool call，先用同一 call ID 寫入 `DEFERRED_FOR_QUERY`、`executed:false` 的 tool result，保留 P2 草稿，再加入查詢 user message。Turn 4 可使用已配對的查詢結果回答。恢復後的正式執行使用新的 tool call ID；不得為已結束的 planning call 再追加第二個 receipt result。

查詢資料記錄 `fetched_at`、patient binding、request ID 和當時 task/revision。查詢成功、失敗或追問均不能覆寫 booking constraints、selected candidate 或原 task ID。查詢失敗顯示無法核實，不聲稱沒有其他預約。

## 撞期判定

Server 以 timezone-aware 時間比較 P2 與既有預約的半開區間 `[start,end)`：`candidate.start < appointment.end` 且 `appointment.start < candidate.end` 才算重疊。相鄰端點不算撞期，例如 15:00–15:30 與 15:30–15:45。以服務時區 `Asia/Macau` 展示日期，不能只比較鐘面時間或只比較同名科室。

已有預約狀態為 `booked` 或 `confirmed` 時納入判定；`cancelled`／`canceled` 不阻擋；其他未能確定是否占時的狀態標成不確定。相關紀錄缺少有效 start/end、timezone 或讀取不完整時，不能回答「肯定唔撞」。本輪不估算交通、候診或檢查準備時間。

結果為 `clear|overlap|unknown`，並記錄比較的候選與 snapshot。模型把 server 判定轉成自然語言；例如「15:30 掛號與你現有 15:00–15:30 預約沒有時間重疊」，並保留這是目前查詢結果的限制。已知 overlap 或 unknown 時，不發出可執行確認卡，改要求選其他時段或補足資料；本輪不做強制撞期 override。

## 恢復和再次確認

Turn 5 必須重新搜尋，不單靠記憶裡的 availability。以 P2 的 exact slot ID、科室、日期、doctor（若有）、start/end、地點和 constraints 比較新的結果。相同有效候選保留 P2；slot 消失、remaining 不足、內容改變或草稿過期時，P2 失效，提出新草稿 P3 並說明原因，不偷偷選另一個時間。

草稿沿用 300 秒期限；resume 不延長。候選 verification snapshot 有效 60 秒；超過後 Turn 6 必須重查。Appointments snapshot 超過 60 秒也要重新查詢及重算撞期。A2 的 expiry 為發卡時間加 300 秒與候選 expiry 的較早者。到期後只能重新評估及發新卡，不能使舊卡復活。

Approve 時 server 再檢查當前 phase、candidate、approval generation、intent revision、digest、期限、撞期資料和 snapshot freshness。過舊的資料會撤銷 A2、重查並要求新確認；不能在使用者點了舊卡後悄悄刷新批准內容再執行。Availability 最後仍以 backend 建立掛號時的檢查為準。

## 沿用的執行和失敗邊界

`medical.create_registration` 只在 Turn 7 的有效 action 執行，使用 server frozen input、固定 idempotency key 和已有 receipt 驗證。雙擊或重送同一批准回傳原執行結果，不產生另一筆掛號。

已開始執行的掛號不因查詢或瀏覽器 abort 而取消。Receipt 不匹配或 timeout 可能代表 backend 已成功但結果未核實；沿用上一輪 unknown-outcome 阻擋與人工查核，不當作無副作用失敗後重新掛號。

不新增 SQLite、durable task／lease、通用多任務管理、background resume、SDK／HTTP framework、OAuth、跨 domain mutation、取消／改期、前端重設計。重啟仍不保留 pending task／approval，也不增加 crash atomicity 保證。

## 完成條件

七個 turn 可經 canonical HTTP、真實 MCP 和 mock backend 完成；Turn 7 前的 `medical.create_registration` 次數為零。原 task ID 與「下星期二、心臟科、15:00 後」constraints 在 Turn 3–6 保留；P1 不能重放；P2 經查詢後恢復、驗證，且只有 A2 的明確 action 可以提交。撞期、查詢失敗、過期、失去 slot、舊 action 及 timeout 分支均有可重現測試。

實作順序及測試對應見 [第二輪 Implementation Plan](Ponte_Demo_Round2_Implementation_Plan.md)。
