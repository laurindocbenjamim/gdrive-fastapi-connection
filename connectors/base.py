from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseConnector(ABC):
    @abstractmethod
    def get_authorization_url(self) -> str:
        """Returns the authorization URL for the OAuth2 flow."""
        pass

    @abstractmethod
    def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchanges the authorization code for tokens.
        
        Returns:
            Dict containing:
            - access_token
            - refresh_token (optional)
            - expires_in (optional)
            - user_email (to identify the user)
        """
        pass

    @abstractmethod
    def list_recent_files(self, user) -> List[Dict[str, Any]]:
        """Lists files modified recently using the provider's API.
        
        Returns a list of dicts with at least:
        - id
        - name
        - modified_time (datetime or string)
        """
        pass
    
    @abstractmethod
    def update_tokens(self, user, db_session) -> bool:
        """Checks if existing tokens are valid/refreshable and updates DB if needed.
        Returns True if tokens are valid/refreshed, False if expired/invalid.
        """
        pass
