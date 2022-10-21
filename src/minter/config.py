from functools import lru_cache


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
