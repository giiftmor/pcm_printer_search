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


GROUPER_GROUP_PRESETS = [
    {"id": "papercut-staff", "label": "Papercut Staff Include", "url": "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=928bd04dcf244ccf8a8a6d61c78dd7b1&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Papercut_pcm_staff_include&subjectId=928bd04dcf244ccf8a8a6d61c78dd7b1&name=nwu%3Agroups%3Apapercut%3APapercut_pcm_staff_include&subjectType=group&sourceId=g%3Agsa"},
    {"id": "azure-staff", "label": "Azure Staff", "url": "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=8eed182c75ec4b648b64672d2dd8511a&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Add+extra+staff+to+office+365&subjectId=8eed182c75ec4b648b64672d2dd8511a&name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff&subjectType=group&sourceId=g%3Agsa"},
    {"id": "ms-full-staff", "label": "MS Full Staff License", "url": "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=885780297fb64a3c8e568b29c50f68b8&typeName=group&returnTo=%2FdoSearchSubjects.do&description=msfed_include_full_staff_license&subjectId=885780297fb64a3c8e568b29c50f68b8&name=nwu%3Agroups%3Amslicenses%3Amsfed_include_full_staff_license&subjectType=group&sourceId=g%3Agsa"},
    {"id": "ms-activate", "label": "MS Activate", "url": "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=bc7da4ab2b0d4e97852f42a343a530c7&typeName=group&returnTo=%2FdoSearchSubjects.do&description=ms_activate&subjectId=bc7da4ab2b0d4e97852f42a343a530c7&name=nwu%3Agroups%3Amslicenses%3Ams_activate&subjectType=group&sourceId=g%3Agsa"},
    {"id": "azure-students", "label": "Azure Students", "url": "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=fefea6d36fdc4d12acde72596648d0ba&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Add+extra+students+to+office+365&subjectId=fefea6d36fdc4d12acde72596648d0ba&name=nwu%3Agroups%3AAzure%3AAzure_Include_Students&subjectType=group&sourceId=g%3Agsa"},
    {"id": "acrobat", "label": "Acrobat", "url": "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=62d5747d54314b1f96cda7cbc54afdf2&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Acrobat_fedID_users&subjectId=62d5747d54314b1f96cda7cbc54afdf2&name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users&subjectType=group&sourceId=g%3Agsa"},
    {"id": "acrobat-include", "label": "Acrobat Include", "url": "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=95653bbe87d646f7829fab2ef82c39e5&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Acrobat_fedID_users_include&subjectId=95653bbe87d646f7829fab2ef82c39e5&name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users_include&subjectType=group&sourceId=g%3Agsa"},
]
