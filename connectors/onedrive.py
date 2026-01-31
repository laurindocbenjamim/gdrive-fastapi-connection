import os
import msal
import requests
import datetime
from .base import BaseConnector

ONEDRIVE_CLIENT_ID = os.getenv("ONEDRIVE_CLIENT_ID")
ONEDRIVE_CLIENT_SECRET = os.getenv("ONEDRIVE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/auth/onedrive/callback"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Files.Read.All", "User.Read", "offline_access"]
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

class OneDriveConnector(BaseConnector):
    def _build_msal_app(self):
        return msal.ConfidentialClientApplication(
            ONEDRIVE_CLIENT_ID,
            authority=AUTHORITY,
            client_credential=ONEDRIVE_CLIENT_SECRET
        )

    def get_authorization_url(self) -> str:
        app = self._build_msal_app()
        auth_url = app.get_authorization_request_url(
            SCOPES,
            redirect_uri=REDIRECT_URI
        )
        return auth_url

    def exchange_code(self, code: str) -> dict:
        app = self._build_msal_app()
        result = app.acquire_token_by_authorization_code(
            code,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        if "error" in result:
             raise Exception(f"Error exchanging code: {result.get('error_description')}")
             
        # Get user email/details from graph
        access_token = result['access_token']
        headers = {'Authorization': 'Bearer ' + access_token}
        user_info = requests.get(f'{GRAPH_API_ENDPOINT}/me', headers=headers).json()
        
        return {
            "access_token": result['access_token'],
            "refresh_token": result.get('refresh_token'), # May not always come back if not offline_access?
            "token_uri": AUTHORITY, # Store authority as token_uri for consistency or None
            "client_id": ONEDRIVE_CLIENT_ID,
            "client_secret": ONEDRIVE_CLIENT_SECRET,
            "scopes": ",".join(SCOPES),
            "user_email": user_info.get('userPrincipalName') or user_info.get('mail'),
            "provider": "onedrive"
        }

    def update_tokens(self, user, db_session) -> bool:
        # Check if expired logic could be added here, but MSAL handles cache usually.
        # Since we store tokens in DB manually, we use refresh token flow.
        app = self._build_msal_app()
        
        # We need to manually refresh if we don't use MSAL's token cache persistence
        # acquire_token_by_refresh_token
        result = app.acquire_token_by_refresh_token(
            user.refresh_token,
            scopes=SCOPES
        )
        
        if "error" in result:
            print(f"Error refreshing OneDrive token: {result.get('error_description')}")
            return False
            
        user.access_token = result['access_token']
        if 'refresh_token' in result:
            user.refresh_token = result['refresh_token']
            
        db_session.commit()
        return True

    def list_recent_files(self, user) -> list:
        # Assumes update_tokens called before ensuring validity
        headers = {'Authorization': 'Bearer ' + user.access_token}
        
        # Filter logic
        now = datetime.datetime.utcnow()
        if user.last_synced_at:
            start_time = user.last_synced_at
        else:
            start_time = now - datetime.timedelta(minutes=15)
            
        # OData filter format: 2023-01-01T12:00:00Z
        time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # https://graph.microsoft.com/v1.0/me/drive/root/search(q='...')? 
        # Or better use delta or filter on list.
        # Simple list with filter on root children (recursive search is harder with pure filter on list)
        # Using search api: /me/drive/root/search(q='')
        # However, filter on lastModifiedDateTime usually works on list children.
        # Let's use recursive search if possible or just filter root for demo.
        # Better: /me/drive/root/children?$filter=lastModifiedDateTime ge ...
        
        # Note: OneDrive filter support varies. 
        # Let's try to just list root children for now with filter, 
        # or search. Search doesn't always support complex filters perfectly.
        
        url = f"{GRAPH_API_ENDPOINT}/me/drive/root/children"
        params = {
            "$filter": f"lastModifiedDateTime ge {time_str}",
            "$select": "id,name,lastModifiedDateTime"
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error listing OneDrive files: {response.text}")
            return []
            
        data = response.json()
        items = data.get('value', [])
        
        return [
            {"id": item['id'], "name": item['name'], "modified_time": item['lastModifiedDateTime']}
            for item in items
        ]
