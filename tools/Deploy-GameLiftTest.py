"""Bounded test deployment. No fleets are created until cleanup is armed.

Uses the authenticated AWS CLI; stores only non-secret resource IDs in build/.
"""
import argparse
import hashlib
from datetime import datetime, timezone, timedelta
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REGION = 'ca-central-1'
ACCOUNT = '021891613113'
CLIENT = 'q2u1oorqn5lt2v89abisrg7rv'
POOL = 'ca-central-1_KqtmaZCPv'
AWS = shutil.which('aws')


def aws(service, operation, **parameters):
    print('AWS: '+service+' '+operation, flush=True)
    command = [AWS, service, operation, '--region', REGION, '--no-cli-pager', '--cli-connect-timeout', '5', '--cli-read-timeout', '30']
    if parameters:
        command += ['--cli-input-json', json.dumps(parameters)]
    started = time.monotonic()
    process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        try:
            stdout, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            # A suspended desktop can jump past the timeout before Windows lets
            # the CLI finish. Give that owned process one bounded resume grace.
            if time.monotonic()-started <= 240:
                raise
            print('Long desktop delay detected; allowing 30 seconds for the CLI to finish.', flush=True)
            stdout, stderr = process.communicate(timeout=30)
    except BaseException:
        process.kill()
        process.communicate()
        raise
    if process.returncode:
        raise RuntimeError(f'{service} {operation}: {stderr.strip()}')
    return json.loads(stdout) if stdout.strip() else {}


def write_state(folder, state):
    (folder/'resources.json').write_text(json.dumps(state, indent=2), encoding='utf-8')


def generated_policy(file):
    command = ['uvx', '--offline', 'iam-policy-autopilot==0.3.0', 'generate-policies', str(ROOT/'multiplayer_backend'/file),
        '--region', REGION, '--account', ACCOUNT, '--service-hints', 'gamelift', 'apigatewayv2', '--pretty']
    environment = dict(os.environ, DISABLE_IAM_POLICY_AUTOPILOT_TELEMETRY='true')
    result = subprocess.run(command, text=True, capture_output=True, env=environment, timeout=180)
    if result.returncode:
        raise RuntimeError('IAM policy generation failed: '+result.stderr)
    output = json.loads(result.stdout)
    policies = [item['Policy'] for item in output['Policies']]
    policy = {'Version': '2012-10-17', 'Statement': [statement for item in policies for statement in item['Statement']]}
    # Autopilot supplies actions; restrict API management to HTTP APIs in this region.
    for statement in policy['Statement']:
        actions = statement.get('Action', [])
        if actions and all(action.startswith('apigateway:') for action in actions):
            statement['Resource'] = [f'arn:aws:apigateway:{REGION}::/apis', f'arn:aws:apigateway:{REGION}::/apis/*']
    return policy


def role(name, policy):
    trust = {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]}
    result = aws('iam', 'create-role', RoleName=name, AssumeRolePolicyDocument=json.dumps(trust),
        Description='Cube Beta approved two-hour GameLift test')
    aws('iam', 'put-role-policy', RoleName=name, PolicyName='GeneratedGameRuntime', PolicyDocument=json.dumps(policy))
    aws('iam', 'attach-role-policy', RoleName=name,
        PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')
    return result['Role']['Arn']


def lambda_package(source, folder):
    archive = folder/(source+'.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(ROOT/'multiplayer_backend'/(source+'.py'), source+'.py')
    return archive


def function(name, role_arn, source, variables, folder):
    archive = lambda_package(source, folder)
    # CLI JSON cannot contain raw zip bytes; use the CLI's binary-file argument.
    parameters = {'FunctionName': name, 'Runtime': 'python3.12', 'Role': role_arn, 'Handler': source+'.handler',
        'Timeout': 30, 'MemorySize': 128, 'Environment': {'Variables': variables},
        'Tags': {'Project': 'CubeBetaTwoHourTest'}}
    command = [AWS, 'lambda', 'create-function', '--region', REGION, '--no-cli-pager',
        '--cli-input-json', json.dumps(parameters), '--zip-file', 'fileb://'+str(archive)]
    for attempt in range(8):
        result = subprocess.run(command, text=True, capture_output=True, timeout=90)
        if not result.returncode:
            return json.loads(result.stdout)['FunctionArn']
        if 'cannot be assumed' not in result.stderr or attempt == 7:
            raise RuntimeError(result.stderr)
        time.sleep(5)


def wait_function(name):
    for _ in range(30):
        result = aws('lambda', 'get-function-configuration', FunctionName=name)
        if result.get('State') == 'Active' and result.get('LastUpdateStatus', 'Successful') == 'Successful':
            return
        if result.get('State') == 'Failed' or result.get('LastUpdateStatus') == 'Failed':
            raise RuntimeError('Lambda activation/update failed')
        time.sleep(2)
    raise RuntimeError('Lambda activation timed out')


def verify_shutdown(state, folder):
    schedule = aws('scheduler', 'get-schedule', Name=state['schedule_name'], GroupName=state['schedule_group'])
    expected = 'at('+datetime.fromtimestamp(float(state['deadline_epoch']), timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+')'
    if schedule['State'] != 'ENABLED' or schedule['Target']['Arn'] != state['stop_function_arn'] or schedule['ScheduleExpression'] != expected:
        raise RuntimeError('Automatic shutdown schedule verification failed; no fleet will be started.')
    output = folder/'shutdown-preflight.json'
    result = subprocess.run([AWS, 'lambda', 'invoke', '--region', REGION, '--no-cli-pager',
        '--function-name', state['stop_function_name'], str(output)], text=True, capture_output=True, timeout=180)
    if result.returncode or json.loads(result.stdout).get('FunctionError'):
        raise RuntimeError('Shutdown Lambda preflight failed: '+result.stderr)
    if json.loads(output.read_text(encoding='utf-8')) != {'state': 'armed'}:
        raise RuntimeError('Shutdown guard did not report armed; no fleet will be started.')
    print('Verified enabled AWS shutdown schedule and Lambda guard.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['prepare', 'start', 'refresh-start', 'retry', 'prepare-retry'], required=True)
    parser.add_argument('--state-dir', default='build/gamelift-test-deployment')
    parser.add_argument('--reuse-build', help='Previously verified GameLift Linux build ID; avoids another upload.')
    parser.add_argument('--deadline-epoch', type=float, help='Keep an existing approved test deadline for an in-window retry.')
    parser.add_argument('--server-payload', default='build/gamelift-linux-server')
    parser.add_argument('--resume-preparation', action='store_true', help='Resume only an interrupted preparation with no recorded resources.')
    args = parser.parse_args()
    folder = (ROOT/args.state_dir).resolve()
    if ROOT not in folder.parents:
        raise ValueError('Deployment state must be in the repository build directory.')
    folder.mkdir(parents=True, exist_ok=True)
    if not (ROOT/'dedicated_server'/'cube-server').is_file():
        raise RuntimeError('Linux dedicated host must be compiled before any deployment.')
    proof = json.loads((ROOT/'build'/'dedicated-tls-qa'/'success.json').read_text(encoding='utf-8'))
    if not proof.get('two_tls_players') or proof['server_sha256'] != hashlib.sha256((ROOT/'dedicated_server'/'cube-server.exe').read_bytes()).hexdigest():
        raise RuntimeError('Current local server must pass the two-player TLS test first.')
    identity = aws('sts', 'get-caller-identity')
    if identity['Account'] != ACCOUNT:
        raise RuntimeError('AWS account does not match approved test.')
    if args.phase == 'prepare':
        if (folder/'resources.json').exists():
            if not args.resume_preparation:
                raise RuntimeError('Existing test state found. Inspect it instead of creating duplicate resources.')
            state = json.loads((folder/'resources.json').read_text(encoding='utf-8'))
            if state.get('roles') or state.get('stop_function_arn') or state.get('fleet_id') or state['account'] != ACCOUNT:
                raise RuntimeError('Preparation recorded resources; inspect them instead of automatically resuming.')
            deadline = datetime.fromtimestamp(float(state['deadline_epoch']), timezone.utc)
            if deadline.timestamp()-time.time() < 3600:
                raise RuntimeError('Too little approved time remains to resume preparation.')
            prefix = state['prefix']
        else:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            prefix = 'CubeBetaTest-'+stamp
            deadline = (datetime.now(timezone.utc)+timedelta(hours=2)).replace(microsecond=0)
            if args.deadline_epoch is not None:
                if not time.time()+1800 < args.deadline_epoch <= deadline.timestamp():
                    raise RuntimeError('Retry deadline must be unexpired and cannot extend the two-hour approved window.')
                deadline = datetime.fromtimestamp(args.deadline_epoch, timezone.utc).replace(microsecond=0)
            state = {'region': REGION, 'account': ACCOUNT, 'prefix': prefix, 'deadline': deadline.isoformat(),
                'deadline_epoch': str(deadline.timestamp()), 'fleet_name': prefix, 'roles': []}
        write_state(folder, state)
        print('Creating test-only shutdown control; no fleet capacity yet.', flush=True)
        cleanup_policy = generated_policy('test_shutdown.py')
        (folder/'shutdown-policy.json').write_text(json.dumps(cleanup_policy, indent=2), encoding='utf-8')
        stop_role_name = prefix+'-StopRole'
        stop_role = role(stop_role_name, cleanup_policy)
        state['roles'].append(stop_role_name)
        state['stop_role_arn'] = stop_role
        state['stop_function_name'] = prefix+'-Stop'
        write_state(folder, state)
        variables = {'TEST_DEADLINE': state['deadline_epoch'], 'TEST_FLEET_NAME': prefix, 'TEST_FLEET_ID': '',
            'TEST_API_NAME': prefix+'-Api'}
        stop_arn = function(state['stop_function_name'], stop_role, 'test_shutdown', variables, folder)
        state['stop_function_arn'] = stop_arn
        write_state(folder, state)
        wait_function(state['stop_function_name'])
        # Scheduler invokes only this one shutdown function.
        group = aws('scheduler', 'create-schedule-group', Name=prefix)
        state['schedule_group'] = prefix
        schedule_trust = {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow',
            'Principal': {'Service': 'scheduler.amazonaws.com'}, 'Action': 'sts:AssumeRole',
            'Condition': {'StringEquals': {'aws:SourceAccount': ACCOUNT}, 'ArnEquals': {'aws:SourceArn': group['ScheduleGroupArn']}}}]}
        schedule_role_name = prefix+'-ScheduleRole'
        schedule_role = aws('iam', 'create-role', RoleName=schedule_role_name,
            AssumeRolePolicyDocument=json.dumps(schedule_trust))['Role']['Arn']
        state['roles'].append(schedule_role_name)
        schedule_policy = {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Action': 'lambda:InvokeFunction', 'Resource': stop_arn}]}
        aws('iam', 'put-role-policy', RoleName=schedule_role_name, PolicyName='InvokeOnlyTestShutdown', PolicyDocument=json.dumps(schedule_policy))
        time.sleep(5)
        aws('scheduler', 'create-schedule', Name=prefix+'-Deadline', GroupName=prefix,
            ScheduleExpression='at('+deadline.strftime('%Y-%m-%dT%H:%M:%S')+')', ScheduleExpressionTimezone='UTC',
            FlexibleTimeWindow={'Mode': 'OFF'}, ActionAfterCompletion='DELETE',
            Target={'Arn': stop_arn, 'RoleArn': schedule_role, 'Input': '{}',
                'RetryPolicy': {'MaximumEventAgeInSeconds': 3600, 'MaximumRetryAttempts': 3}})
        state['shutdown_armed'] = True
        state['schedule_name'] = prefix+'-Deadline'
        write_state(folder, state)
        verify_shutdown(state, folder)
        print('Shutdown armed for '+deadline.isoformat()+'. No fleet created.', flush=True)
        return
    state = json.loads((folder/'resources.json').read_text(encoding='utf-8'))
    if args.phase in ('retry', 'prepare-retry'):
        if state.get('status') != 'failed-delete-requested' or state.get('api_id') or state.get('game_session_id'):
            raise RuntimeError('Only a failed pre-game-session test can use the in-window retry.')
        if float(state['deadline_epoch'])-time.time() < 1800:
            raise RuntimeError('Too little of the original window remains for another attempt.')
        old = aws('gamelift', 'describe-fleet-attributes', FleetIds=[state['fleet_id']])['FleetAttributes']
        allowed_prior_states = ('TERMINATED', 'DELETING') if args.phase == 'prepare-retry' else ('TERMINATED',)
        if old and old[0].get('Status') not in allowed_prior_states:
            raise RuntimeError('Previous fleet has not finished deleting; refused replacement capacity.')
        control_role = aws('iam', 'get-role', RoleName=state['roles'][0])['Role']
        if control_role['Arn'] != state['stop_role_arn'] or any(
            tag['Key'].startswith('aws:cloudformation:') or tag.get('Value', '').lower() == 'terraform'
            for tag in control_role.get('Tags', [])):
            raise RuntimeError('Shutdown role ownership/management changed; refused automatic modification.')
        # Reuse this test's controls and ORIGINAL deadline, never start a new window.
        policy = json.loads((folder/'shutdown-policy.json').read_text(encoding='utf-8'))
        aws('iam', 'put-role-policy', RoleName=state['roles'][0], PolicyName='GeneratedGameRuntime', PolicyDocument=json.dumps(policy))
        aws('lambda', 'update-function-configuration', FunctionName=state['stop_function_name'], Environment={'Variables': {
            'TEST_DEADLINE': state['deadline_epoch'], 'TEST_FLEET_NAME': state['fleet_name'],
            'TEST_FLEET_ID': '', 'TEST_API_NAME': state['prefix']+'-Api'}})
        wait_function(state['stop_function_name'])
        state.setdefault('previous_attempts', []).append({key: state.get(key) for key in ('fleet_id', 'fleet_arn', 'build_id')})
        for key in ('fleet_id', 'fleet_arn', 'build_id'):
            state.pop(key, None)
        state['status'] = 'retry-prepared'
        write_state(folder, state)
        print('Retry controls reset without extending '+state['deadline'], flush=True)
        if args.phase == 'prepare-retry':
            verify_shutdown(state, folder)
            print('Retry prepared only. No fleet capacity created; earlier deletion must finish before start.', flush=True)
            return
    if not state.get('shutdown_armed') or state.get('fleet_id'):
        raise RuntimeError('A fresh armed shutdown is required; this state cannot start another fleet.')
    if args.phase == 'refresh-start':
        if state.get('window_refreshed'):
            raise RuntimeError('The unused window was already refreshed; inspect the deployment before proceeding.')
        # Only refresh a window that has NEVER started capacity. An approval delay
        # must not produce a running fleet whose safety deadline already expired.
        page = aws('gamelift', 'describe-fleet-attributes')
        if page.get('NextToken') or any(item.get('Name') == state['fleet_name'] for item in page.get('FleetAttributes', [])):
            raise RuntimeError('Cannot prove this deployment has no fleet; refused to extend the window.')
        deadline = (datetime.now(timezone.utc)+timedelta(hours=2)).replace(microsecond=0)
        variables = {'TEST_DEADLINE': str(deadline.timestamp()), 'TEST_FLEET_NAME': state['fleet_name'],
            'TEST_FLEET_ID': '', 'TEST_API_NAME': state['prefix']+'-Api'}
        aws('lambda', 'update-function-configuration', FunctionName=state['stop_function_name'], Environment={'Variables': variables})
        wait_function(state['stop_function_name'])
        existing = aws('scheduler', 'get-schedule', Name=state['schedule_name'], GroupName=state['schedule_group'])
        expression = 'at('+deadline.strftime('%Y-%m-%dT%H:%M:%S')+')'
        aws('scheduler', 'update-schedule', Name=state['schedule_name'], GroupName=state['schedule_group'],
            ScheduleExpression=expression, ScheduleExpressionTimezone='UTC', State='ENABLED',
            FlexibleTimeWindow={'Mode': 'OFF'}, ActionAfterCompletion='DELETE', Target=existing['Target'])
        verified = aws('scheduler', 'get-schedule', Name=state['schedule_name'], GroupName=state['schedule_group'])
        if verified['State'] != 'ENABLED' or verified['ScheduleExpression'] != expression or verified['Target']['Arn'] != state['stop_function_arn']:
            raise RuntimeError('Refreshed shutdown verification failed; no fleet will be started.')
        state.update(deadline=deadline.isoformat(), deadline_epoch=str(deadline.timestamp()), window_refreshed=True)
        write_state(folder, state)
        print('Unused shutdown window refreshed: '+state['deadline'], flush=True)
    verify_shutdown(state, folder)
    if float(state['deadline_epoch'])-time.time() < 1800:
        raise RuntimeError('Insufficient time remaining on the shutdown schedule. Do not start capacity.')
    payload = (ROOT/args.server_payload).resolve()
    if ROOT/'build' not in payload.parents:
        raise ValueError('Server payload must stay under the repository build directory.')
    if not (payload/'cube-server').is_file():
        raise RuntimeError('Allowlisted Linux server payload is missing.')
    if args.reuse_build:
        existing = aws('gamelift', 'describe-build', BuildId=args.reuse_build)['Build']
        if existing['Status'] != 'READY' or existing['OperatingSystem'] != 'AMAZON_LINUX_2023' or existing['ServerSdkVersion'] != '5.6.0':
            raise RuntimeError('Reusable build does not match the verified Linux SDK configuration.')
        state['build_id'] = existing['BuildId']
        print('Reusing the uploaded Linux server build; no running instances yet.', flush=True)
    else:
        print('Uploading the dedicated server build; no running instances yet.', flush=True)
        command = [AWS, 'gamelift', 'upload-build', '--region', REGION, '--no-cli-pager',
            '--name', state['prefix'], '--build-version', 'halloween-cpe-test-1', '--build-root', str(payload),
            '--operating-system', 'AMAZON_LINUX_2023', '--server-sdk-version', '5.6.0']
        upload = subprocess.run(command, text=True, capture_output=True, timeout=900)
        if upload.returncode:
            raise RuntimeError('Build upload failed: '+upload.stderr)
        # upload-build is a CLI customization: its result is progress text, not JSON.
        match = re.search(r'Build ID:\s*(build-[a-f0-9-]+)', upload.stdout)
        if not match:
            raise RuntimeError('Upload completed without a recognizable build ID; inspect builds before retrying.')
        state['build_id'] = match.group(1)
    write_state(folder, state)
    for _ in range(120):
        build = aws('gamelift', 'describe-build', BuildId=state['build_id'])['Build']
        if build['Status'] == 'READY':
            break
        if build['Status'] == 'FAILED':
            raise RuntimeError('GameLift build processing failed; no fleet capacity started.')
        time.sleep(3)
    else:
        raise RuntimeError('Build processing timed out; no fleet capacity started.')
    if float(state['deadline_epoch'])-time.time() < 1800:
        raise RuntimeError('Upload consumed the test window; no fleet capacity started.')
    prior_fleets = aws('gamelift', 'describe-fleet-attributes')
    if prior_fleets.get('NextToken') or any(
        item.get('Name', '').startswith('CubeBetaTest-') and item.get('Status') != 'TERMINATED'
        for item in prior_fleets.get('FleetAttributes', [])):
        raise RuntimeError('An earlier test fleet still exists; wait for its removal before creating replacement capacity.')
    print('Build ready. Creating one capped Linux c5.large test instance.', flush=True)
    fleet_id = None
    try:
        fleet = aws('gamelift', 'create-fleet', Name=state['fleet_name'], BuildId=state['build_id'],
            EC2InstanceType='c5.large', FleetType='ON_DEMAND', CertificateConfiguration={'CertificateType': 'GENERATED'},
            NewGameSessionProtectionPolicy='NoProtection',
            EC2InboundPermissions=[{'FromPort': 27100, 'ToPort': 27100, 'IpRange': '0.0.0.0/0', 'Protocol': 'TCP'}],
            RuntimeConfiguration={'ServerProcesses': [{'LaunchPath': '/local/game/cube-server',
                'Parameters': '--python /local/game/venv/bin/python --worker /local/game/worker.py --port 27100', 'ConcurrentExecutions': 1}],
                'MaxConcurrentGameSessionActivations': 1, 'GameSessionActivationTimeoutSeconds': 120},
            Tags=[{'Key': 'Project', 'Value': state['prefix']}])['FleetAttributes']
        fleet_id = fleet['FleetId']
        state['fleet_id'], state['fleet_arn'] = fleet_id, fleet['FleetArn']
        write_state(folder, state)
        # Immediately point the pre-existing shutdown function at this exact new fleet.
        variables = {'TEST_DEADLINE': state['deadline_epoch'], 'TEST_FLEET_NAME': state['fleet_name'], 'TEST_FLEET_ID': fleet_id,
            'TEST_API_NAME': state['prefix']+'-Api'}
        aws('lambda', 'update-function-configuration', FunctionName=state['stop_function_name'], Environment={'Variables': variables})
        wait_function(state['stop_function_name'])
        # Narrow the generated DeleteFleet statement from this region's fleet pattern to the actual test ARN.
        stop_policy = json.loads((folder/'shutdown-policy.json').read_text(encoding='utf-8'))
        for statement in stop_policy['Statement']:
            actions = statement.get('Action', [])
            if actions == ['gamelift:DeleteFleet'] or actions == 'gamelift:DeleteFleet':
                statement['Resource'] = [state['fleet_arn']]
        aws('iam', 'put-role-policy', RoleName=state['roles'][0], PolicyName='GeneratedGameRuntime', PolicyDocument=json.dumps(stop_policy))
        print('Shutdown has the exact fleet ID and deletion permission.', flush=True)
        ready = False
        last = ''
        for _ in range(240):
            if time.time() > float(state['deadline_epoch'])-600:
                raise RuntimeError('Too little test time remains; stopping fleet rather than extending the paid window.')
            attributes = aws('gamelift', 'describe-fleet-attributes', FleetIds=[fleet_id])['FleetAttributes']
            if not attributes:
                raise RuntimeError('Test fleet no longer exists; stopped before creating any replacement.')
            info = attributes[0]
            if info['Status'] != last:
                last = info['Status']; print('Fleet status: '+last, flush=True)
            if last == 'ACTIVE':
                ready = True; break
            if last in ('ERROR', 'TERMINATED'):
                events = aws('gamelift', 'describe-fleet-events', FleetId=fleet_id, Limit=30)
                # Keep signed log URLs out of terminal output; retain local diagnostics.
                (folder/'fleet-failure-events.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
                print('Fleet event codes: '+', '.join(event.get('EventCode', '') for event in events.get('Events', [])), flush=True)
                raise RuntimeError('Fleet setup failed: '+last)
            time.sleep(5)
        if not ready:
            raise RuntimeError('Fleet activation timed out.')
        aws('gamelift', 'update-fleet-capacity', FleetId=fleet_id, DesiredInstances=1, MinSize=0, MaxSize=1)
        session = aws('gamelift', 'create-game-session', FleetId=fleet_id, MaximumPlayerSessionCount=4,
            Name='Halloween shared CPE sandbox')['GameSession']
        state['game_session_id'] = session['GameSessionId']
        write_state(folder, state)
        print('Game session created. Preparing authenticated reservation API.', flush=True)
        api_role_name = state['prefix']+'-ApiRole'
        api_role = role(api_role_name, generated_policy('session_api.py'))
        state['roles'].append(api_role_name)
        state['api_function_name'] = state['prefix']+'-Reserve'
        api_function = function(state['api_function_name'], api_role, 'session_api',
            {'TEST_DEADLINE': state['deadline_epoch'], 'COGNITO_CLIENT_ID': CLIENT, 'GAME_SESSION_ID': state['game_session_id']}, folder)
        wait_function(state['api_function_name'])
        api = aws('apigatewayv2', 'create-api', Name=state['prefix']+'-Api', ProtocolType='HTTP')
        state['api_id'], state['backend_url'] = api['ApiId'], api['ApiEndpoint']
        write_state(folder, state)
        for statement in stop_policy['Statement']:
            if 'apigateway:DELETE' in statement.get('Action', []):
                statement['Resource'] = [f'arn:aws:apigateway:{REGION}::/apis', f'arn:aws:apigateway:{REGION}::/apis/{api["ApiId"]}']
        aws('iam', 'put-role-policy', RoleName=state['roles'][0], PolicyName='GeneratedGameRuntime', PolicyDocument=json.dumps(stop_policy))
        auth = aws('apigatewayv2', 'create-authorizer', ApiId=api['ApiId'], Name='NuttyincCloud', AuthorizerType='JWT',
            IdentitySource=['$request.header.Authorization'], JwtConfiguration={'Audience': [CLIENT],
                'Issuer': 'https://cognito-idp.'+REGION+'.amazonaws.com/'+POOL})
        integration = aws('apigatewayv2', 'create-integration', ApiId=api['ApiId'], IntegrationType='AWS_PROXY',
            IntegrationUri=api_function, PayloadFormatVersion='2.0', TimeoutInMillis=25000)
        aws('apigatewayv2', 'create-route', ApiId=api['ApiId'], RouteKey='POST /sessions/reserve',
            AuthorizationType='JWT', AuthorizerId=auth['AuthorizerId'], AuthorizationScopes=['openid'],
            Target='integrations/'+integration['IntegrationId'])
        aws('lambda', 'add-permission', FunctionName=state['api_function_name'], StatementId='OnlyThisApi',
            Action='lambda:InvokeFunction', Principal='apigateway.amazonaws.com', SourceAccount=ACCOUNT,
            SourceArn=f'arn:aws:execute-api:{REGION}:{ACCOUNT}:{api["ApiId"]}/*/POST/sessions/reserve')
        aws('apigatewayv2', 'create-stage', ApiId=api['ApiId'], StageName='$default', AutoDeploy=True,
            DefaultRouteSettings={'ThrottlingBurstLimit': 4, 'ThrottlingRateLimit': 2.0})
        variables.update({'TEST_API_ID': api['ApiId'], 'TEST_API_NAME': state['prefix']+'-Api'})
        aws('lambda', 'update-function-configuration', FunctionName=state['stop_function_name'], Environment={'Variables': variables})
        wait_function(state['stop_function_name'])
        # Read-modify-write the EXISTING client, preserving every accepted field.
        client = aws('cognito-idp', 'describe-user-pool-client', UserPoolId=POOL, ClientId=CLIENT)['UserPoolClient']
        callback = 'http://localhost:8765/callback'
        if callback not in client.get('CallbackURLs', []):
            skeleton = subprocess.run([AWS, 'cognito-idp', 'update-user-pool-client', '--generate-cli-skeleton', 'input'], text=True, capture_output=True, check=True)
            accepted = json.loads(skeleton.stdout)
            parameters = {key: value for key, value in client.items() if key in accepted and value is not None}
            parameters.update({'UserPoolId': POOL, 'ClientId': CLIENT, 'CallbackURLs': client.get('CallbackURLs', [])+[callback]})
            aws('cognito-idp', 'update-user-pool-client', **parameters)
        state['status'] = 'hosting'
        write_state(folder, state)
        print('Hosting prepared: '+state['backend_url']+'; shutdown '+state['deadline'], flush=True)
    except BaseException:
        try:
            if fleet_id:
                print('Deployment failed; requesting deletion of ONLY the new test fleet.', flush=True)
                aws('gamelift', 'delete-fleet', FleetId=fleet_id)
        finally:
            if state.get('api_id'):
                aws('apigatewayv2', 'delete-api', ApiId=state['api_id'])
            state['status'] = 'failed-delete-requested'
            write_state(folder, state)
        raise


if __name__ == '__main__':
    main()
