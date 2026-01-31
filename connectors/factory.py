from .google import GoogleConnector
from .onedrive import OneDriveConnector
from .base import BaseConnector

def get_connector(provider: str) -> BaseConnector:
    if provider == "google":
        return GoogleConnector()
    elif provider == "onedrive":
        return OneDriveConnector()
    else:
        raise ValueError(f"Unknown provider: {provider}")
