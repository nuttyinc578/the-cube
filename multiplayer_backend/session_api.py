"""HTTP API JWT-authorized handler for the bounded GameLift test."""
import hashlib
import json
import os
import time
import boto3
from botocore.config import Config

gamelift = boto3.client('gamelift', config=Config(connect_timeout=4, read_timeout=8,
    retries={'mode': 'standard', 'total_max_attempts': 2}))


def response(status, message):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json', 'Cache-Control': 'no-store'},
        'body': json.dumps(message)}


def handler(event, context):
    if time.time() >= float(os.environ['TEST_DEADLINE']):
        return response(410, {'error': 'This test has ended.'})
    claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
    if claims.get('token_use') != 'access' or claims.get('client_id') != os.environ['COGNITO_CLIENT_ID'] or not claims.get('sub'):
        return response(401, {'error': 'Sign in with Nuttyinc Cloud.'})
    session = os.environ.get('GAME_SESSION_ID', '')
    if not session:
        return response(503, {'error': 'Game server is not ready.'})
    player = hashlib.sha256(str(claims['sub']).encode()).hexdigest()
    try:
        # AWS accepts ONE identity selector, not GameSessionId and PlayerId together.
        # Status filtering bounds results to the four slots in this test session.
        existing = gamelift.describe_player_sessions(GameSessionId=session,
            PlayerSessionStatusFilter='RESERVED', Limit=10)['PlayerSessions']
        reserved = next((p for p in existing if p.get('PlayerId') == player), None)
        if reserved is None:
            active = gamelift.describe_player_sessions(GameSessionId=session,
                PlayerSessionStatusFilter='ACTIVE', Limit=10)['PlayerSessions']
            if any(p.get('PlayerId') == player for p in active):
                return response(409, {'error': 'Already connected. Close the other game window before reconnecting.'})
            reserved = gamelift.create_player_session(GameSessionId=session, PlayerId=player)['PlayerSession']
        if not reserved.get('DnsName'):
            return response(503, {'error': 'TLS game server is not available.'})
        return response(200, {'protocol': 'cube-json-tls-v1', 'dns_name': reserved['DnsName'],
            'port': reserved['Port'], 'player_session_id': reserved['PlayerSessionId']})
    except gamelift.exceptions.GameSessionFullException:
        return response(409, {'error': 'All four player slots are occupied.'})

