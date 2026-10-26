"""Scheduled shutdown for ONLY this deployment's exact fleet/API names and IDs."""
import os
import time
import boto3
from botocore.config import Config

gamelift = boto3.client('gamelift', config=Config(connect_timeout=4, read_timeout=8,
    retries={'mode': 'standard', 'total_max_attempts': 2}))
gateway = boto3.client('apigatewayv2', config=Config(connect_timeout=4, read_timeout=8,
    retries={'mode': 'standard', 'total_max_attempts': 2}))


def handler(event, context):
    # Scheduler has minute-level precision. Accept its deadline-minute invocation
    # instead of missing cleanup because of fractional seconds in deployment state.
    if time.time() < float(os.environ['TEST_DEADLINE']) - 60:
        return {'state': 'armed'}
    fleet = os.environ.get('TEST_FLEET_ID', '')
    if not fleet:
        # Covers interruption between CreateFleet and recording its ID in Lambda.
        matches = [item['FleetId']
            for page in gamelift.get_paginator('describe_fleet_attributes').paginate()
            for item in page.get('FleetAttributes', [])
            if item.get('Name') == os.environ['TEST_FLEET_NAME']]
        if len(matches) > 1:
            raise RuntimeError('Ambiguous test fleet; refused shutdown.')
        if matches:
            fleet = matches[0]
    status = 'deleted' if fleet else 'no-fleet'
    try:
        if fleet:
            fleet_info = gamelift.describe_fleet_attributes(FleetIds=[fleet])['FleetAttributes']
            if fleet_info and fleet_info[0]['Name'] != os.environ['TEST_FLEET_NAME']:
                raise RuntimeError('Fleet identity mismatch; refused shutdown.')
            if fleet_info and fleet_info[0].get('Status') not in ('DELETING', 'TERMINATED'):
                gamelift.delete_fleet(FleetId=fleet)
                status = 'delete-requested'
    except gamelift.exceptions.NotFoundException:
        pass
    api = os.environ.get('TEST_API_ID', '')
    if not api and os.environ.get('TEST_API_NAME'):
        matches = [item['ApiId'] for page in gateway.get_paginator('get_apis').paginate()
            for item in page.get('Items', []) if item.get('Name') == os.environ['TEST_API_NAME']]
        if len(matches) > 1:
            raise RuntimeError('Ambiguous test API; refused cleanup.')
        if matches:
            api = matches[0]
    if api:
        try:
            info = gateway.get_api(ApiId=api)
            if info['Name'] != os.environ['TEST_API_NAME']:
                raise RuntimeError('API identity mismatch; refused cleanup.')
            gateway.delete_api(ApiId=api)
        except gateway.exceptions.NotFoundException:
            pass
    return {'state': status, 'fleet': fleet}
