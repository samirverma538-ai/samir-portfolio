import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import storage

# Initialize Firebase Admin if not already initialized
if not firebase_admin._apps:
    # Use application default credentials (works on Cloud Run/Functions)
    # Locally, set GOOGLE_APPLICATION_CREDENTIALS
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {
        'projectId': 'samir-website-23733',
        'storageBucket': 'samir-website-23733.firebasestorage.app'
    })

db = firestore.client()
bucket = storage.bucket()

def get_db():
    return db
