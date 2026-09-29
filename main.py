import boto3
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import AWS_REGION, S3_VIDEOS_BUCKET, S3_THUMBNAILS_BUCKET
from database import engine, Base, get_db
from models import UserDB, VideoDB, CommentDB
from auth import hash_password, verify_password

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Video Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

s3_client = boto3.client("s3", region_name=AWS_REGION)

def upload_to_s3(file: UploadFile, bucket: str, filename: str) -> str:
    s3_client.upload_fileobj(
        file.file,
        bucket,
        filename,
        ExtraArgs={"ContentType": file.content_type}
    )
    return f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{filename}"

# --- RUTAS USUARIOS ---
@app.post("/users", status_code=status.HTTP_201_CREATED)
def register(name: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    hashed_pwd = hash_password(password)
    user = UserDB(name=name, email=email, password_hash=hashed_pwd)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Credenciales inválidas")
    return {"id": user.id, "name": user.name, "email": user.email}

@app.get("/users/{user_id}")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    videos = db.query(VideoDB).filter(VideoDB.user_id == user_id).all()
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email},
        "video_count": len(videos),
        "videos": videos
    }

@app.post("/videos", status_code=status.HTTP_201_CREATED)
def upload_video(
    title: str = Form(...),
    description: str = Form(...),
    user_id: int = Form(...),
    video_file: UploadFile = File(...),
    thumbnail_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    timestamp = int(datetime.now().timestamp())
    video_key = f"videos/{timestamp}_{video_file.filename}"
    thumb_key = f"thumbnails/{timestamp}_{thumbnail_file.filename}"
    
    video_url = upload_to_s3(video_file, S3_VIDEOS_BUCKET, video_key)
    thumb_url = upload_to_s3(thumbnail_file, S3_THUMBNAILS_BUCKET, thumb_key)
    
    video = VideoDB(
        title=title,
        description=description,
        video_url=video_url,
        thumbnail_url=thumb_url,
        user_id=user_id
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video

@app.get("/videos")
def get_videos(db: Session = Depends(get_db)):
    return db.query(VideoDB).all()

@app.get("/videos/{video_id}")
def get_video_detail(video_id: int, db: Session = Depends(get_db)):
    video = db.query(VideoDB).filter(VideoDB.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    
    video.views += 1
    db.commit()
    
    recommended = db.query(VideoDB).filter(VideoDB.id != video_id).limit(5).all()
    return {"video": video, "recommended": recommended}

@app.put("/videos/{video_id}")
def update_video(video_id: int, title: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):
    video = db.query(VideoDB).filter(VideoDB.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    video.title = title
    video.description = description
    db.commit()
    return video

@app.delete("/videos/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(VideoDB).filter(VideoDB.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    db.delete(video)
    db.commit()
    return {"detail": "Video eliminado correctamente"}

# --- RUTAS COMENTARIOS ---
@app.post("/videos/{video_id}/comments")
def add_comment(video_id: int, user_id: int = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    comment = CommentDB(content=content, user_id=user_id, video_id=video_id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

@app.get("/videos/{video_id}/comments")
def get_comments(video_id: int, db: Session = Depends(get_db)):
    return db.query(CommentDB).filter(CommentDB.video_id == video_id).all()