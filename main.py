from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Mi API", description="Una API de ejemplo con FastAPI", version="1.0.0"
)


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a mi API con FastAPI!"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.post("/items/")
def create_item(item: Item):
    return item
