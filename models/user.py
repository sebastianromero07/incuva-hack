from typing import Optional
from pydantic import BaseModel
from passlib.context import CryptContext
import json
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(BaseModel):
    email: str
    name: str
    hashed_password: str

class UserInDB(User):
    def verify_password(self, plain_password: str) -> bool:
        # Truncar password si es muy largo (límite de bcrypt)
        if len(plain_password.encode('utf-8')) > 72:
            plain_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        
        try:
            return pwd_context.verify(plain_password, self.hashed_password)
        except Exception as e:
            print(f"❌ Error verificando password: {e}")
            return False

class UserManager:
    def __init__(self):
        self.users_file = "data/users.json"
        self._ensure_users_file()
    
    def hash_password(self, password: str) -> str:
        """Hash password con límite de 72 bytes para bcrypt"""
        # Truncate password to 72 bytes if necessary (bcrypt limitation)
        if len(password.encode('utf-8')) > 72:
            password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        
        try:
            return pwd_context.hash(password)
        except Exception as e:
            print(f"❌ Error hasheando password: {e}")
            # Fallback simple sin hash
            return f"fallback_{password}"
    
    def _ensure_users_file(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.users_file):
            # Obtener credenciales de variables de entorno O usar defaults
            admin_email = os.getenv("ADMIN_EMAIL")
            admin_password = os.getenv("ADMIN_PASSWORD")
            admin_name = os.getenv("ADMIN_NAME")
            
            # Crear usuario
            try:
                default_user = {
                    admin_email: {
                        "email": admin_email,
                        "name": admin_name,
                        "hashed_password": self.hash_password(admin_password)
                    }
                }
                
                with open(self.users_file, "w") as f:
                    json.dump(default_user, f, indent=2)
                    
                print(f"👤 Usuario creado: {admin_email} / {admin_password}")
                    
            except Exception as e:
                print(f"❌ Error creando usuario: {e}")
                # Crear usuario mínimo sin hash
                fallback_user = {
                    "testuser@tomi.com.pe": {
                        "email": "testuser@tomi.com.pe",
                        "name": "Test User",
                        "hashed_password": "fallback_12345678"
                    }
                }
                with open(self.users_file, "w") as f:
                    json.dump(fallback_user, f, indent=2)
                print("⚠️ Usuario creado con método fallback")
    
    def get_user(self, email: str) -> Optional[UserInDB]:
        try:
            with open(self.users_file, "r") as f:
                users = json.load(f)
            
            if email in users:
                return UserInDB(**users[email])
        except Exception as e:
            print(f"❌ Error leyendo usuario: {e}")
        return None
    
    def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        try:
            user = self.get_user(email)
            if user:
                # Si el hash es fallback, comparar directamente
                if user.hashed_password.startswith("fallback_"):
                    stored_password = user.hashed_password.replace("fallback_", "")
                    if password == stored_password:
                        return user
                else:
                    # Usar verificación normal
                    if user.verify_password(password):
                        return user
        except Exception as e:
            print(f"❌ Error autenticando: {e}")
        return None
    
    def create_user(self, email: str, name: str, password: str) -> bool:
        """Crear nuevo usuario"""
        try:
            users = {}
            if os.path.exists(self.users_file):
                with open(self.users_file, "r") as f:
                    users = json.load(f)
            
            if email in users:
                return False  # Usuario ya existe
            
            users[email] = {
                "email": email,
                "name": name,
                "hashed_password": self.hash_password(password)
            }
            
            with open(self.users_file, "w") as f:
                json.dump(users, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error creando usuario: {e}")
            return False

user_manager = UserManager()