from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File, Cookie, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from auth.jwt_handler import verify_token, create_access_token
from models.user import user_manager
from utils.llm import rag
from datetime import timedelta
import os      # ✅ AGREGAR ESTA LÍNEA
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_current_user(access_token: str = Cookie(None)):
    """Verificar usuario autenticado"""
    if not access_token:
        raise HTTPException(status_code=302, detail="Redirect to login")
    
    try:
        email = verify_token(access_token)
        user = user_manager.get_user(email)
        if not user:
            raise HTTPException(status_code=302, detail="Redirect to login")
        return user
    except:
        raise HTTPException(status_code=302, detail="Redirect to login")



def get_bot_config():
    """Cargar configuración desde archivo"""
    try:
        with open("data/bot_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        # Configuración por defecto si no existe el archivo
        return {
            "status": "inactive",
            "welcome_message": "👋 ¡Hola soy TOmi! Tu asistente virtual de soporte técnico.\nEstoy aquí para ayudarte con cualquier duda o problema que tengas.\n\nCuéntame qué necesitas y te ayudaré al instante.",
            "handoff_message": "Un momento, te voy a conectar con un agente humano que podrá ayudarte mejor."
        }

def save_bot_config(config):
    """Guardar configuración en archivo"""
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/bot_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error guardando config: {e}")
        return False

# ===== RUTAS PÚBLICAS =====

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing page principal - PÚBLICA"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de login - PÚBLICA"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Procesar login - PÚBLICA"""
    user = user_manager.authenticate_user(email, password)
    
    if not user:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Email o contraseña incorrectos"}
        )
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(hours=24)
    )
    
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400
    )
    
    return response

@router.get("/logout")
async def logout():
    """Cerrar sesión - PÚBLICA"""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response

# ===== RUTAS PROTEGIDAS =====

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard principal - PROTEGIDA"""
    # Verificación manual de autenticación
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        email = verify_token(access_token)
        user = user_manager.get_user(email)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        stats = rag.get_stats()
        pdfs = rag.list_documents()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "bot_config": get_bot_config(),
            "pdf_count": stats["total_documents"],   
            "chunks_count": stats["total_chunks"],  
            "rag_status": stats["status"] == "active", 
            "pdfs": pdfs
        })
        

    except Exception as e:
        print(f"❌ Error en dashboard: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "bot_config": bot_config,
            "pdf_count": 0,
            "chunks_count": 0,
            "rag_status": False,
            "pdfs": []
        })

@router.post("/upload-pdf")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """Subir PDF - PROTEGIDA"""
    # Verificación de autenticación
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        verify_token(access_token)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        if not file.filename.endswith('.pdf'):
            return RedirectResponse(url="/dashboard?error=Solo archivos PDF", status_code=302)
        
        file_content = await file.read()
        success = rag.add_pdf_from_upload(file_content, file.filename)
        
        if success:
            return RedirectResponse(url="/dashboard?success=PDF subido correctamente", status_code=302)
        else:
            return RedirectResponse(url="/dashboard?error=Error procesando PDF", status_code=302)
            
    except Exception as e:
        print(f"❌ Error subiendo PDF: {e}")
        return RedirectResponse(url="/dashboard?error=Error interno", status_code=302)

@router.post("/delete-pdf/{filename}")
async def delete_pdf(request: Request, filename: str):
    """Eliminar PDF - PROTEGIDA"""
    # Verificación de autenticación
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        verify_token(access_token)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        success = rag.remove_document(filename) 
        if success:
            return RedirectResponse(url="/dashboard?success=PDF eliminado", status_code=302)
        else:
            return RedirectResponse(url="/dashboard?error=Error eliminando PDF", status_code=302)
    except Exception as e:
        print(f"❌ Error: {e}")
        return RedirectResponse(url="/dashboard?error=Error interno", status_code=302)

@router.post("/update-bot-config")
async def update_bot_config(
    request: Request,
    welcome_message: str = Form(...),
    handoff_message: str = Form(...)
):
    """Actualizar configuración del bot - PROTEGIDA"""
    # Verificación de autenticación
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        verify_token(access_token)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    # CORREGIR: Guardar en archivo, no en memoria
    config = get_bot_config()
    config["welcome_message"] = welcome_message
    config["handoff_message"] = handoff_message
    
    if save_bot_config(config):
        return RedirectResponse(url="/dashboard?success=Configuración actualizada", status_code=302)
    else:
        return RedirectResponse(url="/dashboard?error=Error guardando configuración", status_code=302)


@router.post("/toggle-bot-status")
async def toggle_bot_status(request: Request):
    """Activar/desactivar bot - PROTEGIDA"""
    # Verificación de autenticación
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        verify_token(access_token)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    # CORREGIR: Guardar en archivo, no en memoria
    config = get_bot_config()
    if config["status"] == "active":
        config["status"] = "inactive"
        message = "Bot desactivado"
    else:
        config["status"] = "active"
        message = "Bot activado"
    
    if save_bot_config(config):
        return RedirectResponse(url=f"/dashboard?success={message}", status_code=302)
    else:
        return RedirectResponse(url="/dashboard?error=Error guardando estado", status_code=302)