"""
Simple password-based authentication for Marvin deployment.
Used when DEPLOYMENT_ENV=marvin (not on Replit).
"""
import os
import uuid
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from flask import Blueprint, g, session, redirect, request, url_for, jsonify
from flask_login import LoginManager, login_user, logout_user, current_user

from backend.models import db, User

login_manager = None
marvin_auth_bp = None

def init_marvin_auth(app):
    """Initialize password-based authentication for Marvin"""
    global login_manager, marvin_auth_bp
    
    login_manager = LoginManager(app)
    login_manager.login_view = 'marvin_auth.login_page'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
    
    marvin_auth_bp = create_marvin_auth_blueprint()
    
    deployment_env = os.environ.get('DEPLOYMENT_ENV', 'replit')
    if deployment_env == 'marvin':
        app.register_blueprint(marvin_auth_bp, url_prefix="")
    else:
        app.register_blueprint(marvin_auth_bp, url_prefix="/api")
    
    return marvin_auth_bp

def create_marvin_auth_blueprint():
    """Create the authentication blueprint with all routes"""
    bp = Blueprint('marvin_auth', __name__)
    
    @bp.before_app_request
    def set_session_key():
        if '_browser_session_key' not in session:
            session['_browser_session_key'] = uuid.uuid4().hex
        session.modified = True
        g.browser_session_key = session['_browser_session_key']
    
    @bp.route('/auth/register', methods=['POST'])
    def register():
        """Register a new user with email and password"""
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400
        
        if len(password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'error': 'An account with this email already exists'}), 400
        
        user = User()
        user.id = uuid.uuid4().hex
        user.email = email
        user.password_hash = generate_password_hash(password)
        user.first_name = first_name
        user.last_name = last_name
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'orcid': user.orcid,
                'orcid_name': user.orcid_name,
            }
        })
    
    @bp.route('/auth/login', methods=['POST'])
    def login():
        """Log in with email and password"""
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.password_hash:
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
        
        if not check_password_hash(user.password_hash, password):
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
        
        login_user(user)
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'orcid': user.orcid,
                'orcid_name': user.orcid_name,
            }
        })
    
    @bp.route('/auth/logout', methods=['GET', 'POST'])
    def logout():
        """Log out the current user"""
        logout_user()
        if request.method == 'POST':
            return jsonify({'success': True})
        return redirect('/')
    
    return bp

def get_current_user_info():
    """Return current user info as dict for API responses"""
    if current_user.is_authenticated:
        return {
            'id': current_user.id,
            'email': current_user.email,
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'profile_image_url': current_user.profile_image_url,
            'institution': current_user.institution,
            'orcid': current_user.orcid,
            'orcid_name': current_user.orcid_name,
        }
    return None

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('marvin_auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function

def update_user_orcid(user_id, orcid, orcid_name=None):
    """Link an ORCID to a user account"""
    user = User.query.get(user_id)
    if user:
        user.orcid = orcid
        user.orcid_name = orcid_name
        db.session.commit()
        return True
    return False

def unlink_user_orcid(user_id):
    """Remove ORCID from a user account"""
    user = User.query.get(user_id)
    if user:
        user.orcid = None
        user.orcid_name = None
        db.session.commit()
        return True
    return False
