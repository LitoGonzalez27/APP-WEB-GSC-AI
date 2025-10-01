#!/usr/bin/env python3
"""
Endpoint de diagnóstico para verificar imports del sistema
"""

from flask import Blueprint, jsonify
from auth import admin_required
import sys
import traceback

diagnostic_bp = Blueprint('diagnostic', __name__, url_prefix='/diagnostic')

@diagnostic_bp.route('/imports', methods=['GET'])
@admin_required
def check_imports():
    """Diagnóstico de imports del sistema"""
    
    results = {
        'timestamp': str(__import__('datetime').datetime.now()),
        'python_version': sys.version,
        'imports': {}
    }
    
    # Test 1: quota_manager
    try:
        from quota_manager import get_user_quota_status
        results['imports']['quota_manager'] = {'status': 'OK', 'type': str(type(get_user_quota_status))}
    except Exception as e:
        results['imports']['quota_manager'] = {'status': 'FAILED', 'error': str(e), 'traceback': traceback.format_exc()}
    
    # Test 2: quota_middleware
    try:
        from quota_middleware import quota_protected_serp_call
        results['imports']['quota_middleware'] = {'status': 'OK', 'type': str(type(quota_protected_serp_call))}
    except Exception as e:
        results['imports']['quota_middleware'] = {'status': 'FAILED', 'error': str(e), 'traceback': traceback.format_exc()}
    
    # Test 3: services.serp_service
    try:
        from services.serp_service import get_serp_json
        results['imports']['serp_service'] = {
            'status': 'OK', 
            'type': str(type(get_serp_json)),
            'callable': callable(get_serp_json)
        }
    except Exception as e:
        results['imports']['serp_service'] = {'status': 'FAILED', 'error': str(e), 'traceback': traceback.format_exc()}
    
    # Test 4: services.ai_analysis
    try:
        from services.ai_analysis import detect_ai_overview_elements
        results['imports']['ai_analysis'] = {'status': 'OK', 'type': str(type(detect_ai_overview_elements))}
    except Exception as e:
        results['imports']['ai_analysis'] = {'status': 'FAILED', 'error': str(e), 'traceback': traceback.format_exc()}
    
    # Test 5: services.ai_cache
    try:
        from services.ai_cache import ai_cache
        results['imports']['ai_cache'] = {'status': 'OK', 'available': ai_cache is not None}
    except Exception as e:
        results['imports']['ai_cache'] = {'status': 'FAILED', 'error': str(e), 'traceback': traceback.format_exc()}
    
    # Test 6: manual_ai_system module state
    try:
        import manual_ai_system
        results['imports']['manual_ai_system'] = {
            'status': 'OK',
            'get_serp_json_available': manual_ai_system.get_serp_json is not None,
            'get_serp_json_value': str(manual_ai_system.get_serp_json)
        }
    except Exception as e:
        results['imports']['manual_ai_system'] = {'status': 'FAILED', 'error': str(e), 'traceback': traceback.format_exc()}
    
    # Test 7: Environment variables relevantes
    import os
    results['environment'] = {
        'ENFORCE_QUOTAS': os.getenv('ENFORCE_QUOTAS', 'not set'),
        'SERPAPI_KEY': 'SET' if os.getenv('SERPAPI_KEY') else 'NOT SET',
        'DATABASE_URL': 'SET' if os.getenv('DATABASE_URL') else 'NOT SET'
    }
    
    return jsonify(results), 200

