"""
SQLAlchemy models for Replit Auth and user data.
These run alongside existing psycopg2 code for legacy tables.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    institution = db.Column(db.String, nullable=True)
    orcid = db.Column(db.String(19), nullable=True)
    orcid_name = db.Column(db.String, nullable=True)
    share_to_public_default = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    saved_searches = db.relationship('SavedSearch', backref='user', lazy=True, cascade='all, delete-orphan')
    saved_intertexts = db.relationship('SavedIntertext', backref='owner', lazy=True, cascade='all, delete-orphan')

class OAuth(OAuthConsumerMixin, db.Model):
    __tablename__ = 'oauth'
    user_id = db.Column(db.String, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)

    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_key_provider',
    ),)

class SavedSearch(db.Model):
    __tablename__ = 'saved_searches'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey(User.id), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(10), default='la')
    source_author = db.Column(db.String(255))
    source_work = db.Column(db.String(255))
    source_section = db.Column(db.String(255))
    target_author = db.Column(db.String(255))
    target_work = db.Column(db.String(255))
    target_section = db.Column(db.String(255))
    match_type = db.Column(db.String(50), default='lemma')
    min_matches = db.Column(db.Integer, default=2)
    stoplist_basis = db.Column(db.String(50), default='corpus')
    stoplist_size = db.Column(db.Integer, default=10)
    max_distance = db.Column(db.Integer, default=10)
    source_unit_type = db.Column(db.String(20), default='line')
    target_unit_type = db.Column(db.String(20), default='line')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Intertext(db.Model):
    __tablename__ = 'intertexts'
    id = db.Column(db.Integer, primary_key=True)
    source_text_id = db.Column(db.String(255), nullable=False)
    source_author = db.Column(db.String(255), nullable=True)
    source_work = db.Column(db.String(255), nullable=True)
    source_reference = db.Column(db.String(100), nullable=False)
    source_snippet = db.Column(db.Text, nullable=False)
    source_language = db.Column(db.String(10), default='la')
    target_text_id = db.Column(db.String(255), nullable=False)
    target_author = db.Column(db.String(255), nullable=True)
    target_work = db.Column(db.String(255), nullable=True)
    target_reference = db.Column(db.String(100), nullable=False)
    target_snippet = db.Column(db.Text, nullable=False)
    target_language = db.Column(db.String(10), default='la')
    matched_lemmas = db.Column(db.Text)
    matched_tokens = db.Column(db.Text)
    tesserae_score = db.Column(db.Float, default=0.0)
    user_score = db.Column(db.Integer, default=0)
    submitter_id = db.Column(db.String, db.ForeignKey(User.id), nullable=True)
    submitter_name = db.Column(db.String(255), nullable=True)
    submitter_email = db.Column(db.String(255), nullable=True)
    submitter_institution = db.Column(db.String(255), nullable=True)
    submitter_orcid = db.Column(db.String(19), nullable=True)
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.String, nullable=True)
    
    submitter = db.relationship('User', backref='intertexts', lazy=True)


class SavedIntertext(db.Model):
    """Personal intertext collection for individual users"""
    __tablename__ = 'saved_intertexts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey(User.id), nullable=False)
    source_text_id = db.Column(db.String(255), nullable=False)
    source_author = db.Column(db.String(255), nullable=True)
    source_work = db.Column(db.String(255), nullable=True)
    source_reference = db.Column(db.String(100), nullable=False)
    source_snippet = db.Column(db.Text, nullable=False)
    source_language = db.Column(db.String(10), default='la')
    target_text_id = db.Column(db.String(255), nullable=False)
    target_author = db.Column(db.String(255), nullable=True)
    target_work = db.Column(db.String(255), nullable=True)
    target_reference = db.Column(db.String(100), nullable=False)
    target_snippet = db.Column(db.Text, nullable=False)
    target_language = db.Column(db.String(10), default='la')
    matched_lemmas = db.Column(db.Text)
    matched_tokens = db.Column(db.Text)
    tesserae_score = db.Column(db.Float, default=0.0)
    intertext_score = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)
    shared_to_public = db.Column(db.Boolean, default=False)
    public_intertext_id = db.Column(db.Integer, db.ForeignKey('intertexts.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    public_intertext = db.relationship('Intertext', backref='saved_copies', lazy=True)


# ============================================================================
# BATCH PROCESSING & VISUALIZATION MODELS
# ============================================================================

class BatchJob(db.Model):
    """
    Tracks batch search jobs for visualization pre-computation.
    Each job runs multiple searches between text pairs.
    """
    __tablename__ = 'batch_jobs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')  # pending, running, completed, failed
    job_type = db.Column(db.String(50), default='composite')  # composite, lemma, semantic, sound
    
    # Configuration
    language = db.Column(db.String(10), default='la')
    thresholds_json = db.Column(db.Text)  # JSON: CompositeThresholds
    
    # Progress tracking
    total_pairs = db.Column(db.Integer, default=0)
    completed_pairs = db.Column(db.Integer, default=0)
    failed_pairs = db.Column(db.Integer, default=0)
    
    # Timing
    created_at = db.Column(db.DateTime, default=datetime.now)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Error tracking
    error_message = db.Column(db.Text, nullable=True)
    
    # Relationships
    connections = db.relationship('TextConnection', backref='batch_job', lazy=True, cascade='all, delete-orphan')


class TextConnection(db.Model):
    """
    Pre-computed connection between two texts.
    Stores aggregate statistics for network visualization.
    """
    __tablename__ = 'text_connections'
    id = db.Column(db.Integer, primary_key=True)
    batch_job_id = db.Column(db.Integer, db.ForeignKey('batch_jobs.id'), nullable=True)
    
    # Text identifiers
    source_text_id = db.Column(db.String(255), nullable=False, index=True)
    target_text_id = db.Column(db.String(255), nullable=False, index=True)
    
    # Author/work metadata (for fast lookups)
    source_author = db.Column(db.String(255))
    source_work = db.Column(db.String(255))
    source_era = db.Column(db.String(50))
    target_author = db.Column(db.String(255))
    target_work = db.Column(db.String(255))
    target_era = db.Column(db.String(50))
    language = db.Column(db.String(10), default='la')
    
    # Aggregate counts by confidence tier
    total_parallels = db.Column(db.Integer, default=0)
    gold_count = db.Column(db.Integer, default=0)    # 4 signals (all)
    silver_count = db.Column(db.Integer, default=0)  # 3 signals
    bronze_count = db.Column(db.Integer, default=0)  # 2 signals
    copper_count = db.Column(db.Integer, default=0)  # 1 signal
    
    # Connection strength (weighted score for visualization)
    connection_strength = db.Column(db.Float, default=0.0)
    
    # Individual signal counts (for filtering)
    lemma_match_count = db.Column(db.Integer, default=0)
    semantic_match_count = db.Column(db.Integer, default=0)
    sound_match_count = db.Column(db.Integer, default=0)
    edit_distance_match_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    computed_at = db.Column(db.DateTime, default=datetime.now)
    
    # Unique constraint to prevent duplicates
    __table_args__ = (
        db.UniqueConstraint('source_text_id', 'target_text_id', 'batch_job_id', 
                           name='uq_text_connection'),
    )


class CompositeParallel(db.Model):
    """
    Individual high-confidence parallels from batch processing.
    Only stores Gold and Silver tier matches to limit storage.
    Used for drill-down from visualization to actual text.
    """
    __tablename__ = 'composite_parallels'
    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey('text_connections.id'), nullable=False, index=True)
    
    # Unit references (indexed for drill-down queries)
    source_unit_ref = db.Column(db.String(100), nullable=False, index=True)
    target_unit_ref = db.Column(db.String(100), nullable=False, index=True)
    source_snippet = db.Column(db.Text)
    target_snippet = db.Column(db.Text)
    
    # Confidence tier (indexed for filtering by tier)
    confidence_tier = db.Column(db.String(10), nullable=False, index=True)  # GOLD, SILVER, BRONZE, COPPER
    composite_score = db.Column(db.Float, default=0.0, index=True)  # Indexed for top-N queries
    
    # Individual signal scores (null if not present)
    lemma_score = db.Column(db.Float, nullable=True)
    lemma_matches = db.Column(db.Integer, nullable=True)
    semantic_score = db.Column(db.Float, nullable=True)
    sound_score = db.Column(db.Float, nullable=True)
    edit_distance_score = db.Column(db.Float, nullable=True)
    
    # Which signals confirmed this parallel
    signals_json = db.Column(db.Text)  # JSON array: ["lemma", "semantic", "sound", "edit_distance"]
    
    # Relationship
    connection = db.relationship('TextConnection', backref='parallels', lazy=True)
