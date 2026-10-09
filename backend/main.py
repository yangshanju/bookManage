from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session 
from datetime import datetime  
from pathlib import Path 

# ====================== 配置模块 ======================
BASE_DIR=Path(__file__).parent
class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=BASE_DIR/'.env',env_file_encoding='utf-8',extra='ignore')
    app_title:str
    db_url:str

settings=Settings()
def get_settings():
    return settings

# ====================== 数据库 ======================
engine = create_engine(settings.db_url, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 数据库模型 Book表
class BookDB(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, index=True)
    book_name = Column(String(100), nullable=False)  # 图书名称
    author = Column(String(50), nullable=False)      # 作者 
    isbn = Column(String(30), unique=True)           # ISBN编号
    create_time = Column(DateTime, default=datetime.now)

# 自动建表
Base.metadata.create_all(bind=engine)

# 数据库会话依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ====================== Pydantic模型（请求/响应） ======================
class BookCreate(BaseModel):
    book_name: str
    author: str
    isbn: str | None = None

class BookUpdate(BaseModel):
    book_name: str | None = None
    author: str | None = None
    isbn: str | None = None

class BookRead(BookCreate):
    id: int
    create_time: datetime
    model_config = ConfigDict(from_attributes=True)

# ====================== Service业务层封装（考试要求！） ======================
class BookService:
    @staticmethod
    def get_book_by_id(db: Session, book_id: int):
        return db.query(BookDB).filter(BookDB.id == book_id).first()

    @staticmethod
    def get_book_list(db: Session, page: int, page_size: int):
        skip = (page - 1) * page_size
        return db.query(BookDB).offset(skip).limit(page_size).all()

    @staticmethod
    def create_book(db: Session, book: BookCreate):
        db_book = BookDB(**book.model_dump())
        db.add(db_book)
        db.commit()
        db.refresh(db_book)
        return db_book

    @staticmethod
    def update_book(db: Session, book_id: int, book_data: BookUpdate):
        db_book = BookService.get_book_by_id(db, book_id)
        if not db_book:
            return None
        update_data = book_data.model_dump(exclude_unset=True)
        for key, val in update_data.items():
            setattr(db_book, key, val)
        db.commit()
        db.refresh(db_book)
        return db_book

    @staticmethod
    def delete_book(db: Session, book_id: int):
        db_book = BookService.get_book_by_id(db, book_id)
        if not db_book:
            return False
        db.delete(db_book)
        db.commit()
        return True

# ====================== FastAPI应用与路由接口 ======================
app = FastAPI(title=settings.app_title)
# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 新增图书 POST
@app.post("/book", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def add_book(book: BookCreate, db: Session = Depends(get_db)):
    return BookService.create_book(db, book)

# 分页查询图书列表 GET
@app.get("/book/list", response_model=list[BookRead])
def get_book_page(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1), db: Session = Depends(get_db)):
    return BookService.get_book_list(db, page, page_size)

# 根据id查询单本图书
@app.get("/book/{book_id}", response_model=BookRead)
def get_book(book_id: int, db: Session = Depends(get_db)):
    book = BookService.get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="图书不存在")
    return book

# 修改图书 PUT
@app.put("/book/{book_id}", response_model=BookRead)
def edit_book(book_id: int, book_data: BookUpdate, db: Session = Depends(get_db)):
    book = BookService.update_book(db, book_id, book_data)
    if not book:
        raise HTTPException(status_code=404, detail="图书不存在")
    return book

# 删除图书 DELETE
@app.delete("/book/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def del_book(book_id: int, db: Session = Depends(get_db)):
    ok = BookService.delete_book(db, book_id)
    if not ok:
        raise HTTPException(status_code=404, detail="图书不存在")
    return

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
