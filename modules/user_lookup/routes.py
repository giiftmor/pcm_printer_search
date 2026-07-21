from flask import request, jsonify
from modules.user_lookup import bp
from modules.user_lookup.urls import (
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
