from pydantic import BaseModel

class CaseOut(BaseModel):
    id: int
    title: str
    description: str

    class Config:
        orm_mode = True

class CaseCreate(BaseModel):
    title: str
    description: str
    body: str
