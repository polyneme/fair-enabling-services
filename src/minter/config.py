import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase

TYPECODES = [
    {
        "codes": ["agt"],
        "type": "prov:Agent",
        "note": "an agent",
    },
    {
        "codes": ["ent"],
        "type": "prov:Entity",
        "note": "an entity",
    },
    {
        "codes": ["act"],
        "type": "prov:Activity",
        "note": "an activity",
    },
]


@lru_cache
def typecode_type(typecode):
    for t in TYPECODES:
        if typecode in t["codes"]:
            return t["type"], t["note"]
    else:
        raise ValueError(f"typecode '{typecode}' not found")


@lru_cache
def get_mongo_db() -> MongoDatabase:
    _client = MongoClient(
        host=os.getenv("MONGO_HOST"),
        username=os.getenv("MONGO_USERNAME"),
        password=os.getenv("MONGO_PASSWORD"),
    )
    return _client["minter"]
