import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Warning: SUPABASE_URL and SUPABASE_KEY are not set in the environment.")
    # In production/deployment, these should be set.
    # For testing, we might want to fail gracefully or error out here.

def get_supabase() -> Client:
    return create_client(url, key)
