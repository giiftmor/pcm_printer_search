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
