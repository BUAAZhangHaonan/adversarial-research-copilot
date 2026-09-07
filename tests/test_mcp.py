import asyncio
from decimal import Decimal
from pathlib import Path
import sys
import pytest
from mcp import Client
from mcp.server import MCPServer
from pydantic import BaseModel
from arc.mcp_client import MCPHub, MCPFailure, ServiceConfig, Capability, validate_arguments, model_schema


def test_strict_arguments_and_untrusted_urls():
    schema={'type':'object','properties':{'url':{'type':'string'}},'required':['url']}
    with pytest.raises(MCPFailure,match='UNDECLARED'):validate_arguments(schema,{'url':'https://example.org','issue_id':'x'})
    for url in ['file:///etc/passwd','http://127.0.0.1/x','http://10.1.2.3/x','http://u:p@example.org/x']:
        with pytest.raises(MCPFailure,match='FORBIDDEN'):validate_arguments(schema,{'url':url})
    validate_arguments(schema,{'url':'https://arxiv.org/abs/2409.04109'})
    cleaned=model_schema({'type':'object','description':'external injection','properties':{'title':{'type':'string','description':'secret'}}})
    assert cleaned['properties']['title']=={'type':'string'}
    assert 'description' not in cleaned


@pytest.mark.asyncio
async def test_official_sdk_v2_preserves_structured_result_and_tool_error():
    server=MCPServer('offline-fixture')
    class Result(BaseModel):
        query: str
        title: str
    @server.tool()
    def lookup(query:str)->Result:
        return Result(query=query,title='fixture')
    async with Client(server) as client:
        listing=await client.list_tools()
        assert listing.tools[0].input_schema['required']==['query']
        result=await client.call_tool('lookup',{'query':'abc'})
        assert result.structured_content=={'query':'abc','title':'fixture'}
        error=await client.call_tool('lookup',{})
        assert error.is_error


@pytest.mark.asyncio
async def test_unobservable_cost_blocks_before_session():
    hub=MCPHub([],{})
    hub.capabilities['search_literature']=Capability('search_literature','s','query',
        {'type':'object','properties':{'query':{'type':'string'}},'required':['query']},'metadata',None,'unknown')
    with pytest.raises(MCPFailure,match='COST_UNOBSERVABLE'):
        await hub.call('search_literature',{'query':'hello'})


@pytest.mark.asyncio
@pytest.mark.parametrize('body',["import time; time.sleep(30)","import sys,time; sys.stdout.write('{');sys.stdout.flush();time.sleep(30)","pass"])
async def test_silent_partial_line_and_eof_stdio_terminate(tmp_path,body):
    script=tmp_path/'server.py';script.write_text(body)
    hub=MCPHub([ServiceConfig('silent','stdio',command=sys.executable,args=(str(script),),
                              timeout_seconds=.3,startup_timeout_seconds=.3)],{})
    await asyncio.wait_for(hub.prepare(),timeout=8)
    assert 'silent' in hub.failures


@pytest.mark.asyncio
@pytest.mark.parametrize('silent',[True,False])
async def test_sse_missing_endpoint_and_early_eof_exit(silent):
    writers=[]
    async def serve(reader,writer):
        writers.append(writer)
        await reader.readuntil(b'\r\n\r\n')
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n')
        await writer.drain()
        if silent:await reader.read()
        writer.close()
    server=await asyncio.start_server(serve,'127.0.0.1',0)
    try:
        port=server.sockets[0].getsockname()[1]
        hub=MCPHub([ServiceConfig('sse','sse',url=f'http://127.0.0.1:{port}/sse',
                                  startup_timeout_seconds=.3,timeout_seconds=.3)],{})
        await asyncio.wait_for(hub.prepare(),timeout=5)
        assert 'sse' in hub.failures
    finally:
        server.close();await server.wait_closed()
        for writer in writers:writer.close()
