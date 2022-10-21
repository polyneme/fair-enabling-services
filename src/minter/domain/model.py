from pydantic import BaseModel, PositiveInt


class MintRequest(BaseModel):
    naa: str = "polyneme"
    shoulder: str = "1fk1"  # "fake" shoulder
    number: PositiveInt = 1
