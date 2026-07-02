"""
Simple password-based authentication for Marvin deployment.
Used when DEPLOYMENT_ENV=marvin (not on Replit).
"""
import os
import re
import uuid
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from flask import Blueprint, g, session, redirect, request, url_for, jsonify
from flask_login import LoginManager, login_user, logout_user, current_user

from backend.models import db, User
from backend.db_utils import get_db_cursor
from backend.logging_config import get_logger

login_manager = None
marvin_auth_bp = None
logger = get_logger('marvin_auth')


def _client_ip():
    forwarded_for = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return forwarded_for or request.remote_addr or 'unknown'


def _validate_password_policy(password):
    """Return an error message if password does not meet policy, else None."""
    if len(password) < 8:
        return 'Password must be at least 8 characters long'
    if not re.search(r'[A-Z]', password):
        return 'Password must include at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return 'Password must include at least one lowercase letter'
    if not re.search(r'\d', password):
        return 'Password must include at least one number'
    if not re.search(r'[^A-Za-z0-9\s]', password):
        return 'Password must include at least one special character'
    return None


def _load_user_roles(user_id):
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT r.name
                FROM roles r
                JOIN user_roles ur ON ur.role_id = r.id
                WHERE ur.user_id = %s
                """,
                (user_id,),
            )
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.warning(f"Failed to load roles for user_id={user_id}: {e}")
        return []


def _load_user_roles_by_email(email):
    """Load roles by email via users->user_roles join (fallback for legacy id mismatches)."""
    normalized_email = (email or '').strip().lower()
    if not normalized_email:
        return []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT r.name
                FROM users u
                JOIN user_roles ur ON ur.user_id = u.id
                JOIN roles r ON r.id = ur.role_id
                WHERE LOWER(COALESCE(u.email, '')) = %s
                """,
                (normalized_email,),
            )
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.warning(f"Failed to load roles for email={normalized_email}: {e}")
        return []


def _is_admin_account(user_id, email=None):
    """True if account has ADMIN or SUPER_ADMIN role."""
    roles = [str(role).upper() for role in _load_user_roles(user_id)]
    if email:
        roles.extend(str(role).upper() for role in _load_user_roles_by_email(email))
    return any(role in ('ADMIN', 'SUPER_ADMIN') for role in roles)


def _ensure_user_role(role_name='USER'):
    """Ensure role exists and return role_id."""
    with get_db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO roles (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            (role_name, 'Standard user' if role_name == 'USER' else role_name),
        )
        cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
        row = cur.fetchone()
        return row[0] if row else None


def _assign_role_to_user(user_id, role_name='USER', assigned_by='self_register'):
    """Assign role to user if not already assigned."""
    role_id = _ensure_user_role(role_name)
    if not role_id:
        raise RuntimeError(f"Role '{role_name}' not found")

    with get_db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)
            VALUES (%s, %s, NOW(), %s)
            ON CONFLICT (user_id, role_id) DO NOTHING
            """,
            (user_id, role_id, assigned_by),
        )


def init_marvin_auth(app):
    """Initialize password-based authentication for Marvin"""
    global login_manager, marvin_auth_bp
    
    login_manager = LoginManager(app)
    # Frontend handles login UI; keep API responses explicit instead of redirecting to a missing endpoint.
    login_manager.login_view = None
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
    
    marvin_auth_bp = create_marvin_auth_blueprint()

    # Use API_PREFIX from app.py so auth routes match all other routes.
    # Previously this checked DEPLOYMENT_ENV independently, causing a mismatch
    # when DEPLOYMENT_ENV=marvin but DIRECT_SERVER=1 (dev server scenario).
    from backend.app import API_PREFIX
    app.register_blueprint(marvin_auth_bp, url_prefix=API_PREFIX or None)
    
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
        if os.environ.get('DISABLE_SELF_REGISTER', 'false').lower() in ('true', '1', 'yes'):
            logger.warning(f"Registration blocked (disabled) from ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Self-registration is disabled'}), 403
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        if not email or not password:
            logger.warning(f"Registration rejected (missing credentials) email={email or 'unknown'} ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400

        password_error = _validate_password_policy(password)
        if password_error:
            logger.warning(f"Registration rejected (password policy) email={email} ip={_client_ip()}")
            return jsonify({'success': False, 'error': password_error}), 400
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            logger.info(f"Registration duplicate email blocked email={email} ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'An account with this email already exists'}), 400
        
        user = User()
        user.id = uuid.uuid4().hex
        user.email = email
        user.password_hash = generate_password_hash(password)
        user.first_name = first_name
        user.last_name = last_name
        
        db.session.add(user)
        db.session.commit()

        try:
            _assign_role_to_user(user.id, 'USER', assigned_by='self_register')
        except Exception as e:
            logger.error(f"Failed to assign USER role during registration for {email}: {e}")
            try:
                db.session.delete(user)
                db.session.commit()
            except Exception as cleanup_err:
                logger.error(f"Failed to rollback user creation after role assignment error: {cleanup_err}")
            return jsonify({'success': False, 'error': 'Failed to finalize registration'}), 500
        
        login_user(user)
        logger.info(f"User registered and logged in user_id={user.id} email={user.email} ip={_client_ip()}")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'orcid': user.orcid,
                'orcid_name': user.orcid_name,
                'must_reset_password': user.must_reset_password,
                'roles': _load_user_roles(user.id),
            }
        })
    
    @bp.route('/auth/login', methods=['POST'])
    def login():
        """Log in with email and password"""
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            logger.warning(f"Login rejected (missing credentials) email={email or 'unknown'} ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.password_hash:
            logger.warning(f"Login failed (user not found/no password) email={email} ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
        
        if not check_password_hash(user.password_hash, password):
            logger.warning(f"Login failed (bad password) email={email} ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401

        if _is_admin_account(user.id, email=user.email):
            logger.warning(f"Public login blocked for admin account user_id={user.id} email={user.email} ip={_client_ip()}")
            return jsonify({
                'success': False,
                'error': 'Not authorised',
            }), 403
        
        login_user(user)
        logger.info(f"User login success user_id={user.id} email={user.email} ip={_client_ip()}")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'orcid': user.orcid,
                'orcid_name': user.orcid_name,
                'must_reset_password': user.must_reset_password,
                'roles': _load_user_roles(user.id),
            }
        })
    
    @bp.route('/auth/logout', methods=['GET', 'POST'])
    def logout():
        """Log out the current user"""
        if current_user.is_authenticated:
            logger.info(f"User logout user_id={current_user.id} email={current_user.email} ip={_client_ip()}")
        logout_user()
        if request.method == 'POST':
            return jsonify({'success': True})
        return redirect('/')

    @bp.route('/auth/reset-password', methods=['POST'])
    def reset_password():
        """Reset password for the current user"""
        if not current_user.is_authenticated:
            logger.warning(f"Password reset rejected (unauthenticated) ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        data = request.get_json() or {}
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not new_password or not confirm_password:
            logger.warning(f"Password reset rejected (missing password) user_id={current_user.id} ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Password is required'}), 400
        if new_password != confirm_password:
            logger.warning(f"Password reset rejected (mismatch) user_id={current_user.id} ip={_client_ip()}")
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400

        password_error = _validate_password_policy(new_password)
        if password_error:
            logger.warning(f"Password reset rejected (policy) user_id={current_user.id} ip={_client_ip()}")
            return jsonify({'success': False, 'error': password_error}), 400

        current_user.password_hash = generate_password_hash(new_password)
        current_user.must_reset_password = False
        db.session.commit()
        logger.info(f"Password reset success user_id={current_user.id} email={current_user.email} ip={_client_ip()}")

        return jsonify({'success': True})
    
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
            'must_reset_password': current_user.must_reset_password,
            'roles': _load_user_roles(current_user.id),
        }
    return None

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect('/')
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
