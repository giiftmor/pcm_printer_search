from flask import request, jsonify
from modules.user_lookup import bp
from modules.user_lookup.urls import (
    GROUPER_GROUP_PRESETS,
    build_grouper_group_url,
    build_idm_consolidation_url,
    build_idm_password_url,
    build_grouper_url,
)


@bp.route('/api/user-lookup/urls', methods=['GET'])
def get_urls():
    user_id = request.args.get('user_id', '').strip()
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    return jsonify({
        'user_id': user_id,
        'urls': {
            'idm_consolidation': build_idm_consolidation_url(user_id),
            'idm_password': build_idm_password_url(user_id),
            'grouper': build_grouper_url(user_id),
        }
    })


@bp.route('/api/user-lookup/grouper-presets', methods=['GET'])
def grouper_presets():
    presets = [
        {**p, 'url': build_grouper_group_url(p['name'])}
        for p in GROUPER_GROUP_PRESETS
    ]
    return jsonify({'presets': presets})


@bp.route('/api/user-lookup/group-url', methods=['GET'])
def grouper_group_url():
    name = request.args.get('name', '').strip()
    url = build_grouper_group_url(name)
    if url is None:
        return jsonify({'error': 'name is required'}), 400
    return jsonify({'url': url, 'name': name})
