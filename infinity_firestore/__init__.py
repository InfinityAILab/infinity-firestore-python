import logging

import firebase_admin
from google.cloud.firestore import Client

logger = logging.getLogger(__name__)


def initialize_firebase():
    firebase_admin.initialize_app()


def get_firestore_client(database: str | None = None) -> Client:
    return Client(database=database)
