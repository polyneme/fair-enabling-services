import re
from enum import Enum
from functools import lru_cache
from itertools import tee
from typing import Union, Any, Optional, Literal

from pydantic import BaseModel, constr, PositiveInt, root_validator

# NO i, l, o or u.
# ref: https://www.crockford.com/base32.html
from toolz import concat, pluck

base32_letters = "abcdefghjkmnpqrstvwxyz"
base32_chars = "0123456789" + base32_letters

# Archival Resource Key (ARK) identifier scheme
# ref: https://www.ietf.org/archive/id/draft-kunze-ark-35.html
#
# NAAN - Name Assigning Authority Number
# ref: https://n2t.net/e/pub/naan_registry.txt

# The base compact name assigned by the NAA consists of
# (a) a "shoulder", and (b) a final string known as the "blade".
# (The shoulder plus blade terminology mirrors locksmith jargon describing
# the information-bearing parts of a key.)
#
# Shoulders may reserved for internal departments or units.
# In the case of one central minting service, there technically need only be one shoulder.
# ref: https://www.ietf.org/archive/id/draft-kunze-ark-35.html#name-optional-shoulders
#
# For NMDC, semantically meaningful typecodes are desired for IDs.
# Solution described at <https://gist.github.com/dwinston/083a1cb508bbff21d055e7613f3ac02f>.
# In essence, bridging is needed between (a) the now-legacy shoulders and identifier structure
# `nmdc:<shoulder><generated_id>`and (b) the desired structure
# `nmdc:<type_code><shoulder><generated_id>`.
# The difference in shoulder structure is that legacy shoulders are of the pattern r"[a-z]+[0-9]",
# whereas current shoulders are to be of the pattern r"[0-9][a-z]*[0-9]" so that, in concert with
# the requirement that typcodes be of the pattern r"[a-z]{1,6}", a processor can identify (optional)
# typecode and subsequent shoulder syntactically.


def double_iter(iterable):
    return zip(tee(iterable))


def construct_models(naan_aliases, typecodes, shoulders):
    @lru_cache
    def typecode_info(typecode):
        for code, info in typecodes.items():
            if typecode == code:
                return info["type"], info["note"]
        else:
            raise ValueError(f"typecode '{typecode}' not found")

    fake_shoulders = shoulders["fake"]
    allocated_shoulders = shoulders["allocated"]
    shoulder_values = fake_shoulders + allocated_shoulders

    _naa = rf"(?P<naa>({'|'.join(list(naan_aliases.values()))}))"
    _blade = rf"(?P<blade>[{base32_chars}]{{4,}})"
    _typecode = rf"(?P<typecode>({'|'.join(typecodes)})"
    _shoulder = rf"(?P<shoulder>({'|'.join(shoulder_values)}))"
    _assigned_base_name = rf"{_typecode}{_shoulder}{_blade}"
    _base_object_name = rf"{_naa}:{_assigned_base_name}"

    id_pattern = {
        "naa": re.compile(_naa),
        "blade": re.compile(_blade),
        "typecode": re.compile(_typecode),
        "shoulder": re.compile(_shoulder),
        "assigned_base_name": re.compile(_assigned_base_name),
        "base_object_name": re.compile(_base_object_name),
    }

    Naa = Enum("Naa", names=zip(tee(naan_aliases.values())), type=str)
    Blade = constr(regex=_blade, min_length=4)

    Typecode = Enum(
        "Typecode",
        names=zip(tee(typecodes)),
        type=str,
    )

    Shoulder = Enum("Shoulder", names=zip(tee(shoulder_values)), type=str)
    BaseObjectName = constr(regex=_base_object_name)

    NameAssigningAuthority = Literal[tuple(naan_aliases.values())]

    class MintRequest(BaseModel):
        naa: NameAssigningAuthority = naan_aliases["default"]
        typecode: Typecode = typecodes["default"]
        shoulder: Shoulder = shoulders["default"]
        number: PositiveInt = 1

    class StructuredId(BaseModel):
        naa: Naa
        typecode: Typecode
        shoulder: Shoulder
        blade: Blade

    class IdBindings(BaseModel):
        where: BaseObjectName

    class IdBindingOp(str, Enum):
        set = "set"
        addToSet = "addToSet"
        rm = "rm"
        purge = "purge"

    class IdBindingRequest(BaseModel):
        i: BaseObjectName
        o: IdBindingOp = IdBindingOp.set
        a: Optional[str]
        v: Any

        @root_validator()
        def set_or_add_needs_value(cls, values):
            op = values.get("o")
            if op in (IdBindingOp.set, IdBindingOp.addToSet):
                if "v" not in values:
                    raise ValueError("{'set','add'} operations needs value 'v'.")
            return values

        @root_validator()
        def set_or_add_or_rm_needs_attribute(cls, values):
            op = values.get("o")
            if op in (IdBindingOp.set, IdBindingOp.addToSet, IdBindingOp.rm):
                if not values.get("a"):
                    raise ValueError(
                        "{'set','add','rm'} operations need attribute 'a'."
                    )
            return values

    return {
        "typecode_info": typecode_info,
        "id_pattern": id_pattern,
        "models": {
            "MintRequest": MintRequest,
            "StructuredId": StructuredId,
            "IdBindings": IdBindings,
            "IdBindingRequest": IdBindingRequest,
        },
    }
