import os
import firebase_admin 
from firebase_admin import credentials, firestore 

# Path to serviceAccountKey.json in project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIAL_PATH = os.path.join(BASE_DIR, 'serviceAccountKey.json')

# Prevent re-initialization error if the module is loaded multiple times
if not firebase_admin._apps:
    if os.path.exists(CREDENTIAL_PATH):
        cred = credentials.Certificate(CREDENTIAL_PATH)
        firebase_admin.initialize_app(cred)
    else:
        raise FileNotFoundError(
            f"Firebase key not found at '{CREDENTIAL_PATH}'. "
            "Ensure serviceAccountKey.json is placed in your project root folder."
        )

# Global client object
db = firestore.client()