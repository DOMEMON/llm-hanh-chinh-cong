"""Endpoint tests with mocked DB transport; NOT a PostgreSQL connectivity test."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.testclient import TestClient
import app.main as main
from app.config import Settings
from app.corpus import read_corpus,fingerprint

class FakeConnection:
    async def run_sync(self,fn):pass
class FakeEngine:
    @asynccontextmanager
    async def begin(self):yield FakeConnection()
    async def dispose(self):pass
class FakeDB:
    async def execute(self,*args,**kwargs):pass
class FakeSessions:
    @asynccontextmanager
    async def begin(self):yield FakeDB()
    @asynccontextmanager
    async def __call__(self):yield FakeDB()

def test_endpoints_with_mocked_storage(monkeypatch):
    corpus=read_corpus(Path(__file__).resolve().parents[1]/'fixtures/demo')
    states={};logs=[]
    monkeypatch.setattr(main,'make_database',lambda settings:(FakeEngine(),FakeSessions()))
    async def active(db):return fingerprint(corpus),corpus
    async def get(db,sid):return states.get(sid)
    async def save(db,state):states[state['session_id']]=state
    async def log(db,sid,payload):logs.append(payload)
    monkeypatch.setattr(main,'load_active',active);monkeypatch.setattr(main,'get_state',get)
    monkeypatch.setattr(main,'save_state',save);monkeypatch.setattr(main,'log_event',log)
    cfg=Settings(api_token='secret',bootstrap_demo=False,allow_draft=True,generator_backend='mock')
    headers={'Authorization':'Bearer secret'}
    with TestClient(main.create_app(cfg)) as client:
        assert client.get('/health').status_code==200
        assert client.get('/health').json()['generator']=='mock'
        preflight=client.options('/api/v1/answer',headers={
            'Origin':'http://127.0.0.1:3000','Access-Control-Request-Method':'POST',
            'Access-Control-Request-Headers':'content-type'})
        assert preflight.status_code==200
        assert preflight.headers['access-control-allow-origin']=='http://127.0.0.1:3000'
        assert client.post('/api/v1/answer',json={'query_text_raw':'demo alpha'}).status_code==401
        def call(text,endpoint='answer',**kwargs):
            return client.post('/api/v1/'+endpoint,headers=headers,json={'query_text_raw':text,'session_id':'test-session',**kwargs})
        response=call('demo alpha lệ phí');assert response.status_code==200,response.text
        assert response.json()['status']=='answered'
        assert response.headers['X-Conversation-Session-Id']=='test-session'
        assert call('còn thời gian','retrieve').json()['resolved_procedure_id']=='DEMO-A'
        assert call('demo beta lệ phí','retrieve').json()['resolved_procedure_id']=='DEMO-B'
        assert call('demo chung lệ phí').json()['status']=='clarification_needed'
        assert call('zzzzzzzz').json()['status']=='insufficient_data'
        assert states['test-session']['last_resolved_procedure_id'] is None
        assert call('demo alpha',filters={'effective_date':'bad'}).status_code==422
        assert call('demo alpha',top_k=0).status_code==422
    assert len(logs)==5
    assert all('top_score' in p and 'second_score' in p and 'margin' in p for p in logs)
    assert all('snapshot' in p and 'bundle_id' in p and 'segmenter' in p for p in logs)
    assert all(not {'query_text_raw','query','text','answer_text','source_text'} & p.keys() for p in logs)

def test_real_generator_is_constructed_from_settings(monkeypatch):
    from person3_generation_evaluation import GroundedGenerator,LlamaCppHTTPRuntime

    cfg=Settings(generator_backend='llama_cpp',llm_base_url='http://127.0.0.1:8081',
        llm_model='test-model',llm_api_key='test-key',llm_timeout_seconds=12)
    generator=main.create_generator(cfg)
    assert isinstance(generator,GroundedGenerator)
    assert isinstance(generator.runtime,LlamaCppHTTPRuntime)
    assert generator.runtime.base_url=='http://127.0.0.1:8081'
    assert generator.runtime.model=='test-model'
    assert generator.runtime.api_key=='test-key'
    assert generator.runtime.timeout_seconds==12
