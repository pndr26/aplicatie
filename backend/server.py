from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Settings
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
INSPECTOR_CREATION_PASSWORD = "Chiru_041217_"

# Security
security = HTTPBearer()

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Models
class UserBase(BaseModel):
    name: str
    phone: str
    email: EmailStr
    role: str  # "client" or "inspector"

class UserCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr
    role: str
    password: str
    inspector_id: Optional[str] = None
    inspector_creation_password: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    phone: str
    email: str
    role: str
    inspector_id: Optional[str] = None
    cars: List[str] = []

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class AddCarRequest(BaseModel):
    license_plate: str

class InspectionCreate(BaseModel):
    car_license_plate: str
    owner_phone: str
    inspection_date: str  # DD-MM-YYYY
    expiry_date: str  # DD-MM-YYYY
    inspector_name: str
    inspector_phone: str
    car_kilometers: int

class InspectionUpdate(BaseModel):
    car_license_plate: Optional[str] = None
    owner_phone: Optional[str] = None
    inspection_date: Optional[str] = None
    expiry_date: Optional[str] = None
    inspector_name: Optional[str] = None
    inspector_phone: Optional[str] = None
    car_kilometers: Optional[int] = None

class InspectionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    car_license_plate: str
    owner_phone: str
    inspection_date: str
    expiry_date: str
    inspector_name: str
    inspector_phone: str
    car_kilometers: int
    created_at: str

# Helper functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token invalid")
        
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="Utilizator negăsit")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirat")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalid")

# Auth Routes
@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email-ul este deja înregistrat")
    
    # Validate role
    if user_data.role not in ["client", "inspector"]:
        raise HTTPException(status_code=400, detail="Rol invalid")
    
    # If inspector, validate creation password and inspector_id
    if user_data.role == "inspector":
        if not user_data.inspector_id:
            raise HTTPException(status_code=400, detail="ID-ul de inspector este necesar")
        if user_data.inspector_creation_password != INSPECTOR_CREATION_PASSWORD:
            raise HTTPException(status_code=403, detail="Parolă de creare inspector incorectă")
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(user_data.password)
    
    user_dict = {
        "id": user_id,
        "name": user_data.name,
        "phone": user_data.phone,
        "email": user_data.email,
        "role": user_data.role,
        "password": hashed_pw,
        "cars": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if user_data.role == "inspector":
        user_dict["inspector_id"] = user_data.inspector_id
    
    await db.users.insert_one(user_dict)
    
    # Create token
    access_token = create_access_token({"sub": user_id})
    
    # Prepare response
    user_response = UserResponse(
        id=user_id,
        name=user_data.name,
        phone=user_data.phone,
        email=user_data.email,
        role=user_data.role,
        inspector_id=user_data.inspector_id if user_data.role == "inspector" else None,
        cars=[]
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(login_data: UserLogin):
    user = await db.users.find_one({"email": login_data.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Email sau parolă incorectă")
    
    if not verify_password(login_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email sau parolă incorectă")
    
    access_token = create_access_token({"sub": user["id"]})
    
    user_response = UserResponse(
        id=user["id"],
        name=user["name"],
        phone=user["phone"],
        email=user["email"],
        role=user["role"],
        inspector_id=user.get("inspector_id"),
        cars=user.get("cars", [])
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        name=current_user["name"],
        phone=current_user["phone"],
        email=current_user["email"],
        role=current_user["role"],
        inspector_id=current_user.get("inspector_id"),
        cars=current_user.get("cars", [])
    )

# User Routes
@api_router.post("/users/add-car")
async def add_car(car_data: AddCarRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "client":
        raise HTTPException(status_code=403, detail="Doar clienții pot adăuga mașini")
    
    cars = current_user.get("cars", [])
    if car_data.license_plate in cars:
        raise HTTPException(status_code=400, detail="Mașina este deja adăugată")
    
    cars.append(car_data.license_plate)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"cars": cars}}
    )
    
    return {"message": "Mașină adăugată cu succes", "cars": cars}

@api_router.delete("/users/remove-car/{license_plate}")
async def remove_car(license_plate: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "client":
        raise HTTPException(status_code=403, detail="Doar clienții pot șterge mașini")
    
    cars = current_user.get("cars", [])
    if license_plate not in cars:
        raise HTTPException(status_code=404, detail="Mașină negăsită")
    
    cars.remove(license_plate)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"cars": cars}}
    )
    
    return {"message": "Mașină ștearsă cu succes", "cars": cars}

# Inspection Routes
@api_router.post("/inspections", response_model=InspectionResponse)
async def create_inspection(inspection_data: InspectionCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "inspector":
        raise HTTPException(status_code=403, detail="Doar inspectorii pot crea inspecții")
    
    inspection_id = str(uuid.uuid4())
    inspection_dict = {
        "id": inspection_id,
        "car_license_plate": inspection_data.car_license_plate,
        "owner_phone": inspection_data.owner_phone,
        "inspection_date": inspection_data.inspection_date,
        "expiry_date": inspection_data.expiry_date,
        "inspector_name": inspection_data.inspector_name,
        "inspector_phone": inspection_data.inspector_phone,
        "car_kilometers": inspection_data.car_kilometers,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.inspections.insert_one(inspection_dict)
    
    return InspectionResponse(**inspection_dict)

@api_router.get("/inspections", response_model=List[InspectionResponse])
async def get_inspections(current_user: dict = Depends(get_current_user)):
    if current_user["role"] == "client":
        # Client can only see their own cars' inspections
        cars = current_user.get("cars", [])
        if not cars:
            return []
        inspections = await db.inspections.find(
            {"car_license_plate": {"$in": cars}},
            {"_id": 0}
        ).to_list(1000)
    else:
        # Inspector can see all inspections
        inspections = await db.inspections.find({}, {"_id": 0}).to_list(1000)
    
    return [InspectionResponse(**insp) for insp in inspections]

@api_router.get("/inspections/search/{license_plate}", response_model=List[InspectionResponse])
async def search_inspections(license_plate: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] == "client":
        # Client can only search their own cars
        cars = current_user.get("cars", [])
        if license_plate not in cars:
            raise HTTPException(status_code=403, detail="Nu aveți permisiunea de a vedea această mașină")
    
    inspections = await db.inspections.find(
        {"car_license_plate": license_plate},
        {"_id": 0}
    ).to_list(1000)
    
    return [InspectionResponse(**insp) for insp in inspections]

@api_router.put("/inspections/{inspection_id}", response_model=InspectionResponse)
async def update_inspection(inspection_id: str, inspection_data: InspectionUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "inspector":
        raise HTTPException(status_code=403, detail="Doar inspectorii pot actualiza inspecțiile")
    
    inspection = await db.inspections.find_one({"id": inspection_id}, {"_id": 0})
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspecție negăsită")
    
    update_data = inspection_data.model_dump(exclude_unset=True)
    if update_data:
        await db.inspections.update_one(
            {"id": inspection_id},
            {"$set": update_data}
        )
        inspection.update(update_data)
    
    return InspectionResponse(**inspection)

@api_router.delete("/inspections/{inspection_id}")
async def delete_inspection(inspection_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "inspector":
        raise HTTPException(status_code=403, detail="Doar inspectorii pot șterge inspecțiile")
    
    result = await db.inspections.delete_one({"id": inspection_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Inspecție negăsită")
    
    return {"message": "Inspecție ștearsă cu succes"}

@api_router.get("/inspections/expiring/soon", response_model=List[InspectionResponse])
async def get_expiring_inspections(current_user: dict = Depends(get_current_user)):
    # Get inspections expiring in next 30 days
    today = datetime.now(timezone.utc)
    
    if current_user["role"] == "client":
        cars = current_user.get("cars", [])
        if not cars:
            return []
        inspections = await db.inspections.find(
            {"car_license_plate": {"$in": cars}},
            {"_id": 0}
        ).to_list(1000)
    else:
        inspections = await db.inspections.find({}, {"_id": 0}).to_list(1000)
    
    # Filter expiring inspections
    expiring = []
    for insp in inspections:
        try:
            # Parse DD-MM-YYYY format
            expiry_parts = insp["expiry_date"].split("-")
            expiry_date = datetime(int(expiry_parts[2]), int(expiry_parts[1]), int(expiry_parts[0]))
            days_until_expiry = (expiry_date - today).days
            
            if 0 <= days_until_expiry <= 30:
                expiring.append(InspectionResponse(**insp))
        except:
            continue
    
    return expiring

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()