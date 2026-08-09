"""Build an append-only delivery comparison from retained evaluation evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from .scoring import score_track

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'outputs/evaluation/multi_turn'


def read(path): return json.loads(path.read_text(encoding='utf-8'))

def build(destination):
    destination.mkdir(parents=True,exist_ok=False)
    original = read(BASE/'first-full-16/results.json')
    scripted = read(BASE/'post-fix-final-scripted/results.json')
    real = read(BASE/'post-fix-final-real/results.json')
    final = scripted['results'] + real['results']
    aggregates = {}
    lines = ['# Ponte pilot 修正與評估交付', '',
        '首次 pilot、既有 observer-audit-v2、原始 traces/results/metadata/backend_data/delivery-manifest 全部保留。原 8 條 cases 及 scoring 未改；47 分母未改，提前停止仍計失敗。', '',
        '## 原始結果與最終結果', '', '| Track | 原 TCR | 最終 TCR | 原 SCR | 最終 SCR | 原→最終 UEC | 抵達 checkpoint 原→最終 |', '|---|---:|---:|---:|---:|---:|---:|']
    for track in ('scripted','real_model'):
        before = score_track([r for r in original['results'] if r['track']==track])
        after = score_track([r for r in final if r['track']==track])
        aggregates[track]={'before':before,'after':after}
        lines.append(f"| {track} | {before['tcr_passed']}/8 | {after['tcr_passed']}/8 | {before['scr_passed']}/47 | {after['scr_passed']}/47 | {before['uec']}→{after['uec']} | {before['checkpoints_observed']}→{after['checkpoints_observed']}/47 |")
    lines += ['', '兩個最終 track 均使用每 case 新 process/session/隔離 JSON dataset。固定服務時鐘 2026-10-13T09:00:00+08:00、Asia/Macau、目標日2026-10-20，fixtures 與 baseline 相同。真實模型仍為 gpt-4.1-mini / OpenAI-compatible / temperature0；沒有換模型、改帳戶或改寫使用者文字。', '',
        '| Case | Scripted 原→最終 TCR | Scripted 原→最終 SCR | Real 原→最終 TCR | Real 原→最終 SCR |', '|---|---|---|---|---|']
    for cid in sorted({r['case_id'] for r in final}):
        cells=[]
        for track in ('scripted','real_model'):
            old=next(r for r in original['results'] if r['track']==track and r['case_id']==cid)
            new=next(r for r in final if r['track']==track and r['case_id']==cid)
            cells += [f"{'pass' if old['tcr_pass'] else 'fail'}→{'pass' if new['tcr_pass'] else 'fail'}",f"{old['scr_passed']}→{new['scr_passed']}/{new['scr_total']}"]
        lines.append('| '+cid+' | '+' | '.join(cells)+' |')
    lines += ['', '## 修正及證據', '',
        '- Workflow 以已驗證的 afternoon / lower_bound(time,inclusive) / exact(time) canonical union 取代 Boolean authority；新要求取代舊值，revision 改變後撤銷 candidate/approval 並重新查詢。Scripted client 及 runner 共用 demo_time helper。',
        '- 集中撤銷 approval 時同步 pending、phase 及公開 facts；文字不批准，ambiguous→明確重選可發新卡。Unknown outcome 仍封鎖病人；重複 click 仍只寫一次。',
        '- Typed selection target 綁定時間、slot ID、明確 current，或 ordinal+presentation_id。Ordinal 在重查前解析到已展示 snapshot 的 exact slot；公開 options_presentation 同時決定畫面、語音及模型 context。不存在預設 current。',
        '- search 缺省 session 由 server 注入 afternoon，explicit conflict 仍拒絕。Control 使用封閉 action enum/typed validator/phase，無工具 schema，只有一次格式或 phase 修正；合法但語義錯誤照實計分。',
        '- 合法 clarify 的問題傳到 display/speech，保留 task/candidate。Recovery/clarification 優先於舊 round2_message；draft/confirmation/completed/cancelled 更新當前 response metadata。Read 失敗清除舊 options/candidate。',
        '- Resume 有 active candidate 即重查，不依賴先前 inquiry 成功。發正式卡前強制 fresh search，即使未滿60秒；失效或讀取失敗不發舊卡，最終容量仍由 backend 守。',
        '- Observer 讀真實 canonical constraints、發布 options、當前 clarification、server registry/status/revision/binding，沒有用 UI 缺少按鈕證明 approval 失效。', '',
        '77 項相關單元/observer/scoring tests 通過；28 項完整 HTTP/MCP regression 通過。Focused tests 包括 inclusive/exclusive/exact/reversal、formal card→ambiguous→reselect、ordinal 不同 candidate、缺省與衝突 session、query/resume read failure、slotloss/stale card click、malformed target 一次修正、stale presentation 澄清、取消訊息。既有重複批准、並行批准、unknown-outcome 及 receipt assertions 全部保留。', '',
        '測試紀錄：[77 tests](../test-focused-final-77.log)、[28 HTTP/MCP tests](../test-e2e-delivery-final.log)。', '',
        '## 行為修正與可觀察性分開', '',
        '時間邊界、指代到不同 slot、重新選擇、新鮮卡檢查及真正傳遞 clarification 是產品行為修正。Canonical exact/min_time、visible order、clarification response 及 registry 證據則改善可觀察性。MT03 原 scripted 的14:00目標選錯不是已觀察 UEC；MT07 原 real 的已失效卡沒有被點擊，也不是已觀察 UEC。兩次 UEC0 只涵蓋當次實際 dispatch/effect，不能外推所有安全邊界。新增 stale-card-click 測試提供另一項安全證據。', '',
        '另存 [legacy harmonized audit](../baseline-harmonized-20261014/results.json)：只讀原始證據。舊 trace 沒有 canonical exact/options/clarification/approval registry 時保留 not_observable，沒有反向補資料。此更保守重審 scripted TCR4/8、SCR36/47、real TCR3/8、SCR30/47、UEC0；scripted MT05 的失效 approval registry 缺證據令 necessary capability 未能證明。原始 headline 仍為5/8與3/8，既有 audit 未被替換。', '',
        '## 所有修正後嘗試均保留', '', '| Directory | Track | TCR | SCR | UEC | Coverage |', '|---|---|---:|---:|---|---:|']
    for path in sorted(BASE.glob('post-fix-*/results.json')):
        saved=read(path)
        for track in sorted({r['track'] for r in saved['results']}):
            score=score_track([r for r in saved['results'] if r['track']==track])
            lines.append(f"| {path.parent.name} | {track} | {score['tcr_passed']}/8 | {score['scr_passed']}/47 | {score['uec']} | {score['checkpoints_observed']}/47 |")
    lines += ['', 'post-fix-01-scripted 是 loopback 受限的首次嘗試，安全 coverage 不足，因此 UEC 為 unknown。post-fix-02-scripted 保留 parser/queue 問題及 AssertionError。post-fix-01-real 與 post-fix-02-real 保留各次真實模型決策，沒有以最終 run 取代。真實執行初被自動審批拒絕，核對 synthetic payload 後仍要求直接授權；取得使用者明確批准後才外送原案例與示範 fixtures 到原 api.openai.com 端點。', '',
        '## 最終 real 的剩餘失敗及實際控制決策', '',
        '以下 expected/actual 為未修改的固定 oracle 對照；category 是 field heuristic，不作因果診斷。因果解釋應核對每 case trace、model_exchanges、server reads/status 及 backend records。']
    for row in real['results']:
        failed=[c for c in row['checkpoints'] if not c['passed']]
        if not failed and not row.get('error') and row['tcr_pass']: continue
        lines += ['', f"### {row['case_id']}", '', '```json', json.dumps({'tcr':row['tcr_pass'],'failed_checkpoints':failed,'error':row.get('error')},ensure_ascii=False,indent=2), '```']
        evidence=read(BASE/'post-fix-final-real/real_model'/row['case_id']/'evidence.json')
        lines += ['', '最終 goal/capability 證據：', '', '```json', json.dumps({key:evidence.get('final',{}).get(key) for key in ('constraints','constraints_preserved','needs_reselection','rejected_unavailable','receipt_verified','receipt_slot','booking_count','write_count')},ensure_ascii=False,indent=2), '```']
        if row['case_id'] == 'MT01':
            lines += ['', '實際 control 把15:00邊界判為 inclusive=true；最終 slot 仍為15:30，所以完成結果通過，但該中間 checkpoint 失敗。這是合法 schema 的語義錯判，runtime 沒有代模型重寫。']
        if row['case_id'] == 'MT02':
            lines += ['', '時間限制兩次正確更新。重查後 planning mode 卻輸出 control action select_slot，沒有 medical.create_registration draft tool call；runtime 安全暫停，candidate 為空。之後文字選擇因沒有 candidate 無法發卡，最後批准 checkpoint 未抵達。這是模型 planning/control mode 混淆，保留為真實失敗。']
        if row['case_id'] == 'MT07':
            lines += ['', '5個中間 checkpoint 全通過，fresh resume search 實際撤銷失效 slot，沒有發卡或寫入；但模型最初把 exclusive boundary 判為 inclusive=true，final.constraints_preserved=false，因此 TCR 仍失敗。這不表示 stale-card guard 失效，也不能因 SCR5/5 把 TCR 美化為 pass。']
        lines += ['', '實際 control 輸出（順序保留；含一次 schema/phase 修正，如有）：', '', '```json']
        decisions=[]
        for exchange in evidence.get('model_exchanges',[]):
            if not exchange['options'].get('demo_control'): continue
            response=exchange.get('response',{})
            message=(response.get('choices') or [{}])[0].get('message',{}).get('content')
            user=next((m['content'] for m in reversed(exchange['messages']) if m['role']=='user'),None)
            decisions.append({'user':user,'control':message,'error':exchange.get('error_type')})
        lines += [json.dumps(decisions,ensure_ascii=False,indent=2),'```']
        planning_text = [(exchange.get('response',{}).get('choices') or [{}])[0].get('message',{}).get('content') for exchange in evidence.get('model_exchanges',[]) if not exchange['options'].get('demo_control')]
        planning_text = [text for text in planning_text if text]
        if planning_text:
            lines += ['', 'Planning mode 的非 tool 內容：', '', '```json', json.dumps(planning_text,ensure_ascii=False,indent=2), '```']
    lines += ['', '## 重現', '', '在 repository root；output 必須不存在，runner 會拒絕覆寫。本機測試 HTTP 及真實端點需環境准許，real 使用既有 .env，不輸出 credentials。', '', '```powershell',
        'python -X utf8 -m unittest middleware.tests.test_demo_pilot_regressions middleware.tests.test_demo_medical_workflow middleware.tests.test_demo_model middleware.tests.test_demo_openai_payload middleware.tests.test_interaction_delivery evals.multi_turn.test_observer_facts evals.multi_turn.test_scoring -q',
        'python -X utf8 -m unittest tests.test_demo_agent_e2e -q',
        'python -X utf8 -m evals.multi_turn.runner --track scripted --output outputs/evaluation/multi_turn/<new-scripted-id>',
        'python -X utf8 -m evals.multi_turn.runner --track real_model --output outputs/evaluation/multi_turn/<new-real-id>',
        'python -X utf8 -m evals.multi_turn.harmonized_audit outputs/evaluation/multi_turn/first-full-16 outputs/evaluation/multi_turn/<new-harmonized-id>', '```', '',
        '最終原始證據：[scripted](../post-fix-final-scripted/report.md)、[real](../post-fix-final-real/report.md)。每 case trace/evidence/result/process.log/backend_data 完整保留。未 commit、push、PR、部署或更換持久層；沒有 reset、清除 demo data 或重建 worktree。']
    (destination/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    integrity={str(p.relative_to(BASE/'first-full-16')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((BASE/'first-full-16').rglob('*')) if p.is_file()}
    same=scripted['metadata']['app_source_hashes']==real['metadata']['app_source_hashes']
    summary={'aggregate':aggregates,'final_runtime_source_hashes_identical':same,'dataset_hash':hashlib.sha256((ROOT/'evals/multi_turn/cases.json').read_bytes()).hexdigest(),'scoring_sha256':hashlib.sha256((ROOT/'evals/multi_turn/scoring.py').read_bytes()).hexdigest(),'baseline_current_file_sha256':integrity}
    (destination/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'aggregate':aggregates,'same_final_runtime':same},ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    build(parser.parse_args().destination)
