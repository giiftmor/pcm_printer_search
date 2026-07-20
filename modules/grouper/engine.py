GROUPER_BASE_URL = "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do"


def build_grouper_url(user_id: str) -> str:
    user_id = user_id.strip()
    if not user_id:
        return None
    return (
        f"{GROUPER_BASE_URL}"
        f"?id={user_id}"
        f"&typeName=person"
        f"&subjectId={user_id}"
        f"&name={user_id}"
        f"&subjectType=person"
        f"&sourceId=NWUSource0"
    )


def validate_user_id(user_id: str) -> bool:
    return bool(user_id and user_id.strip())
