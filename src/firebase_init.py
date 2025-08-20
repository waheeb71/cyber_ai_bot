import os
import json
import firebase_admin
from firebase_admin import credentials, db


service_account_content = os.getenv("SERVICE_ACCOUNT_JSON")
firebase_db_url = os.getenv("FIREBASE_DB_URL")

if not service_account_content or not firebase_db_url:
    raise ValueError("SERVICE_ACCOUNT_JSON or FIREBASE_DB_URL is missing!")


with open("serviceAccountKey.json", "w") as f:
    f.write(service_account_content)


cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': firebase_db_url
})

print("Firebase initialized successfully ✅")
