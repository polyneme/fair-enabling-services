from operator import itemgetter
from typing import Union

from fastapi import FastAPI

from minter.util.models import construct_models
from minter.util.idgen import generate_ids

app = FastAPI()


_rv = construct_models(
    naan_aliases={"76954": "nmdc", "default": "nmdc"},
    shoulders={
        "fake": ["1fk1"],
        "allocated": ["11"],
        "default": "1fk1",
    },
    typecodes={
        "sa": {"type": "nmdc:Biosample", "note": "a sample"},
        "st": {"type": "nmdc:Study", "note": "a study"},
        "saw": {
            "type": "prov:NamedThing",
            "note": "the workflow/plan for sampling / sample prep",
        },
        "saa": {
            "type": "prov:BiosampleProcessing",
            "note": (
                "sample activity (sa prov:wasGeneratedBy saa, saa prov:used saw) "
                "- the execution of the plan"
            ),
        },
        "p": {
            "type": "nmdc:Agent",
            "note": "party (e.g. instrument, person, software agent)",
        },
        "do": {"type": "nmdc:DataObject", "note": "data object"},
        "opw": {
            "type": "nmdc:NamedThing",
            "note": "omics processing - the workflow/plan for data object (do) production",
        },
        "opa": {
            "type": "nmdc:OmicsProcessing",
            "note": (
                "omics processing activity (opa prov:used sample, do prov:wasGeneratedBy opa) "
                "- the execution of the plan"
            ),
        },
        "oaw": {
            "type": "nmdc:NamedThing",
            "note": "omics analysis - the (computational) workflow/plan",
        },
        "oaa": {
            "type": "nmdc:WorkflowExecutionActivity",
            "note": (
                "omics analysis activity (oaa prov:used do, oaa prov:used oa, "
                "do prov:wasGeneratedBy oaa) - "
                "the execution of the plan"
            ),
        },
        "sys": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "sysqy": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "sysop": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "syssc": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "syspt": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "sysdo": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "sysjob": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "sysrun": {
            "type": "nmdc:NamedThing",
            "note": "for internal use by the nmdc-runtime site",
        },
        "default": "oaa",
    },
)

typecode_info, id_pattern = itemgetter("typecode_info", "id_pattern")(_rv)
MintRequest, StructuredId, IdBindings, IdBindingRequest = itemgetter(
    "MintRequest",
    "StructuredId",
    "IdBindings",
    "IdBindingRequest",
)(_rv["models"])


@app.post("/ids/mint", response_model=list[str])
def mint_ids(
    mint_req: MintRequest,
):
    """Generate one or more identifiers.

    Leaving `populator` blank will set it to the site ID of the request client.
    """
    ids = generate_ids(
        mdb,
        owner=site.id,
        populator=(mint_req.populator or site.id),
        number=mint_req.number,
        naa=mint_req.naa,
        shoulder=mint_req.shoulder,
        typecode=mint_req.typecode,
    )
    return ids


@app.post("/ids/bindings", response_model=List[Dict[str, Any]])
def set_id_bindings(
    binding_requests: List[IdBindingRequest],
    mdb: MongoDatabase = Depends(get_mongo_db),
    site: Site = Depends(get_current_client_site),
):
    bons = [r.i for r in binding_requests]  # "Base Object Names"
    ids: List[Union[StructuredId, LegacyStructuredId]] = []
    for bon in bons:
        if m := re.match(pattern["base_object_name"], bon):
            ids.append(
                StructuredId(
                    naa=m.group("naa"),
                    typecode=m.group("typecode"),
                    shoulder=m.group("shoulder"),
                    blade=m.group("blade"),
                )
            )
        elif m := re.match(pattern["legacy"]["base_object_name"], bon):
            ids.append(
                LegacyStructuredId(
                    naa=m.group("naa"),
                    shoulder=m.group("shoulder"),
                    blade=m.group("blade"),
                )
            )
    # Ensure that user owns all supplied identifiers.
    for id_, r in zip(ids, binding_requests):
        # TODO check typecode if non-legacy ID
        collection = mdb.get_collection(collection_name(id_.naa, id_.shoulder))
        doc = collection.find_one({"_id": decode_id(str(id_.blade))}, ["__ao"])
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"id {r.i} not found",
            )
        elif doc.get("__ao") != site.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"authenticated site client does not manage {r.i} "
                    f"(client represents site {site.id}).",
                ),
            )
    # Ensure no attempts to set reserved attributes.
    if any(r.a.startswith("__a") for r in binding_requests):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot set attribute names beginning with '__a'.",
        )
    # Process binding requests
    docs = []
    for id_, r in zip(ids, binding_requests):
        collection = mdb.get_collection(collection_name(id_.naa, id_.shoulder))

        filter_ = {"_id": decode_id(id_.blade)}
        if r.o == "purge":
            docs.append(collection.find_one_and_delete(filter_))
        elif r.o == "rm":
            docs.append(collection.find_one_and_update(filter_, {"$unset": {r.a: ""}}))
        elif r.o == "set":
            docs.append(collection.find_one_and_update(filter_, {"$set": {r.a: r.v}}))
        elif r.o == "addToSet":
            docs.append(
                collection.find_one_and_update(filter_, {"$addToSet": {r.a: r.v}})
            )
        else:
            # Note: IdBindingRequest root_validator methods should preclude this.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid operation 'o'."
            )

        return [dissoc(d, "_id") for d in docs]


@app.get("/ids/bindings/{rest:path}", response_model=Dict[str, Any])
def get_id_bindings(
    rest: str,
    mdb: MongoDatabase = Depends(get_mongo_db),
):
    # TODO legacy/non-legacy handling
    cleaned = rest.replace("-", "")
    parts = cleaned.split(":")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid ID - needs both name assigning authority (NAA) part"
                "(e.g. 'nmdc') and name part (e.g. 'fk4ra92'), separated by a colon (':')."
            ),
        )
    naa = parts[0]
    suffix_parts = parts[1].split("/")
    if len(suffix_parts) == 2 and suffix_parts[-1] != "":  # one '/', or ends with '/'
        assigned_base_name, attribute = suffix_parts
    else:
        assigned_base_name = suffix_parts[0]
        attribute = None

    if re.match(pattern["naa"], naa) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID - invalid name assigning authority (NAA) '{naa}'.",
        )
    print(assigned_base_name)
    if re.match(pattern["shoulder"], assigned_base_name) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid ID - invalid shoulder. "
                "Every name part begins with a 'shoulder', a "
                "sequence of letters followed by a number, "
                "for example 'fk4'. "
                "Did you forget to include the shoulder?",
            ),
        )
    try:
        m = re.match(
            pattern["assigned_base_name"], AssignedBaseName(assigned_base_name)
        )
        shoulder, blade = m.group("shoulder"), m.group("blade")
        id_decoded = decode_id(blade)
    except (AttributeError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID - characters used outside of base32.",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID - failed checksum. Did you copy it incorrectly?",
        )

    collection = mdb.get_collection(collection_name(naa, shoulder))
    d = raise404_if_none(collection.find_one({"_id": id_decoded}))
    d = dissoc(d, "_id")
    if attribute is not None:
        if attribute not in d:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"attribute '{attribute}' not found in "
                    f"{naa}:{assigned_base_name}."
                ),
            )
        rv = pick(["where", attribute], d)
    else:
        rv = d
    return rv
