import os
import json

=
service_account_content = os.getenv("SERVICE_ACCOUNT_JSON")

# أنشئ ملف serviceAccountKey.json مؤقت
with open("serviceAccountKey.json", "w") as f:
    f.write(service_account_content)


import firebase_admin
from firebase_admin import credentials, db

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': os.getenv("FIREBASE_DB_URL")
})
