from copy import deepcopy
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from .grounded import checked_plan, discard_output_only_filters, bind_unique_scopes
from .scope import operations, exception_reasoning
from .table import Table, execute_plan
from .service import create_app, DatasetStore
from .test_service import ContractModel


@pytest.fixture
def table(tmp_path):
    path = tmp_path / 'data.csv'
    path.write_text('name,group,price (USD),score\nAlpha,A,0,10\nBeta,A,5,20\nGamma,B,2,90\n', encoding='utf-8')
    t = Table(path)
    yield t
    t.close()


def tasks():
    return [dict(request_text='Có bao nhiêu dòng group A', status='answer', operation='count_rows',
        bindings=[], filter_logic='and', filters=[dict(column='group',operator='eq',value='A')], scope_ref=0, scope_quote=''),
        dict(request_text='score trung bình của nhóm này',status='answer',operation='avg',
        bindings=[dict(column='score',requested_text='score')],filter_logic='and',filters=[],scope_ref=1,scope_quote='nhóm này')]


def test_shared_scope_uses_all_and_only_matching_rows(table):
    ts = tasks()
    q = '; '.join(t['request_text'] for t in ts)
    p = checked_plan(ts[1],table,q,tasks=ts,task_index=1)
    assert execute_plan(p,table)['data'] == [{'result':15.0}]
    assert ts[1]['filters'] == []  # no mutation / laundering of source conditions


def test_explicit_global_scope_does_not_inherit(table):
    ts = tasks()
    ts[1].update(request_text='score trung bình toàn bảng',scope_ref=0,scope_quote='')
    p = checked_plan(ts[1],table,'; '.join(t['request_text'] for t in ts),tasks=ts,task_index=1)
    assert execute_plan(p,table)['data'] == [{'result':40.0}]


@pytest.mark.parametrize('change,code',[
    ({'scope_ref':0},'UNRESOLVED_GROUP_REFERENCE'),
    ({'scope_ref':2},'SCOPE_MUST_REFERENCE_EARLIER_TASK'),
    ({'scope_quote':'nhóm khác'},'SCOPE_REFERENCE_NOT_BOUND'),
    ({'operation':'select'},'REQUESTED_OPERATION_NOT_PRESERVED'),
])
def test_bad_scope_or_operation_cannot_report_answer(table,change,code):
    ts = tasks(); ts[1].update(change)
    with pytest.raises(ValueError,match=code):
        checked_plan(ts[1],table,'; '.join(t['request_text'] for t in ts),tasks=ts,task_index=1)


def test_missing_prior_scope_cannot_become_global(table):
    ts=tasks(); ts[0]['status']='clarify'
    with pytest.raises(ValueError,match='REFERENCED_SCOPE_UNAVAILABLE'):
        checked_plan(ts[1],table,'; '.join(t['request_text'] for t in ts),tasks=ts,task_index=1)


def test_model_cannot_choose_arbitrary_group_when_two_exist(table):
    ts=tasks(); second=deepcopy(ts[0]); second['request_text']='Có bao nhiêu dòng group B'
    second['filters'][0]['value']='B'; ts.insert(1,second)
    with pytest.raises(ValueError,match='AMBIGUOUS_GROUP_REFERENCE'):
        checked_plan(ts[2],table,'; '.join(t['request_text'] for t in ts),tasks=ts,task_index=2)


def test_free_can_only_bind_numeric_price_not_unrelated_zero(table):
    t=dict(request_text='Liệt kê name miễn phí',status='answer',operation='select',
        bindings=[dict(column='name',requested_text='name')],filter_logic='and',
        filters=[dict(column='price (USD)',operator='eq',value='0')])
    p=checked_plan(t,table,t['request_text'])
    assert execute_plan(p,table)['data']==[{'name':'Alpha'}]
    t['filters'][0]['column']='score'
    with pytest.raises(ValueError,match='FILTER_VALUE_NOT_IN_QUESTION_SPAN'):
        checked_plan(t,table,t['request_text'])


@pytest.mark.parametrize('content,code',[(b'a,a\n1,2\n','INVALID_HEADERS_OR_TABLE_LIMIT'),(b'name\n\xff\n','CSV_REQUIRES_UTF8')])
def test_failed_upload_leaves_no_directory(tmp_path,content,code):
    store=DatasetStore(tmp_path,ContractModel,'grounded')
    with pytest.raises(ValueError,match=code): store.ingest(content,'data.csv')
    assert list(tmp_path.iterdir())==[]


def test_model_failure_also_rolls_back_upload(tmp_path):
    class Failed(ContractModel):
        def call(self,*a,**kw): raise RuntimeError('offline')
    with pytest.raises(RuntimeError): DatasetStore(tmp_path,Failed).ingest(b'a\n1\n','data.csv')
    assert list(tmp_path.iterdir())==[]


def test_retry_replays_result_without_advancing_conversation(tmp_path):
    with TestClient(create_app(tmp_path,ContractModel,'grounded')) as client:
        data=client.post('/v1/datasets?filename=x.csv',content=b'a\n1\n2\n').json()
        route='/v1/datasets/'+data['dataset_id']; headers={'X-Dataset-Token':data['dataset_token']}
        state=client.post(route+'/conversations',headers=headers,json={'version':data['version']}).json()
        body={'version':data['version'],'question':'Có bao nhiêu dòng?',
            'conversation_id':state['conversation_id'],'revision':0,'request_id':str(uuid.uuid4())}
        first=client.post(route+'/query',headers=headers,json=body).json()
        second=client.post(route+'/query',headers=headers,json=body).json()
        assert second['replayed'] is True
        assert first['results']==second['results']
        assert first['conversation']['revision']==second['conversation']['revision']==1
        assert 'last_request' not in second['conversation']
        assert client.post(route+'/query',headers=headers,json={**body,'question':'changed'}).status_code==409
        assert client.post(route+'/query',json=body).status_code==404


def test_ready_separates_model_failure_from_process_health(tmp_path,monkeypatch):
    async def fail(*args,**kwargs): raise httpx.ConnectError('model offline')
    monkeypatch.setattr(httpx.AsyncClient,'get',fail)
    with TestClient(create_app(tmp_path,ContractModel,'grounded')) as client:
        assert client.get('/health').status_code==200
        assert client.get('/ready').status_code==503


def test_quoted_values_are_not_statistics():
    assert operations('Tra cứu "average price"')==set()
    assert operations('Xe này có bao nhiêu xi-lanh?')==set()
    assert operations('Có bao nhiêu dòng?')=={'count'}


def test_exception_checks_are_a_separate_capability(table):
    from .collection import run_collection
    class NoModel:
        def call(self,*a,**kw): raise AssertionError('Unavailable capability must not reach model')
    result=run_collection(table,'Liệt kê các mục hợp lệ sau khi xét mọi ngoại lệ',NoModel())
    assert result['results'][0]['status']=='clarify'
    assert not result['results'][0]['data']
    assert not exception_reasoning('Hiển thị "xét mọi ngoại lệ" trong cột name')
    assert exception_reasoning('Show products available without any requirements')
    assert exception_reasoning('Những dịch vụ sử dụng vô điều kiện')


def test_unique_group_binding_does_not_choose_between_two_groups():
    ts=tasks(); ts[1].update(scope_ref=0,scope_quote='')
    bind_unique_scopes(ts)
    assert ts[1]['scope_ref']==1
    ts=tasks(); second=deepcopy(ts[0]); second['filters'][0]['value']='B'
    ts.insert(1,second); ts[2].update(scope_ref=0,scope_quote='')
    bind_unique_scopes(ts)
    assert ts[2]['scope_ref']==0


@pytest.mark.parametrize('operator,value',[('is_null',''),('contains','xe lăn')])
def test_coordinated_information_output_is_not_a_filter(operator,value):
    ts=[dict(status='answer',operation='select',request_text='Liệt kê tên miễn phí cùng thông tin tiếp cận bằng xe lăn trong bảng',
        bindings=[dict(column='access',requested_text='thông tin tiếp cận bằng xe lăn')],
        filters=[dict(column='price',operator='eq',value='0'),dict(column='access',operator=operator,value=value)])]
    assert discard_output_only_filters(ts)
    assert ts[0]['filters']==[dict(column='price',operator='eq',value='0')]


def test_explicit_filter_outside_output_phrase_is_retained():
    ts=[dict(status='answer',operation='select',request_text='Hiển thị tên và thông tin access; chỉ lấy access chứa accessible',
        bindings=[dict(column='access',requested_text='thông tin access')],
        filters=[dict(column='access',operator='contains',value='accessible')])]
    assert discard_output_only_filters(ts)==[]


def test_ordinary_in_table_is_not_a_missing_value_request(table):
    t=tasks()[0]; t.update(request_text='Có bao nhiêu dòng trong bảng',filters=[dict(column='score',operator='is_null',value='')])
    with pytest.raises(ValueError,match='NULL_FILTER_REQUIRES_EXPLICIT_MISSING_REQUEST'):
        checked_plan(t,table,t['request_text'])
