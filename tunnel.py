import json
import time

import click
import xerox
import requests
import shortuuid
from websocket import create_connection


@click.command(help='Opens a tunnel for development.')
@click.option('--protocol', default='wss')
@click.option('--host', '-h', default='2localhost.com')
@click.option('--port', '-p', default=None)
@click.option('--copy', '-c', is_flag=True)
def tunnel(protocol, host, port, copy):
    ws = create_connection(make_endpoint(protocol, host, port, 'websocket'))

    try:
        while ws.connected:
            message_as_json = ws.recv()

            if message_as_json is not None:
                message = json.loads(message_as_json)
                message_type = message['message_type']

                if message_type == 'init':
                    greeting(message, protocol, host, port, copy)
                elif message_type == 'request':
                    response_message_as_json = forward_request(message)
                    ws.send(response_message_as_json)
                elif message_type == 'ping':
                    pass
                else:
                    click.echo('bad message type {}'.format(message_type))
    except KeyboardInterrupt:
        ws.close()


def make_endpoint(protocol, host, port, path):
    endpoint = protocol + '://' + host
    if port is not None:
        endpoint += ':' + port
    endpoint += '/' + path
    return endpoint


def greeting(message, protocol, host, port, copy):
    client_id = message['client_id']
    client_protocol = 'https' if protocol == 'wss' else 'http'  # FIXME
    client_endpoint = make_endpoint(client_protocol, host, port, client_id)

    click.echo(" * Tunnel has been created at {}".format(client_endpoint))
    if copy:
        xerox.copy(client_endpoint)
        click.echo(" * (Tunnel endpoint copied to clipboard)")


def forward_request(message):
    method = message['method']
    headers = message['headers']
    data = message['data']
    client_id = message['client_id']
    url = 'http://localhost:5000'

    try:
        response = requests.request(method, url, headers=headers, data=data)
        status_code = response.status_code
        content = response.content
        response_message = dict(client_id=client_id, status_code=status_code, content=content)
        return json.dumps(response_message)
    except requests.exceptions.ConnectionError, ex:
        click.echo("Connection to {} could not be established".format(url))


if __name__ == '__main__':
    main()
