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


def microsoft_player(event):
    # Only API Gateway's JWT authorizer can populate this trusted context.
    # The route verifies the signature, expiry, audience and delegated scope.
    tenant = os.environ.get('MICROSOFT_TENANT_ID')
    client = os.environ.get('MICROSOFT_CLIENT_ID')
    audience = os.environ.get('MICROSOFT_API_APP_ID')
    if not (tenant and client and audience):
        return None
    claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
    if not isinstance(claims, dict):
        return None
    scope = claims.get('scp')
    identity = claims.get('oid')
    if (claims.get('iss') != f'https://login.microsoftonline.com/{tenant}/v2.0'
            or claims.get('tid') != tenant or claims.get('ver') != '2.0'
            or claims.get('aud') != audience or claims.get('azp') != client
            or not isinstance(scope, str) or 'Cube.Online' not in scope.split()
            or not isinstance(identity, str) or not identity):
        return None
    return hashlib.sha256(f'{tenant}:{identity}'.encode()).hexdigest()


def handler(event, context):
    if time.time() >= float(os.environ['TEST_DEADLINE']):
        return response(410, {'error': 'This test has ended.'})
    player = microsoft_player(event)
    if player is None:
        return response(401, {'error': 'Sign in with Microsoft to play online.'})
    session = os.environ.get('GAME_SESSION_ID', '')
    if not session:
        return response(503, {'error': 'Game server is not ready.'})
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

