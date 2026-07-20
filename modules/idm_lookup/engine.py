IDM_BASE_URL = "https://idm.nwu.ac.za/profileinfo/profileinfo.jsp"


def build_idm_url(user_id: str) -> str:
    user_id = user_id.strip()
    if not user_id:
        return None
    return f"{IDM_BASE_URL}?Menu=Consolidation&USN={user_id}"


def validate_user_id(user_id: str) -> bool:
    return bool(user_id and user_id.strip())
