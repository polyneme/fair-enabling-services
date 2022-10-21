import re

from fastapi import FastAPI, Depends, HTTPException
from pymongo.database import Database as MongoDatabase
from starlette import status

from minter.config import get_mongo_db
from minter.domain.model import MintRequest
from minter.service_layer.idgen import generate_ids, decode_id

app = FastAPI()


def raise404_if_none(doc, detail="Not found"):
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return doc


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/ids/mint", response_model=list[str])
def mint_ids(
    mint_req: MintRequest,
    mdb: MongoDatabase = Depends(get_mongo_db),
):
    """Generate one or more identifiers."""
    ids = generate_ids(
        mdb,
        number=mint_req.number,
        naa=mint_req.naa,
        shoulder=mint_req.shoulder,
    )
    return ids


shoulder_key_pattern = re.compile(r"([0-9].*?[0-9])(.+)")


@app.get("/ids/{id_str}", response_model=dict)
def get_id(
    id_str: str,
    mdb: MongoDatabase = Depends(get_mongo_db),
):
    """Get identifier."""
    try:
        prefix, rest = id_str.split(":", maxsplit=1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID needs to be a CURIE (so has a ':').",
        )
    try:
        shoulder, key = re.fullmatch(shoulder_key_pattern, rest).groups()
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "ID local part (after ':') needs to start with shoulder "
                "of form r'[0-9].*?[0-9]'."
            ),
        )
    coll = mdb.get_collection(f"ids_{prefix}_{shoulder}")
    try:
        doc = coll.find_one({"_id": decode_id(key)})
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID key has invalid checksum. This ID could never have been issued.",
        )
    return raise404_if_none(doc)
