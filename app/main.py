from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy import select
from typing import Annotated
import os
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL)
new_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with new_session() as session:
        yield session

SessionDepend = Annotated[AsyncSession, Depends(get_session)]

class PaginationParametres(BaseModel):
    limit: int = Field(6, ge=0, le=12, description="Количество элементов на странице")
    offset: int = Field(0, ge=0, description="Смещение для пагинации")

PaginationDep = Annotated[PaginationParametres, Depends(PaginationParametres)]

class BookSchema(BaseModel):
    title: str
    author: str
    genre: str | None
    pages: int | None

class BookResponseSchema(BookSchema):
    id: int

class Base(DeclarativeBase):
    ...

class BookModel(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key = True, autoincrement=True)
    title: Mapped[str]
    author: Mapped[str]
    genre: Mapped[str] = mapped_column(nullable=True)
    pages: Mapped[int] = mapped_column(nullable=True)


@app.post('/setud_db')
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.post('/books')
async def add_book(session: SessionDepend, added_book: BookSchema):
    new_book = BookModel(title = added_book.title, author = added_book.author, genre = added_book.genre, pages = added_book.pages)
    session.add(new_book)
    await session.commit()
    await session.refresh(new_book)
    return new_book

@app.get('/books')
async def get_books(session: SessionDepend, pagination: PaginationDep):
    result = select(BookModel).limit(pagination.limit).offset(pagination.offset)
    query = await session.execute(result)
    return query.scalars().all()

@app.put('/books/{book_id}')
async def update_books(book_id: int, session: SessionDepend, book: BookSchema):
    db_book = await session.get(BookModel, book_id)
    db_book.title = book.title
    db_book.author = book.author
    db_book.genre = book.genre
    db_book.pages = book.pages
    await session.commit()
    await session.refresh(db_book)
    return db_book 

@app.delete('/books/{book_id}')
async def delete_book(book_id: int, session: SessionDepend,):
    book = await session.get(BookModel, book_id)
    if not book:
        raise HTTPException(status_code=404)
    await session.delete(book)
    await session.commit()
    return {"Deleted successfully": True}

@app.get('/books/search')
async def search_book(session: SessionDepend, search_text: str = ""):
    if not search_text:
        return await get_books(session)
    result = await session.execute(select(BookModel).where((BookModel.title.contains(search_text)) | (BookModel.author.contains(search_text))))
    return result.scalars().all()

@app.get('/books/filter/{genre_name}')
async def filter_by_genre(genre_name: str, session: SessionDepend):
    result = await session.execute(select(BookModel).where(BookModel.genre == genre_name))
    books = result.scalars().all()
    return books