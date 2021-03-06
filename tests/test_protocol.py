############################################################################
# Copyright(c) Open Law Library. All rights reserved.                      #
# See ThirdPartyNotices.txt in the project root for additional notices.    #
#                                                                          #
# Licensed under the Apache License, Version 2.0 (the "License")           #
# you may not use this file except in compliance with the License.         #
# You may obtain a copy of the License at                                  #
#                                                                          #
#     http: // www.apache.org/licenses/LICENSE-2.0                         #
#                                                                          #
# Unless required by applicable law or agreed to in writing, software      #
# distributed under the License is distributed on an "AS IS" BASIS,        #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. #
# See the License for the specific language governing permissions and      #
# limitations under the License.                                           #
############################################################################
import json
from concurrent.futures import Future

import pytest
from pygls.exceptions import JsonRpcException
from pygls.protocol import (JsonRPCNotification, JsonRPCRequestMessage,
                            JsonRPCResponseMessage, deserialize_message,
                            to_lsp_name)
from pygls.types import InitializeResult


class dictToObj:
    def __init__(self, entries):
        self.__dict__.update(**entries)


def test_deserialize_message_with_reserved_words_should_pass_without_errors(client_server):
    params = '''
    {
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {
            "__dummy__": true
        }
    }
    '''
    result = deserialize_message(params)

    assert isinstance(result, JsonRPCNotification)
    assert result.params._0 is True


def test_deserialize_message_should_return_notification_message():
    params = '''
    {
        "jsonrpc": "2.0",
        "method": "test",
        "params": "1"
    }
    '''
    result = deserialize_message(params)

    assert isinstance(result, JsonRPCNotification)
    assert result.jsonrpc == "2.0"
    assert result.method == "test"
    assert result.params == "1"


def test_deserialize_message_without_jsonrpc_field__should_return_object():
    params = '''
    {
        "random": "data",
        "def": "def"
    }
    '''
    result = deserialize_message(params)

    assert type(result).__name__ == 'Object'
    assert result.random == "data"

    # namedtuple does not guarantee field order
    try:
        assert result._0 == "def"
    except AttributeError:
        assert result._1 == "def"


def test_deserialize_message_should_return_response_message():
    params = '''
    {
        "jsonrpc": "2.0",
        "id": "id",
        "result": "1"
    }
    '''
    result = deserialize_message(params)

    assert isinstance(result, JsonRPCResponseMessage)
    assert result.jsonrpc == "2.0"
    assert result.id == "id"
    assert result.result == "1"
    assert result.error is None


def test_deserialize_message_should_return_request_message():
    params = '''
    {
        "jsonrpc": "2.0",
        "id": "id",
        "method": "test",
        "params": "1"
    }
    '''
    result = deserialize_message(params)

    assert isinstance(result, JsonRPCRequestMessage)
    assert result.jsonrpc == "2.0"
    assert result.id == "id"
    assert result.method == "test"
    assert result.params == "1"


def test_deserialize_message_should_not_error_on_nested_jsonrpc_object():
    params = '''
    [
        {
            "jsonrpc": "-1",
            "content": "unexpected"
        }
    ]
    '''
    result = deserialize_message(params)

    assert isinstance(result, list)
    obj, = result
    assert type(obj).__name__ == "Object"
    assert obj.jsonrpc == "-1"
    assert obj.content == "unexpected"


def test_data_received_without_content_type_should_handle_message(client_server):
    _, server = client_server
    body = json.dumps({
        "jsonrpc": "2.0",
        "method": "test",
        "params": 1,
    })
    message = '\r\n'.join((
        'Content-Length: ' + str(len(body)),
        '',
        body,
    ))
    data = bytes(message, 'utf-8')
    server.lsp.data_received(data)


def test_data_received_content_type_first_should_handle_message(client_server):
    _, server = client_server
    body = json.dumps({
        "jsonrpc": "2.0",
        "method": "test",
        "params": 1,
    })
    message = '\r\n'.join((
        'Content-Type: application/vscode-jsonrpc; charset=utf-8',
        'Content-Length: ' + str(len(body)),
        '',
        body,
    ))
    data = bytes(message, 'utf-8')
    server.lsp.data_received(data)


def dummy_message(param=1):
    body = json.dumps({
        "jsonrpc": "2.0",
        "method": "test",
        "params": param,
    })
    message = '\r\n'.join((
        'Content-Length: ' + str(len(body)),
        'Content-Type: application/vscode-jsonrpc; charset=utf-8',
        '',
        body,
    ))
    return bytes(message, 'utf-8')


def test_data_received_single_message_should_handle_message(client_server):
    _, server = client_server
    data = dummy_message()
    server.lsp.data_received(data)


def test_data_received_partial_message_should_handle_message(client_server):
    _, server = client_server
    data = dummy_message()
    partial = len(data) - 5
    server.lsp.data_received(data[:partial])
    server.lsp.data_received(data[partial:])


def test_data_received_multi_message_should_handle_messages(client_server):
    _, server = client_server
    messages = (dummy_message(i) for i in range(3))
    data = b''.join(messages)
    server.lsp.data_received(data)


def test_data_received_error_should_raise_jsonrpc_error(client_server):
    _, server = client_server
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": "err",
        "error": {
            "code": -1,
            "message": "message for you sir",
        },
    })
    message = '\r\n'.join([
        'Content-Length: ' + str(len(body)),
        'Content-Type: application/vscode-jsonrpc; charset=utf-8',
        '',
        body,
    ]).encode("utf-8")
    future = server.lsp._server_request_futures["err"] = Future()
    server.lsp.data_received(message)
    with pytest.raises(JsonRpcException, match="message for you sir"):
        future.result()


def test_initialize_without_capabilities_should_raise_error(client_server):
    _, server = client_server
    params = dictToObj({
        "processId": 1234,
        "rootUri": None
    })
    with pytest.raises(Exception):
        server.lsp.bf_initialize(params)


def test_initialize_without_process_id_should_raise_error(client_server):
    _, server = client_server
    params = dictToObj({
        "capabilities": {},
        "rootUri": None
    })
    with pytest.raises(Exception):
        server.lsp.bf_initialize(params)


def test_initialize_without_root_uri_should_raise_error(client_server):
    _, server = client_server
    params = dictToObj({
        "capabilities": {},
        "processId": 1234,
    })
    with pytest.raises(Exception):
        server.lsp.bf_initialize(params)


def test_initialize_should_return_server_capabilities(client_server):
    _, server = client_server
    params = dictToObj({
        "capabilities": {},
        "processId": 1234,
        "rootUri": None
    })

    server_capabilities = server.lsp.bf_initialize(params)

    assert isinstance(server_capabilities, InitializeResult)


def test_response_object_fields():
    # Result field set
    response = JsonRPCResponseMessage(0, '2.0', 'result', None).without_none_fields()

    assert hasattr(response, 'id')
    assert hasattr(response, 'jsonrpc')
    assert hasattr(response, 'result')
    assert not hasattr(response, 'error')

    # Error field set
    response = JsonRPCResponseMessage(0, '2.0', None, 'error').without_none_fields()

    assert hasattr(response, 'id')
    assert hasattr(response, 'jsonrpc')
    assert hasattr(response, 'error')
    assert not hasattr(response, 'result')


def test_to_lsp_name():
    f_name = 'text_document__did_open'
    name = 'textDocument/didOpen'

    assert to_lsp_name(f_name) == name
