import json
import os
import datetime
from .base import BaseConnector
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# Update this dynamically or via config
REDIRECT_URI = "http://localhost:8000/auth/google/callback"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/userinfo.email"]

class GoogleConnector(BaseConnector):
    def get_authorization_url(self) -> str:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = REDIRECT_URI
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        return authorization_url

    def exchange_code(self, code: str) -> dict:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = REDIRECT_URI
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Get user email
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": json.dumps(credentials.scopes) if credentials.scopes else json.dumps(SCOPES),
            "user_email": user_info['email'],
            "provider": "google"
        }
        
    def  _get_creds(self, user):
        return Credentials(
            token=user.access_token,
            refresh_token=user.refresh_token,
            token_uri=user.token_uri,
            client_id=user.client_id,
            client_secret=user.client_secret,
            scopes=None 
        )

    def update_tokens(self, user, db_session) -> bool:
        creds = self._get_creds(user)
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                user.access_token = creds.token
                if creds.refresh_token:
                    user.refresh_token = creds.refresh_token
                db_session.commit()
                return True
            except Exception as e:
                print(f"Error refreshing Google token: {e}")
                return False
        return True

    def list_recent_files(self, user) -> list:
        creds = self._get_creds(user)
        service = build('drive', 'v3', credentials=creds)
        
        # Time filter
        now = datetime.datetime.utcnow()
        if user.last_synced_at:
            start_time = user.last_synced_at
        else:
            start_time = now - datetime.timedelta(minutes=15)
        
        time_str = start_time.isoformat() + "Z"
        query = f"modifiedTime > '{time_str}' and trashed = false"
        
        results = service.files().list(
            q=query, pageSize=10, fields="nextPageToken, files(id, name, modifiedTime)"
        ).execute()
        
        items = results.get('files', [])
        return [
            {"id": item['id'], "name": item['name'], "modified_time": item['modifiedTime']}
            for item in items
        ]
