import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from connectors.factory import get_connector

def process_users(providers: list = None):
    """
    Syncs files for users matches the specified providers.
    If providers is None, syncs all.
    """
    db = SessionLocal()
    try:
        query = db.query(User)
        if providers:
            query = query.filter(User.provider.in_(providers))
            
        users = query.all()
        print(f"Found {len(users)} users to process for providers: {providers or 'ALL'}")
        
        for user in users:
            try:
                print(f"Processing {user.email} (Provider: {user.provider})")
                
                try:
                    connector = get_connector(user.provider)
                except ValueError as e:
                    print(f"Skipping {user.email}: {e}")
                    continue

                # 1. Update/Refresh tokens
                if not connector.update_tokens(user, db):
                     print(f"Failed to refresh tokens for {user.email}. Skipping.")
                     continue
                
                # 2. List recent files
                print(f"Listing recent files for {user.email}...")
                files = connector.list_recent_files(user)
                
                if not files:
                    print(f"No new files found for {user.email}.")
                else:
                    print(f"Found {len(files)} new/modified files:")
                    for f in files:
                        print(f"  [{f['modified_time']}] {f['name']} (ID: {f.get('id')})")
                
                # 3. Update Sync Time
                user.last_synced_at = datetime.datetime.utcnow()
                db.commit()
                
            except Exception as e:
                print(f"Error processing user {user.email}: {e}")
                
    finally:
        db.close()

if __name__ == "__main__":
    process_users()
