"""One isolated real-model rehearsal; retain observable responses, not secrets."""
import argparse,hashlib,json,os,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from middleware.config import load_dotenv
from middleware.demo_model import RegistryToolNameClient
from middleware.llm_configuration import agent_chat_client_from_environment
from tests.test_english_medical_demo_e2e import EnglishMedicalDemoEndToEndTests

parser = argparse.ArgumentParser(description="Local English seven-turn acceptance; real_model makes billable calls.")
parser.add_argument("--track", choices=("scripted", "real_model"), default="scripted")
args = parser.parse_args()
load_dotenv()
environment=dict(os.environ)
for field in ('API_URL','API_KEY','MODEL'):
    if environment.get('PONTE_DEMO_LLM_'+field): environment['PONTE_LLM_'+field]=environment['PONTE_DEMO_LLM_'+field]
directory=Path('outputs/evaluation')/('integration-english-'+args.track+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
directory.mkdir(parents=True,exist_ok=False)
evidence={'track':args.track,'model':environment.get('PONTE_LLM_MODEL'),'passed':False,'turns':[],
          'scenario':'Seven English turns: draft, constraints, inquiry, conflict, resume, selection, approval, verified receipt and replay',
          'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('middleware/demo_medical_workflow.py'),Path('middleware/interaction_core.py'),Path('middleware/interaction_delivery.py')]}}
test=EnglishMedicalDemoEndToEndTests()
try:
    test.setUp()
    harness=test.harness
    workflow=harness.app.demo_workflow
    if args.track == "real_model":
        workflow.client=RegistryToolNameClient(agent_chat_client_from_environment(environment))
        workflow.model_mode='real'
        harness.app.demo_agent_mode='real'
    else:
        evidence["model"] = "ScriptedCardiologyClient"
    original=harness.http_json
    def http_json(method,url,body=None,headers=None):
        status,response=original(method,url,body,headers)
        if '/api/interactions' in url:
            evidence['turns'].append({'input':body,'http_status':status,'response':response})
            (directory/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        return status,response
    harness.http_json=http_json
    test.test_seven_english_turns_confirm_receipt_and_replay_once()
    evidence['passed']=True
    evidence['write_dispatches']=len(test.live.write_dispatches())
    evidence['booking_requests']=len(harness.booking_requests())
except Exception as error:
    evidence['error_type']=type(error).__name__
    # Assertions contain only our synthetic expected/actual values. Provider exceptions may contain secrets.
    if isinstance(error,AssertionError): evidence['assertion']=str(error)
finally:
    if hasattr(test,'harness'):
        shutil.copytree(test.harness.data_dir,directory/'backend_data',dirs_exist_ok=False)
    test.doCleanups()
    (directory/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'path':str(directory),'passed':evidence['passed'],'error_type':evidence.get('error_type'),'assertion':evidence.get('assertion'),'write_dispatches':evidence.get('write_dispatches')},ensure_ascii=True))
