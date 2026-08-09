# Medical live-demo-v2 資料設定

此 profile 已整合至 `main` 的新 UI；目前啟動方式及兩套 runtime 的路由見 [心臟科 Demo](../CARDIOLOGY_DEMO.md)。下文保留資料版本建立時的驗證紀錄，最新整合評估另行保存，不覆寫首次 pilot。

`live-demo-v2` 是明確啟用的合成 medical dataset，讓本地或受監督的線上 demo 有近期庫存、可查詢的預約歷史及可辨別的撞期例子。它沿用現有 HTTP → middleware → ExecutionPipeline → MCP → mock backend，沒有連接真實醫院，也不包含真實病人資料。

本次只改善資料及展示細節。首次 pilot 修正後的剩餘問題仍是模型把「三點後」判成含 15:00，以及 planning 回合輸出 control action；更多資料不能證明這些問題已修好。原有八條案例、評分及 `outputs/evaluation/multi_turn/` 原始紀錄保持不變。豐富資料的驗證須另行報告，不替換原 benchmark 的分數。

## 啟動

在 repository 根目錄，以**新的資料目錄**啟動：

```powershell
$demoData = Join-Path (Get-Location) ('.demo-data-live-v2-' + [guid]::NewGuid().ToString('N'))
python -m scripts.run_stack --demo-agent scripted --medical-data-profile live-demo-v2 --data-dir $demoData
```

打開啟動訊息提供的 frontend URL。`scripted` 是模型決策替身；查詢、批准、MCP dispatch、backend 寫入及 receipt 核實仍實際執行。已有模型設定時可改為 `--demo-agent real`；這不保證真實模型每輪都選對工具，也不免除 provider 費用。

只啟動 backend 時使用相同旗標：

```powershell
python -m mock_backends.server --host 127.0.0.1 --port 8080 --medical-data-profile live-demo-v2 --data-dir $demoData
```

| 設定 | 用途 |
| --- | --- |
| `--medical-data-profile live-demo-v2` / `PONTE_MEDICAL_DATA_PROFILE=live-demo-v2` | CLI 旗標優先於環境變數；未選擇時為 `legacy`，沿用既有資料行為。 |
| `--data-dir` | 指向本次演示專用目錄；新目錄產生新 dataset，既有目錄保留交易紀錄。v2 stack 未指定時使用獨立 `.demo-data-medical-v2`。 |
| `PONTE_PATIENT_ID` | 指定合成病人；stack 讓 backend history 與 middleware 身份一致。預設 `PAT-DEMO-001`。 |
| `--demo-agent scripted` / `real` | 選擇 agent 模式；與 medical 資料設定分開。 |

不要把新 profile 指向 `database`、使用中的 `.demo-data-*` 或任何 evaluation 目錄，企圖把它們變成新 dataset。也不要刪除首次 pilot、失敗 run 或 unknown-outcome 紀錄來重演。

Docker Compose 的 backend 也會接收 `PONTE_MEDICAL_DATA_PROFILE` 和 `PONTE_PATIENT_ID`。切換 v2 時需使用新的 volume，例如在停止目前 stack 後以另一個 project name 啟動 `docker compose -p ponte-live-v2 up --build`；不要刪除既有 volume。Render 單容器的 backend 可讀取相同環境變數，但仍需先完成 Free 部署設定；本次沒有部署線上服務。

## 資料內容與日曆

保留現有三個科室：心臟科、影像科、復康治療科，以及原有檢查／治療服務。合成醫生及地點只供工具結果、選擇卡和 receipt 展示，不代表任何真實機構的排班、收費或臨床流程。

| 項目 | 演示資料 |
| --- | --- |
| 心臟科庫存 | service 當日到當日 +14 日（兩端日期均包含）之間的平日；提供 09:00、10:30、14:00、15:00、15:30、16:00，另有已滿的 15:15。當日只列尚未開始的時段；目前 agent 只使用下午時段。 |
| 醫生 | 兩位合成心臟科醫生，slot 綁定實際 doctor ID。 |
| 預約歷史 | 嚴格下一個星期二 14:45–15:15 的 booked 影像科預約、reference date 後下一個平日 10:00–10:45 的 confirmed 復康預約，以及下一個星期二 15:30–15:45 的 cancelled 心臟科預約。 |
| 撞期例子 | 下一個星期二 15:00 心臟科與影像科預約重疊；15:30 不重疊。已取消紀錄不能當成有效撞期。 |
| 庫存與交易 | slot 有穩定日期 ID；掛號消耗該 slot 庫存，歷史查詢反映實際已保存紀錄。 |

時間採用 service clock 與 `Asia/Macau`（UTC+08:00），不是瀏覽器本機時區。下星期二是 service 當日之後的嚴格下一個星期二；星期二當日指向七天後。演示前核對畫面上的實際日期，不使用 pilot 固定的 2026-10-13 時鐘來啟動 live demo。

庫存滾動與既有交易分開：日期改變時不搬移已保存預約，也不重設已使用 slot 的容量。Slot ID 包含實際日期，例如 `SLOT-LIVE-V2-REG-YYYYMMDD-CARDIO-HHMM`，同一日期／時間重查及重啟保持同一 ID。重新啟動不是清空資料或取消掛號的方法。歷史 seed 綁定首次建立 dataset 的 reference date，不隨每次重啟搬到新的「下星期二」。長期保留同一目錄後，初始歷史可能已成過去，完整重演故事應另建新目錄。

## 建議展示

1. 「幫我預約下星期二的心臟科」：查科室及可用下午時段，建立草稿；沒有掛號。
2. 「下午三點後先得」：更新限制並撤銷舊草稿，選取符合限制的 slot。
3. 「等等，我之前有冇其他預約？」：調用 `medical.get_my_appointments`，展示合成病人的已保存預約。
4. 「咁會唔會撞時間？」：以當前候選及查詢快照回答；15:30 與 14:45–15:15 影像科紀錄不重疊。
5. 「好，返去頭先個預約」：重新查驗候選，保留原任務；不可復用失效庫存。
6. 「就15:30嗰個」：顯示正式確認卡；文字選擇仍沒有寫入。
7. 點擊「確認掛號」：server 驗證當前 proposal，執行 `medical.create_registration` 並核實 backend receipt。

另開新 session 可展示「15:00 有冇撞期？」的重疊例子，但新 session 不會清空 backend 預約。對時間、交通或候診的回答不能超出已查資料；目前只比較預約起止區間。

資料設定沒有擴大 agent 的服務範圍：目前 demo agent 仍只處理心臟科下午掛號及相關預約歷史／撞期查詢。目錄中有影像科和復康服務，不表示 agent 已能自由預約它們。文字「OK」「應該冇問題」不代替正式卡批准。

## 資料生命週期與限制

- 同一 data directory、同一 patient 的不同瀏覽器 session 共用預約與庫存。一人掛號會影響其他人的搜尋結果；這不是多使用者隔離。
- UI「重新開始」只建立新的 conversational session，保留 backend bookings。不要把它當成資料 reset。
- 首次建立 v2 時，`medical/demo_profile.txt` 先保存 profile、reference date 及 patient，然後插入保留 ID 的合成 history。若中途停止，下一次啟動只補上缺少的保留 seed ID，保留已有紀錄，不重複插入或覆寫交易。這不是跨檔案原子交易保證。
- 沒有 profile marker 但 medical 目錄已有任何 `.txt` 時，v2 拒絕覆寫。Marker 的 profile／patient 不一致也拒絕啟動；v2 目錄不可改用 `legacy` 啟動。保留原目錄查核，改用新目錄演示，不手動刪除單個交易檔或 marker。
- 沒有公開 reset endpoint。重用同一目錄會保留已完成掛號、既有 history 與 idempotency 紀錄。
- pending task、proposal 和批准仍在 middleware 程序記憶體中；重啟後須重新開始、查詢和批准。JSON 儲存沒有跨程序或 crash-atomic 交易保證。
- 如掛號結果不明，先核對該目錄的 `medical/appointments.txt`、`tasks.txt`、`idempotency.txt`；不可換 session 或重啟來假定交易沒有成功。
- [Render Free](https://render.com/docs/free) 的臨時磁碟在重啟、重新部署或休眠後會遺失資料。此 profile 提供可重建的 mock 演示資料，不能代替線上持久化與真實交易恢復。

## 驗證與評估分開

新增資料驗證應覆蓋：當日到 +14 日的包含邊界與週末、當日過期時間／時區、doctor／department／location 關聯、已滿 slot 不出現在可用清單、日期 ID 穩定、seed 重啟不重複及部分 seed 恢復、profile／patient 不一致拒絕、history 狀態與撞期、已掛號容量不恢復，以及新 session 保留 backend records。

測試及 benchmark 直接呼叫的 `create_application(data_dir, clock=None, *, medical_data_profile="legacy", patient_id="PAT-DEMO-001")` 不隱式讀取環境變數；只有明確傳入 v2 才改變資料設定，避免部署環境變數污染原有 fixtures。

原有八條 multi-turn 案例仍用它們自己的隔離 fixtures。它們包含 15:00 邊界、失效 proposal、slot 被佔用和重複批准，不能因新 demo 資料更容易完成而改 oracle 或刪除困難路徑。任何使用 `live-demo-v2` 的 scripted／real-model 演示結果，須標明新 profile、資料目錄／hash、service clock、模型模式及是否真正取得 receipt；不要併入首次 pilot 的 TCR、SCR 或 UEC。

## 本次驗證（2026-10-14）

| 驗證 | 結果 |
| --- | --- |
| 資料、backend、seed 與 legacy 醫療回歸 | 41 tests 通過，含 18 項新增資料／整合檢查。 |
| HTTP/MCP、既有兩輪 demo 與 stack 設定 | 47 tests 通過，含新增資料的三項 queued-model acceptance。 |
| 最終 v2 HTTP/MCP | 4 tests 通過；另外驗證 app 使用的 `ScriptedCardiologyClient` 完成七輪流程並取得 receipt。前三項與上列重疊，合計 89 個不同 Python tests。 |
| 前端 console／workspace／voice cancel | 21 tests 通過。 |
| Docker Compose 設定 | `docker compose config --quiet` 通過；未建立容器映像或部署線上。 |
| 原八條 scripted benchmark | TCR 8/8、SCR 47/47、UEC 0；沿用原 fixtures。 |

新增完整流程另驗證：15:00 撞期不發正式卡、其他病人佔用 15:30 後撤銷草稿、明確批准前零寫入，以及重複批准只有一次實際 MCP write。新 profile 尚未進行 real-model 評估，本次沒有額外 provider 呼叫或費用。

原 benchmark 重跑證據：[完整 run](../../outputs/evaluation/multi_turn/20261013T180317Z-c80a1e13/report.md)。案例 SHA256 仍為 `e2afda1cbf7cea882dd44adfce03c2d8e31a2b8ff62847b5d724d7e20fe39100`。首次 pilot 與既有 post-fix 結果未改寫。

也保留了 [初次受限環境的 run](../../outputs/evaluation/multi_turn/20261013T180050Z-4ce13ced/report.md)：loopback 被 sandbox 阻擋，沒有抵達任何 checkpoint；不能用其中顯示的 UEC 0 推論安全。取得本機 HTTP 執行權限後才產生上列有效結果。初次單元測試的系統暫存目錄權限問題以 workspace 暫存目錄處理；HTTP 測試另遇到 Windows 父子程序編碼不一致，統一 UTF-8 後通過，沒有修改案例來避過斷言。

Windows 使用 `python -X utf8` 跑 HTTP/MCP 測試時，先設 `$env:PYTHONUTF8='1'`，讓 MCP child 採用相同編碼。可重現的測試入口：

```powershell
$env:PYTHONUTF8='1'
python -X utf8 -m unittest tests.medical.test_live_demo_profile tests.medical.test_live_demo_backend tests.medical.test_medical_backend tests.medical.test_cardiology_demo_backend tests.test_medical_demo_seed
python -X utf8 -m unittest tests.test_live_medical_demo_e2e tests.test_demo_agent_e2e tests.test_demo_round2_e2e tests.test_run_stack
node --test tests/frontend_demo_console.test.mjs tests/frontend_workspace_behavior.test.mjs tests/frontend_voice_cancel.test.mjs
python -m evals.multi_turn.runner --track scripted
```
