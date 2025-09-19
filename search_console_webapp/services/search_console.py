import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Cargar variables de entorno (ruta a client_secret.json y token.json)
load_dotenv('serpapi.env')

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
CLIENT_SECRETS_FILE = os.getenv('CLIENT_SECRETS_FILE', 'client_secret.json')
TOKEN_FILE          = os.getenv('TOKEN_FILE', 'token.json')

def authenticate():
    """Autentica con Google Search Console y devuelve el objeto service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Guardar credenciales renovadas
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    service = build('searchconsole', 'v1', credentials=creds)
    return service

def fetch_searchconsole_data_single_call(service, site_url, start_date, end_date,
                                         dimensions, filters=None, row_limit=25000):
    """
    Llama al endpoint searchanalytics.query de GSC.
    Devuelve una lista de filas (cada fila es un dict con keys: keys, clicks, impressions, ctr, position).
    """
    body = {
        'startDate': start_date,
        'endDate':   end_date,
        'dimensions': dimensions,
        'rowLimit':  row_limit
    }
    if filters:
        body['dimensionFilterGroups'] = filters

    resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    return resp.get('rows', [])
