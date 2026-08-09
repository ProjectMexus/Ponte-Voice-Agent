# Ponte Frontend

這是零 build dependency 的前端，使用 main 的 canonical interaction API、agent、工具驗證及確認流程。

## 啟動

從 repository 根目錄啟動完整 stack：

```bash
python scripts/run_stack.py --backend-port 18187 --middleware-port 18197 --frontend-port 16177 --data-dir .demo-data-ui-main
```

開啟 `http://127.0.0.1:16177/?middleware=http://127.0.0.1:18197`。
也可單獨啟動前端：`python -m frontend.server --host 127.0.0.1 --port 5173`。
前端預設連接 `http://127.0.0.1:8090`；query 的 `middleware` 可指定其他位置。
Agent 與模型設定沿用根目錄 README 和 `docs/AGENT_EXECUTION.md`，本版不依賴舊的 scripted cardiology runtime。
預約與福利服務是本機模擬資料。

## 介面與互動

- 淡藍漸變、半透明面板與 SVG 圖示。文字與按鈕維持清晰對比；無背景模糊支援或啟用 reduce-transparency 時使用實色面板。
- 對話保留每輪文字；常用服務按鈕只填入需求，仍需自行送出。編輯需求會同步更新選取狀態，空白需求不能送出。
- 錄音與請求處理期間阻止重複送出；語音辨識結束但沒有文字時恢復輸入。失敗時保留需求，方便重試。
- 右側顯示伺服器投影的服務資料與原封不動的 action event。點選項目有處理回饋，關鍵操作仍需自行確認。
- 操作回放只呈現實際執行紀錄，不發出工具要求、不點按按鈕、不移動鍵盤焦點。可略過或從處理紀錄重播；操作、語言切換及重新開始會停止回放。
- 回放是 HTTP 完成一輪後的紀錄展示，不代表即時工具耗時或重建歷史畫面。只投影允許的服務事件，不公開模型訊息、工具參數、憑證或原始回覆。
- 小澳的光環隨聆聽、處理、朗讀狀態變化；朗讀可立即靜音。繁中／EN 切換介面文字，服務內容沿用伺服器提供的文字。
- 手機上下排列，短螢幕收緊間距；支援鍵盤焦點、reduce-motion、回執列印，以及錯誤提示和重設對話框。
- 重新開始只清除本輪對話與未提交選項，已保存的模擬預約保留。

## 驗證

```bash
node --test tests/frontend_text_input.test.mjs tests/frontend_demo_console.test.mjs tests/frontend_workspace_behavior.test.mjs tests/frontend_agent_motion.test.mjs tests/frontend_voice_cancel.test.mjs
python -m unittest tests.test_frontend_static tests.test_frontend_interaction_contract tests.test_agent_full_stack -q
```

`middleware/service_activity.py` 是 main execution trace 的只讀顯示轉換；工具選擇、授權、確認、提交與回執驗證仍由 main 的 runtime 管理。
