"""Backend service adapter; invoke ONLY after verifying the caller's Cognito access JWT.

Does not create fleets/sessions or deploy an HTTP service. Server-only dependency: boto3.
"""
import hashlib
import re


class Reservations:
    def __init__(self, client, fleet_id):
        self.client, self.fleet_id = client, fleet_id

    @classmethod
    def from_environment(cls):
        import os
        import boto3
        from botocore.config import Config
        client = boto3.Session(region_name=os.environ['AWS_REGION']).client('gamelift',
            config=Config(connect_timeout=5, read_timeout=10, retries={'mode': 'standard', 'total_max_attempts': 2}))
        return cls(client, os.environ['GAMELIFT_FLEET_ID'])

    def reserve_verified_player(self, verified_sub):
        if not isinstance(verified_sub, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', verified_sub):
            raise ValueError('Verified Cognito subject required.')
        # Identity comes from verified claims, NEVER a player ID supplied by the client.
        player = hashlib.sha256(verified_sub.encode()).hexdigest()
        sessions = self.client.search_game_sessions(FleetId=self.fleet_id,
            FilterExpression='hasAvailablePlayerSessions=true', Limit=1).get('GameSessions', [])
        if not sessions:
            raise RuntimeError('No active games with free slots. Try later.')
        session = self.client.create_player_session(GameSessionId=sessions[0]['GameSessionId'], PlayerId=player)['PlayerSession']
        if not session.get('DnsName'):
            raise RuntimeError('Fleet TLS certificate/DNS configuration required.')
        return {'protocol': 'cube-json-tls-v1', 'dns_name': session['DnsName'], 'port': session['Port'],
            'player_session_id': session['PlayerSessionId']}
