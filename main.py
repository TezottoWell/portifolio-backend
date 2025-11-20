import os
import json
import base64
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore

from admin_auth import verify_admin_token

load_dotenv()

def init_firebase_from_env():
    """
    Inicializa o Firebase Admin SDK usando:

    1) SERVICE_ACCOUNT_JSON_B64 (recomendado)
    2) SERVICE_ACCOUNT_JSON (JSON cru)
    3) GOOGLE_APPLICATION_CREDENTIALS (arquivo .json)
    """

    if firebase_admin._apps:
        return

    b64 = os.getenv("SERVICE_ACCOUNT_JSON_B64")
    if b64:
        try:
            decoded = base64.b64decode(b64)
            cred_dict = json.loads(decoded)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("🔥 Firebase inicializado via SERVICE_ACCOUNT_JSON_B64")
            return
        except Exception as e:
            print("Erro ao inicializar via SERVICE_ACCOUNT_JSON_B64:", e)
            raise

    raw = os.getenv("SERVICE_ACCOUNT_JSON")
    if raw:
        try:
            cred_dict = json.loads(raw)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("🔥 Firebase inicializado via SERVICE_ACCOUNT_JSON")
            return
        except Exception as e:
            print("Erro ao inicializar via SERVICE_ACCOUNT_JSON:", e)
            raise

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccount.json")
    if os.path.exists(cred_path):
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print("🔥 Firebase inicializado via arquivo serviceAccount.json")
            return
        except Exception as e:
            print("Erro ao inicializar via arquivo:", e)
            raise

    raise RuntimeError(
        "Nenhuma credencial Firebase encontrada. "
        "Defina SERVICE_ACCOUNT_JSON_B64, SERVICE_ACCOUNT_JSON ou monte o arquivo serviceAccount.json."
    )


init_firebase_from_env()
db = firestore.client()


app = FastAPI(title="Portfolio API (Firestore Base64 Images)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/projects")
def get_projects():
    docs = db.collection("projects") \
             .order_by("created_at", direction=firestore.Query.DESCENDING) \
             .stream()

    projects = []
    for d in docs:
        data = d.to_dict()
        projects.append({
            "id": d.id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "image_data": data.get("image_data", ""),
            "created_at": data.get("created_at")
        })

    return projects


@app.post("/admin/projects")
async def add_project(
    title: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...),
    _: bool = Depends(verify_admin_token)
):
    content = await image.read()

    b64 = base64.b64encode(content).decode("utf-8")
    content_type = image.content_type or "image/jpeg"
    data_url = f"data:{content_type};base64,{b64}"

    approx_size = len(b64) * 3 / 4
    if approx_size > (900 * 1024):
        raise HTTPException(400, "Imagem muito grande. Reduza antes do upload.")

    doc = {
        "title": title,
        "description": description,
        "image_data": data_url,
        "created_at": datetime.utcnow(),
    }

    ref = db.collection("projects").document()
    ref.set(doc)

    return {"message": "created", "id": ref.id}


@app.put("/admin/projects/{project_id}")
async def edit_project(
    project_id: str,
    title: str = Form(None),
    description: str = Form(None),
    image: UploadFile = File(None),
    _: bool = Depends(verify_admin_token)
):
    doc_ref = db.collection("projects").document(project_id)
    snap = doc_ref.get()

    if not snap.exists:
        raise HTTPException(404, "Project not found")

    update_data = {}

    if title is not None:
        update_data["title"] = title
    if description is not None:
        update_data["description"] = description

    if image is not None:
        content = await image.read()
        b64 = base64.b64encode(content).decode("utf-8")
        content_type = image.content_type or "image/jpeg"
        data_url = f"data:{content_type};base64,{b64}"

        approx_size = len(b64) * 3 / 4
        if approx_size > (900 * 1024):
            raise HTTPException(400, "Imagem muito grande. Reduza antes do upload.")

        update_data["image_data"] = data_url

    if not update_data:
        raise HTTPException(400, "Nenhum campo enviado para atualizar.")

    update_data["updated_at"] = datetime.utcnow()

    doc_ref.update(update_data)

    return {"message": "updated", "id": project_id, "updated_fields": list(update_data.keys())}


@app.delete("/admin/projects/{project_id}")
def delete_project(project_id: str, _: bool = Depends(verify_admin_token)):
    doc_ref = db.collection("projects").document(project_id)
    snap = doc_ref.get()

    if not snap.exists:
        raise HTTPException(404, "Project not found")

    doc_ref.delete()
    return {"message": "Project deleted", "id": project_id}
