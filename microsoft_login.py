"""Public-client Microsoft sign-in for Cube Beta's online reservation API."""
from uuid import UUID

CLIENT_ID = 'f34d69f0-add1-412f-8c96-9a5b7ea4aa4b'
TENANT_ID = '8b8c20a6-c2d7-45e0-b24f-15e6cae52c60'
AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
ONLINE_PERMISSION = 'Cube.Online'
GRAPH_APP_ID = '00000003-0000-0000-c000-000000000000'


def api_application_id(value: str) -> str:
    try:
        app_id = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Set microsoft_api_app_id to the Cube Beta Online API application ID.') from None
    if app_id in {CLIENT_ID, GRAPH_APP_ID, str(UUID(int=0))}:
        raise ValueError('Use a separate Cube Beta Online API registration, not the login client or Microsoft Graph.')
    return app_id


def sign_in_online(api_app_id: str) -> str:
    """Return only the scoped access token; never persist it or print MSAL errors."""
    scope = f'api://{api_application_id(api_app_id)}/{ONLINE_PERMISSION}'
    from msal import PublicClientApplication

    auth = PublicClientApplication(CLIENT_ID, authority=AUTHORITY, exclude_scopes=['offline_access'])
    result = auth.acquire_token_interactive(scopes=[scope], prompt='select_account', timeout=120)
    token = result.get('access_token')
    if not isinstance(token, str) or not token:
        raise RuntimeError('Microsoft sign-in did not return an online-play access token.')
    return token
