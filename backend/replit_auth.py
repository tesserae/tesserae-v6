"""
Replit Auth integration using flask-dance OAuth2.
"""
import jwt
from jwt import PyJWKClient
import os
import uuid
from functools import wraps
from urllib.parse import urlencode

from flask import g, session, redirect, request, url_for
from flask_dance.consumer import (
    OAuth2ConsumerBlueprint,
    oauth_authorized,
    oauth_error,
)
from flask_dance.consumer.storage import BaseStorage
from flask_login import LoginManager, login_user, logout_user, current_user
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from sqlalchemy.exc import NoResultFound

from backend.models import db, OAuth, User

ISSUER_URL = os.environ.get('ISSUER_URL', "https://replit.com/oidc")
JWKS_URL = "https://replit.com/.well-known/jwks.json"
JWKS_CLIENT = None

def get_jwks_client():
    global JWKS_CLIENT
    if JWKS_CLIENT is None:
        try:
            JWKS_CLIENT = PyJWKClient(JWKS_URL)
        except Exception:
            JWKS_CLIENT = None
    return JWKS_CLIENT

login_manager = None
replit_bp = None

def init_auth(app):
    """Initialize authentication for the Flask app"""
    global login_manager, replit_bp
    
    login_manager = LoginManager(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
    
    replit_bp = make_replit_blueprint()
    app.register_blueprint(replit_bp, url_prefix="/api/auth")
    
    return replit_bp

class UserSessionStorage(BaseStorage):
    def get(self, blueprint):
        try:
            token = db.session.query(OAuth).filter_by(
                user_id=current_user.get_id(),
                browser_session_key=g.browser_session_key,
                provider=blueprint.name,
            ).one().token
        except NoResultFound:
            token = None
        return token

    def set(self, blueprint, token):
        db.session.query(OAuth).filter_by(
            user_id=current_user.get_id(),
            browser_session_key=g.browser_session_key,
            provider=blueprint.name,
        ).delete()
        new_model = OAuth()
        new_model.user_id = current_user.get_id()
        new_model.browser_session_key = g.browser_session_key
        new_model.provider = blueprint.name
        new_model.token = token
        db.session.add(new_model)
        db.session.commit()

    def delete(self, blueprint):
        db.session.query(OAuth).filter_by(
            user_id=current_user.get_id(),
            browser_session_key=g.browser_session_key,
            provider=blueprint.name).delete()
        db.session.commit()

def make_replit_blueprint():
    try:
        repl_id = os.environ['REPL_ID']
    except KeyError:
        raise SystemExit("the REPL_ID environment variable must be set")

    issuer_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc")

    bp = OAuth2ConsumerBlueprint(
        "replit_auth",
        __name__,
        client_id=repl_id,
        client_secret=None,
        base_url=issuer_url,
        authorization_url_params={"prompt": "login consent"},
        token_url=issuer_url + "/token",
        token_url_params={"auth": (), "include_client_id": True},
        auto_refresh_url=issuer_url + "/token",
        auto_refresh_kwargs={"client_id": repl_id},
        authorization_url=issuer_url + "/auth",
        use_pkce=True,
        code_challenge_method="S256",
        scope=["openid", "profile", "email", "offline_access"],
        storage=UserSessionStorage(),
        login_url="/login",
        authorized_url="/callback",
    )

    @bp.before_app_request
    def set_applocal_session():
        if '_browser_session_key' not in session:
            session['_browser_session_key'] = uuid.uuid4().hex
        session.modified = True
        g.browser_session_key = session['_browser_session_key']
        g.flask_dance_replit = bp.session

    @bp.route("/logout")
    def logout():
        del bp.token
        logout_user()

        end_session_endpoint = issuer_url + "/session/end"
        encoded_params = urlencode({
            "client_id": repl_id,
            "post_logout_redirect_uri": request.url_root,
        })
        logout_url = f"{end_session_endpoint}?{encoded_params}"
        return redirect(logout_url)

    return bp

def save_user(user_claims):
    user = User()
    user.id = user_claims['sub']
    user.email = user_claims.get('email')
    user.first_name = user_claims.get('first_name')
    user.last_name = user_claims.get('last_name')
    user.profile_image_url = user_claims.get('profile_image_url')
    merged_user = db.session.merge(user)
    db.session.commit()
    return merged_user

@oauth_authorized.connect
def logged_in(blueprint, token):
    try:
        jwks_client = get_jwks_client()
        if jwks_client:
            signing_key = jwks_client.get_signing_key_from_jwt(token['id_token'])
            user_claims = jwt.decode(
                token['id_token'],
                signing_key.key,
                algorithms=["RS256"],
                audience=os.environ.get('REPL_ID'),
                issuer=ISSUER_URL,
            )
        else:
            user_claims = jwt.decode(token['id_token'], options={"verify_signature": False})
    except Exception as e:
        print(f"JWT validation failed, falling back to unverified decode: {e}")
        try:
            user_claims = jwt.decode(token['id_token'], options={"verify_signature": False})
        except Exception as e2:
            print(f"JWT decode failed completely: {e2}")
            return redirect('/')
    user = save_user(user_claims)
    login_user(user)
    blueprint.token = token
    next_url = session.pop("next_url", None)
    if next_url is not None:
        return redirect(next_url)

@oauth_error.connect
def handle_error(blueprint, error, error_description=None, error_uri=None):
    return redirect('/')

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            session["next_url"] = request.url
            return redirect(url_for('replit_auth.login'))
        return f(*args, **kwargs)
    return decorated_function

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
