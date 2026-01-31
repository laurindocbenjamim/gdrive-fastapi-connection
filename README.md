# Cloud Drive Connector Hub

A centralized Hub for connecting and managing Google Drive and Microsoft OneDrive accounts using FastAPI. This service handles OAuth2 authentication, securely stores user credentials, and provides an on-demand synchronization worker to list recent files from connected providers.

## Features

- **Multi-Provider Support**: Connect Google Drive and OneDrive accounts.
- **Connector Architecture**: Modular design for easy addition of new providers (Dropbox, Box, etc.).
- **Secure Storage**: Access and Refresh tokens are encrypted at rest using `cryptography`.
- **On-Demand Sync**: Trigger file synchronization via API (`POST /sync`) to fetch changed files.
- **Smart Refresh**: Automatically handles token refreshing (Google & MSAL) before API calls.

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLite (SQLAlchemy)
- **Auth**: Google Auth Library, MSAL (Microsoft Authentication Library)
- **Security**: Fernet Encryption (Cryptography)

## Setup

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd gdrive-api
   ```

2. **Install Dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Environment Configuration**:
   Create a `.env` file in the root directory:
   ```env
   DATABASE_URL=sqlite:///./gdrive.db
   SECRET_KEY=your_generated_fernet_key
   
   # Google Configuration
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   
   # OneDrive Configuration
   ONEDRIVE_CLIENT_ID=your_onedrive_client_id
   ONEDRIVE_CLIENT_SECRET=your_onedrive_client_secret
   ```
   
   *Tip: Generate a `SECRET_KEY` using:*
   ```python
   from cryptography.fernet import Fernet
   print(Fernet.generate_key().decode())
   ```

## Usage

1. **Start the Server**:
   ```bash
   uvicorn main:app --reload
   ```

2. **Connect Accounts**:
   - **Google**: Navigate to `http://localhost:8000/auth/google/login`
   - **OneDrive**: Navigate to `http://localhost:8000/auth/onedrive/login`
   
   Follow the OAuth2 flow to authenticate.

3. **List Connected Users**:
   ```bash
   curl http://localhost:8000/users
   ```

4. **Trigger Synchronization**:
   Run the background worker process on-demand. You can specify `both` (default), `google`, or `onedrive`.
   ```bash
   # Sync all
   curl -X POST http://localhost:8000/sync
   
   # Sync only OneDrive users
   curl -X POST http://localhost:8000/sync -H "Content-Type: application/json" -d '{"source_type": "onedrive"}'
   ```
   Check the server logs to see the listed files.

## API Reference

### Auth
- **GET** `/auth/{provider}/login`: Start OAuth flow. `provider` = `google` or `onedrive`.
- **GET** `/auth/{provider}/callback`: OAuth callback handler.

### Users
- **GET** `/users`: List all connected users.
  - **Response**: `[{"id": 1, "email": "...", "provider": "google", "has_refresh_token": true}]`

### System
- **GET** `/config`: Check available providers (based on `.env`).
  - **Response**: `{"available_providers": ["google", "onedrive"], "mode": "multi-provider"}`

- **POST** `/sync`: Trigger background sync.
  - **Body** (optional): `{"source_type": "both"}` 
    - values: `both`, `google`, `onedrive`
  - **Response**: `{"message": "Sync process started...", "target_providers": ["google", "onedrive"]}`

## Project Structure

- `main.py`: FastAPI application and endpoints.
- `models.py`: Database models (User, Encryption).
- `connectors/`: Provider implementations.
  - `base.py`: Abstract Interface.
  - `google.py`: Google Drive logic.
  - `onedrive.py`: OneDrive logic.
  - `factory.py`: Connector instantiation logic.
- `worker.py`: Background task logic (can be run standalone or imported).
