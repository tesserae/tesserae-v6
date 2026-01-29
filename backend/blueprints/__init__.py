"""
Tesserae V6 - Flask Blueprints
Modular route organization for maintainability
"""
from backend.blueprints.admin import admin_bp, init_admin_blueprint
from backend.blueprints.search import search_bp, init_search_blueprint
from backend.blueprints.corpus import corpus_bp, init_corpus_blueprint

__all__ = [
    'admin_bp', 'init_admin_blueprint',
    'search_bp', 'init_search_blueprint', 
    'corpus_bp', 'init_corpus_blueprint'
]
