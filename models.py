from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from cryptography.fernet import Fernet
import os
import datetime

# Load key from environment
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY must be set in .env for encryption")

cipher_suite = Fernet(SECRET_KEY)

def encrypt_value(value: str) -> str:
    if not value:
        return None
    return cipher_suite.encrypt(value.encode()).decode()

def decrypt_value(value: str) -> str:
    if not value:
        return None
    return cipher_suite.decrypt(value.encode()).decode()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    provider = Column(String, default="google") # google, onedrive
    
    # Encrypted fields
    _access_token = Column("access_token", String)
    _refresh_token = Column("refresh_token", String)
    _client_id = Column("client_id", String)
    _client_secret = Column("client_secret", String)
    
    token_uri = Column(String)
    scopes = Column(String) # Store as comma-separated
    last_synced_at = Column(DateTime, default=None)
    token_expires_at = Column(DateTime, default=None)

    @property
    def access_token(self):
        return decrypt_value(self._access_token)

    @access_token.setter
    def access_token(self, value):
        self._access_token = encrypt_value(value)

    @property
    def refresh_token(self):
        return decrypt_value(self._refresh_token)

    @refresh_token.setter
    def refresh_token(self, value):
        self._refresh_token = encrypt_value(value)
        
    @property
    def client_id(self):
        return decrypt_value(self._client_id)

    @client_id.setter
    def client_id(self, value):
        self._client_id = encrypt_value(value)

    @property
    def client_secret(self):
        return decrypt_value(self._client_secret)

    @client_secret.setter
    def client_secret(self, value):
        self._client_secret = encrypt_value(value)
