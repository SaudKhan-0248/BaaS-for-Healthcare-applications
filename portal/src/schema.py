from pydantic import BaseModel, constr
from typing import Literal
from datetime import date


class User(BaseModel):
    username: constr(min_length=3, max_length=25)
    email: str
    password: constr(min_length=8, max_length=30)
    dob: date
    gender: Literal['MALE', 'FEMALE']