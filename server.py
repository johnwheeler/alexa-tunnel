import json
import logging

import gevent
import shortuuid
from redis import Redis
from flask import Flask, request
from flask_sockets import Sockets
from geventwebsocket import WebSocketError

app = Flask(__name__)
sockets = Sockets(app)
redis = Redis()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fmt_pattern = "%(levelname)s - %(asctime)s %(filename)s:%(lineno)d %(message)s"
formatter = logging.Formatter(fmt=fmt_pattern)

if app.debug:
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    handler = logging.FileHandler('/var/log/gunicorn/2localhost.log')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@sockets.route('/websocket')
def websocket(ws):
    client_id = 'fixme'  # shortuuid.uuid()[:8]
    request_key = 'req-{}'.format(client_id)
    response_key = 'res-{}'.format(client_id)
    
    # client_id's are usually unique except when testing I'll fix it to something.
    # this makes sure there aren't any lingering items in the queues.
    redis.delete(request_key, response_key)

    try:
        # new client has connected. send client_id
        ws.send(make_init_message(client_id))
        logger.info('client {} connected'.format(client_id))

        # poll for requests to process
        while not ws.closed:
            brpop_result = redis.brpop(request_key, timeout=5)
            if brpop_result is not None:
                _, request_message_json = brpop_result
                ws.send(request_message_json)

                with gevent.Timeout(5, False) as timeout:
                    response_message_json = ws.receive()
                    timeout.cancel()
                    if response_message_json is not None:
                        redis.lpush(response_key, response_message_json)

            ws.send(make_ping_message())
    except WebSocketError:
        logger.info('requests websocket closed for {}'.format(client_id))


@app.route('/<string:client_id>', methods=['GET', 'POST'])
def client_path(client_id):
    # enqueue request
    request_key = 'req-{}'.format(client_id)
    request_message_json = make_request_message(client_id, request)
    redis.lpush(request_key, request_message_json)

    # wait for response to pop
    response_key = 'res-{}'.format(client_id)
    brpop_result = redis.brpop(response_key, timeout=5)
    if brpop_result is not None:
        # brpop is different from rpop. it blocks and returns tuple instead of a single value.
        # the first element is the key of the list popped from. the next element is the value.
        _, response_message_json = brpop_result
        response_message = json.loads(response_message_json)
        status_code = response_message['status_code']
        content = response_message['content']
        return content, status_code
    else:
        redis.delete(request_key)
        return "", 400


@app.route('/test')
def test():
    return "OK"


def make_init_message(client_id):
    message = dict(message_type='init', client_id=client_id)
    return json.dumps(message)


def make_request_message(client_id, request):
    method = request.method
    headers = dict(request.headers.items())
    data = request.data

    message = dict(message_type='request', client_id=client_id,
                   method=method, headers=headers, data=data)
    return json.dumps(message)


def make_ping_message():
    ping_message = dict(message_type='ping')
    return json.dumps(ping_message)
