import os
from dotenv import load_dotenv
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        print("ADMIN_TOKEN não está definido nas variáveis de ambiente!")
        raise HTTPException(status_code=500, detail="Server misconfigured")
    if token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True
