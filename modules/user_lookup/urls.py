from urllib.parse import quote

IDM_BASE = 'https://idm.nwu.ac.za/profileinfo/profileinfo.jsp'
GROUPER_BASE = 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do'


def build_idm_consolidation_url(user_id: str) -> str:
    return f'{IDM_BASE}?Menu=Consolidation&USN={quote(user_id, safe="")}'


def build_idm_password_url(user_id: str) -> str:
    return f'{IDM_BASE}?Menu=Pwd&USN={quote(user_id, safe="")}'


def build_grouper_url(user_id: str) -> str:
    params = (
        f'returnToLinkKey=subject.action.return-results'
        f'&id={quote(user_id, safe="")}'
        f'&typeName=person'
        f'&returnTo=%2FdoSearchSubjects.do'
        f'&subjectId={quote(user_id, safe="")}'
        f'&name={quote(user_id, safe="")}'
        f'&subjectType=person'
        f'&sourceId=NWUSource'
    )
    return f'{GROUPER_BASE}?{params}'


GROUPER_GROUP_BASE = 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do'

GROUPER_GROUP_PRESETS = [
    {"id": "papercut-staff", "label": "Papercut Staff Include", "name": "Papercut_pcm_staff_include"},
    {"id": "azure-staff", "label": "Azure Staff", "name": "nwu:groups:Azure:Azure_Include_Staff"},
    {"id": "ms-full-staff", "label": "MS Full Staff License", "name": "nwu:groups:mslicenses:msfed_include_full_staff_license"},
    {"id": "ms-activate", "label": "MS Activate", "name": "nwu:groups:mslicenses:ms_activate"},
    {"id": "azure-students", "label": "Azure Students", "name": "nwu:groups:Azure:Azure_Include_Students"},
    {"id": "acrobat", "label": "Acrobat", "name": "nwu:groups:Adobe:Acrobat_fedID_users"},
    {"id": "acrobat-include", "label": "Acrobat Include", "name": "nwu:groups:Adobe:Acrobat_fedID_users_include"},
]


def build_grouper_group_url(group_name: str, description: str | None = None) -> str | None:
    name = (group_name or "").strip()
    if not name:
        return None
    params = [
        ("returnToLinkKey", "subject.action.return-results"),
        ("typeName", "group"),
        ("returnTo", "/doSearchSubjects.do"),
        ("name", name),
        ("subjectType", "group"),
        ("sourceId", "g:gsa"),
    ]
    if description:
        params.append(("description", description))
    qs = "&".join(f"{k}={quote(v, safe='')}" for k, v in params)
    return f"{GROUPER_GROUP_BASE}?{qs}"
