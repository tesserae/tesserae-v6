"""
Tesserae V6 - Batch Processing Blueprint
API endpoints for batch search jobs and visualization data
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user
from datetime import datetime
import json
import os
import re

from backend.logging_config import get_logger
from backend.models import db, BatchJob, TextConnection, CompositeParallel

logger = get_logger('batch')

batch_bp = Blueprint('batch', __name__, url_prefix='/api/batch')

_composite_scorer = None
_matcher = None
_scorer = None
_texts_dir = None
_get_processed_units = None
_admin_password = None
_text_processor = None
_get_corpus_frequencies = None
_author_dates = None


def init_batch_blueprint(composite_scorer=None, matcher=None, scorer=None, 
                         texts_dir=None, get_processed_units_fn=None, admin_password=None,
                         text_processor=None, get_corpus_frequencies_fn=None, author_dates=None):
    """Initialize blueprint with required dependencies"""
    global _composite_scorer, _matcher, _scorer, _texts_dir, _get_processed_units, _admin_password
    global _text_processor, _get_corpus_frequencies, _author_dates
    _composite_scorer = composite_scorer
    _matcher = matcher
    _scorer = scorer
    _texts_dir = texts_dir
    _get_processed_units = get_processed_units_fn
    _admin_password = admin_password
    _text_processor = text_processor
    _get_corpus_frequencies = get_corpus_frequencies_fn
    _author_dates = author_dates


def check_admin_auth():
    """Check admin authentication via X-Admin-Password header"""
    password = request.headers.get('X-Admin-Password', '')
    return password == _admin_password and _admin_password is not None


def get_era_for_author(author, language):
    """Get era for an author from author_dates"""
    if not _author_dates:
        return 'Unknown'
    lang_dates = _author_dates.get(language, {})
    author_info = lang_dates.get(author, {})
    return author_info.get('era', 'Unknown')


def parse_text_id(text_id):
    """Parse text ID to extract author and work"""
    parts = text_id.replace('.tess', '').split('.')
    if len(parts) >= 2:
        author = parts[0]
        work = '.'.join(parts[1:])
        work = re.sub(r'\.part\.\d+$', '', work)
        return author, work
    return text_id, ''


@batch_bp.route('/compute-connections', methods=['POST'])
def compute_connections():
    """
    Compute text connections for network visualization (admin only).
    Takes source and target text lists, runs searches, and stores aggregated results.
    
    Request body:
    {
        "language": "la",
        "source_texts": ["vergil.aeneid.part.1.tess", ...],  # Optional, defaults to all
        "target_texts": ["lucan.bellum_civile.part.1.tess", ...],  # Optional, defaults to all
        "match_type": "lemma",  # lemma, sound, semantic
        "min_matches": 2,
        "max_per_pair": 500,  # Max results per text pair to store
        "job_name": "Latin Core Connections"  # Optional job name
    }
    """
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized - admin access required'}), 401
    
    try:
        data = request.get_json() or {}
        language = data.get('language', 'la')
        match_type = data.get('match_type', 'lemma')
        min_matches = data.get('min_matches', 2)
        max_per_pair = data.get('max_per_pair', 500)
        job_name = data.get('job_name', f'{language.upper()} Connection Computation')
        
        lang_dir = os.path.join(_texts_dir, language)
        if not os.path.exists(lang_dir):
            return jsonify({'error': f'Language directory not found: {language}'}), 400
        
        all_texts = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
        source_texts = data.get('source_texts', all_texts)
        target_texts = data.get('target_texts', all_texts)
        
        source_texts = [t for t in source_texts if t in all_texts]
        target_texts = [t for t in target_texts if t in all_texts]
        
        if not source_texts or not target_texts:
            return jsonify({'error': 'No valid texts found'}), 400
        
        symmetric = data.get('symmetric', True)
        pairs_to_compute = []
        seen = set()
        for s in source_texts:
            for t in target_texts:
                if s == t:
                    continue
                if symmetric:
                    pair_key = tuple(sorted([s, t]))
                    if pair_key not in seen:
                        seen.add(pair_key)
                        pairs_to_compute.append((s, t))
                else:
                    pairs_to_compute.append((s, t))
        
        job = BatchJob(
            name=job_name,
            description=f'Computing {len(pairs_to_compute)} text pairs for {language}',
            job_type=match_type,
            language=language,
            status='running',
            total_pairs=len(pairs_to_compute),
            started_at=datetime.utcnow()
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id
        
        logger.info(f"Starting batch job {job_id}: {len(pairs_to_compute)} pairs")
        
        completed = 0
        failed = 0
        connections_created = 0
        
        freq_data = None
        if _get_corpus_frequencies:
            freq_data = _get_corpus_frequencies(language, _text_processor)
        corpus_frequencies = freq_data.get('frequencies', {}) if freq_data else {}
        
        settings = {
            'match_type': match_type,
            'min_matches': min_matches,
            'max_results': max_per_pair,
            'max_distance': 999,
            'stoplist_basis': 'corpus',
            'source_unit_type': 'line',
            'target_unit_type': 'line',
            'language': language
        }
        
        for source_id, target_id in pairs_to_compute:
            try:
                source_units = _get_processed_units(source_id, language, 'line', _text_processor)
                target_units = _get_processed_units(target_id, language, 'line', _text_processor)
                
                if not source_units or not target_units:
                    failed += 1
                    continue
                
                if match_type == 'sound':
                    matches, stoplist_size = _matcher.find_sound_matches(
                        source_units, target_units, settings
                    )
                elif match_type == 'semantic':
                    from backend.semantic_similarity import find_semantic_matches
                    matches, stoplist_size = find_semantic_matches(
                        source_units, target_units, settings
                    )
                else:
                    matches, stoplist_size = _matcher.find_matches(
                        source_units, target_units, settings, corpus_frequencies
                    )
                
                if not matches:
                    completed += 1
                    continue
                
                scored = _scorer.score_matches(
                    matches, source_units, target_units, settings, corpus_frequencies
                )
                
                gold_count = 0
                silver_count = 0
                bronze_count = 0
                copper_count = 0
                lemma_matches = 0
                semantic_matches = 0
                sound_matches = 0
                
                for m in scored[:max_per_pair]:
                    score = m.get('score', 0) or 0
                    if isinstance(score, (int, float)):
                        if score >= 10:
                            gold_count += 1
                        elif score >= 7:
                            silver_count += 1
                        elif score >= 5:
                            bronze_count += 1
                        else:
                            copper_count += 1
                    else:
                        copper_count += 1
                    
                    if match_type == 'lemma':
                        lemma_matches += 1
                    elif match_type == 'semantic':
                        semantic_matches += 1
                    elif match_type == 'sound':
                        sound_matches += 1
                
                total = min(len(scored), max_per_pair)
                connection_strength = gold_count * 4 + silver_count * 3 + bronze_count * 2 + copper_count
                
                source_author, source_work = parse_text_id(source_id)
                target_author, target_work = parse_text_id(target_id)
                source_era = get_era_for_author(source_author, language)
                target_era = get_era_for_author(target_author, language)
                
                conn = TextConnection(
                    batch_job_id=job_id,
                    source_text_id=source_id,
                    target_text_id=target_id,
                    source_author=source_author,
                    source_work=source_work,
                    source_era=source_era,
                    target_author=target_author,
                    target_work=target_work,
                    target_era=target_era,
                    language=language,
                    total_parallels=total,
                    gold_count=gold_count,
                    silver_count=silver_count,
                    bronze_count=bronze_count,
                    copper_count=copper_count,
                    connection_strength=connection_strength,
                    lemma_match_count=lemma_matches,
                    semantic_match_count=semantic_matches,
                    sound_match_count=sound_matches
                )
                db.session.add(conn)
                connections_created += 1
                
                completed += 1
                
                if completed % 10 == 0:
                    job.completed_pairs = completed
                    job.failed_pairs = failed
                    db.session.commit()
                    logger.info(f"Job {job_id}: {completed}/{len(pairs_to_compute)} pairs completed")
                    
            except Exception as e:
                logger.error(f"Error processing pair {source_id} -> {target_id}: {e}")
                db.session.rollback()
                failed += 1
        
        job.completed_pairs = completed
        job.failed_pairs = failed
        job.status = 'completed'
        job.completed_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Batch job {job_id} completed: {completed} pairs, {connections_created} connections")
        
        return jsonify({
            'job_id': job_id,
            'status': 'completed',
            'total_pairs': len(pairs_to_compute),
            'completed': completed,
            'failed': failed,
            'connections_created': connections_created
        })
        
    except Exception as e:
        logger.error(f"Error in compute_connections: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """List all batch jobs with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', None)
        
        query = BatchJob.query.order_by(BatchJob.created_at.desc())
        
        if status:
            query = query.filter(BatchJob.status == status)
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        jobs = [{
            'id': job.id,
            'name': job.name,
            'description': job.description,
            'status': job.status,
            'job_type': job.job_type,
            'language': job.language,
            'total_pairs': job.total_pairs,
            'completed_pairs': job.completed_pairs,
            'failed_pairs': job.failed_pairs,
            'progress_percent': round(job.completed_pairs / job.total_pairs * 100, 1) if job.total_pairs > 0 else 0,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        } for job in pagination.items]
        
        return jsonify({
            'jobs': jobs,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
    except Exception as e:
        logger.error(f"Error listing batch jobs: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    """Get detailed information about a specific batch job"""
    try:
        job = BatchJob.query.get_or_404(job_id)
        
        thresholds = None
        if job.thresholds_json:
            thresholds = json.loads(job.thresholds_json)
        
        return jsonify({
            'id': job.id,
            'name': job.name,
            'description': job.description,
            'status': job.status,
            'job_type': job.job_type,
            'language': job.language,
            'thresholds': thresholds,
            'total_pairs': job.total_pairs,
            'completed_pairs': job.completed_pairs,
            'failed_pairs': job.failed_pairs,
            'progress_percent': round(job.completed_pairs / job.total_pairs * 100, 1) if job.total_pairs > 0 else 0,
            'error_message': job.error_message,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'connections_count': TextConnection.query.filter_by(batch_job_id=job_id).count()
        })
    except Exception as e:
        logger.error(f"Error getting batch job {job_id}: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/jobs', methods=['POST'])
def create_job():
    """Create a new batch job (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized - admin access required'}), 401
    
    try:
        data = request.get_json()
        
        name = data.get('name')
        if not name:
            return jsonify({'error': 'Job name is required'}), 400
        
        job = BatchJob(
            name=name,
            description=data.get('description', ''),
            job_type=data.get('job_type', 'composite'),
            language=data.get('language', 'la'),
            status='pending',
            total_pairs=data.get('total_pairs', 0)
        )
        
        thresholds = data.get('thresholds')
        if thresholds:
            job.thresholds_json = json.dumps(thresholds)
        
        db.session.add(job)
        db.session.commit()
        
        logger.info(f"Created batch job: {job.id} - {job.name}")
        
        return jsonify({
            'id': job.id,
            'name': job.name,
            'status': job.status,
            'message': 'Batch job created successfully'
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating batch job: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/jobs/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Delete a batch job and all its data (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized - admin access required'}), 401
    
    try:
        job = BatchJob.query.get_or_404(job_id)
        
        if job.status == 'running':
            return jsonify({'error': 'Cannot delete a running job'}), 400
        
        db.session.delete(job)
        db.session.commit()
        
        logger.info(f"Deleted batch job: {job_id}")
        
        return jsonify({'message': 'Batch job deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting batch job {job_id}: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/connections', methods=['GET'])
def get_connections():
    """
    Query pre-computed text connections for visualization.
    Supports filtering by era, language, confidence tier, and minimum connection strength.
    Supports pagination via page and per_page parameters.
    """
    try:
        language = request.args.get('language', 'la')
        min_strength = request.args.get('min_strength', 0, type=float)
        min_tier = request.args.get('min_tier', None)  # gold, silver, bronze, copper
        source_era = request.args.get('source_era', None)
        target_era = request.args.get('target_era', None)
        author = request.args.get('author', None)
        batch_job_id = request.args.get('batch_job_id', None, type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        per_page = min(per_page, 1000)
        
        query = TextConnection.query.filter(
            TextConnection.language == language,
            TextConnection.connection_strength >= min_strength
        )
        
        if batch_job_id:
            query = query.filter(TextConnection.batch_job_id == batch_job_id)
        
        if min_tier:
            tier_map = {'gold': 4, 'silver': 3, 'bronze': 2, 'copper': 1}
            min_tier_value = tier_map.get(min_tier.lower(), 0)
            if min_tier_value == 4:
                query = query.filter(TextConnection.gold_count > 0)
            elif min_tier_value == 3:
                query = query.filter(db.or_(TextConnection.gold_count > 0, TextConnection.silver_count > 0))
            elif min_tier_value == 2:
                query = query.filter(db.or_(TextConnection.gold_count > 0, TextConnection.silver_count > 0, TextConnection.bronze_count > 0))
            elif min_tier_value == 1:
                query = query.filter(db.or_(TextConnection.gold_count > 0, TextConnection.silver_count > 0, TextConnection.bronze_count > 0, TextConnection.copper_count > 0))
        
        if source_era:
            query = query.filter(TextConnection.source_era == source_era)
        if target_era:
            query = query.filter(TextConnection.target_era == target_era)
        
        if author:
            query = query.filter(db.or_(
                TextConnection.source_author.ilike(f'%{author}%'),
                TextConnection.target_author.ilike(f'%{author}%')
            ))
        
        query = query.order_by(TextConnection.connection_strength.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        result = [{
            'id': c.id,
            'source': {
                'text_id': c.source_text_id,
                'author': c.source_author,
                'work': c.source_work,
                'era': c.source_era
            },
            'target': {
                'text_id': c.target_text_id,
                'author': c.target_author,
                'work': c.target_work,
                'era': c.target_era
            },
            'stats': {
                'total_parallels': c.total_parallels,
                'gold_count': c.gold_count,
                'silver_count': c.silver_count,
                'bronze_count': c.bronze_count,
                'copper_count': getattr(c, 'copper_count', 0) or 0,
                'connection_strength': c.connection_strength,
                'lemma_matches': c.lemma_match_count,
                'semantic_matches': c.semantic_match_count,
                'sound_matches': c.sound_match_count,
                'edit_distance_matches': getattr(c, 'edit_distance_match_count', 0) or 0
            }
        } for c in pagination.items]
        
        return jsonify({
            'connections': result,
            'count': len(result),
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page,
            'filters': {
                'language': language,
                'min_strength': min_strength,
                'min_tier': min_tier,
                'source_era': source_era,
                'target_era': target_era,
                'author': author
            }
        })
    except Exception as e:
        logger.error(f"Error querying connections: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/connections/<int:connection_id>/parallels', methods=['GET'])
def get_connection_parallels(connection_id):
    """
    Get individual parallels for a text connection (drill-down from visualization).
    """
    try:
        connection = TextConnection.query.get_or_404(connection_id)
        
        tier = request.args.get('tier', None)
        min_score = request.args.get('min_score', 0, type=float)
        limit = request.args.get('limit', 100, type=int)
        
        query = CompositeParallel.query.filter(
            CompositeParallel.connection_id == connection_id,
            CompositeParallel.composite_score >= min_score
        )
        
        if tier:
            query = query.filter(CompositeParallel.confidence_tier == tier.upper())
        
        parallels = query.order_by(CompositeParallel.composite_score.desc()).limit(limit).all()
        
        result = [{
            'id': p.id,
            'source_ref': p.source_unit_ref,
            'target_ref': p.target_unit_ref,
            'source_snippet': p.source_snippet,
            'target_snippet': p.target_snippet,
            'confidence_tier': p.confidence_tier,
            'composite_score': p.composite_score,
            'signals': json.loads(p.signals_json) if p.signals_json else [],
            'scores': {
                'lemma': p.lemma_score,
                'lemma_matches': p.lemma_matches,
                'semantic': p.semantic_score,
                'sound': p.sound_score,
                'edit_distance': getattr(p, 'edit_distance_score', None)
            }
        } for p in parallels]
        
        return jsonify({
            'connection': {
                'id': connection.id,
                'source_author': connection.source_author,
                'source_work': connection.source_work,
                'target_author': connection.target_author,
                'target_work': connection.target_work
            },
            'parallels': result,
            'count': len(result)
        })
    except Exception as e:
        logger.error(f"Error getting parallels for connection {connection_id}: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/network/nodes', methods=['GET'])
def get_network_nodes():
    """
    Get aggregated node data for network visualization.
    Nodes are authors/works with aggregated connection statistics.
    Computes both out-degree (citing) and in-degree (cited) for each node.
    """
    try:
        language = request.args.get('language', 'la')
        node_type = request.args.get('type', 'author')  # author or work
        batch_job_id = request.args.get('batch_job_id', None, type=int)
        
        nodes = {}
        
        base_filter = [TextConnection.language == language]
        if batch_job_id:
            base_filter.append(TextConnection.batch_job_id == batch_job_id)
        
        if node_type == 'author':
            out_query = db.session.query(
                TextConnection.source_author.label('entity'),
                TextConnection.source_era.label('era'),
                db.func.sum(TextConnection.total_parallels).label('parallels'),
                db.func.sum(TextConnection.gold_count).label('gold'),
                db.func.count(TextConnection.id).label('connections')
            ).filter(*base_filter).group_by(TextConnection.source_author, TextConnection.source_era)
            
            in_query = db.session.query(
                TextConnection.target_author.label('entity'),
                TextConnection.target_era.label('era'),
                db.func.sum(TextConnection.total_parallels).label('parallels'),
                db.func.sum(TextConnection.gold_count).label('gold'),
                db.func.count(TextConnection.id).label('connections')
            ).filter(*base_filter).group_by(TextConnection.target_author, TextConnection.target_era)
        else:
            out_query = db.session.query(
                TextConnection.source_text_id.label('entity'),
                TextConnection.source_era.label('era'),
                TextConnection.source_author.label('author'),
                TextConnection.source_work.label('work'),
                db.func.sum(TextConnection.total_parallels).label('parallels'),
                db.func.sum(TextConnection.gold_count).label('gold'),
                db.func.count(TextConnection.id).label('connections')
            ).filter(*base_filter).group_by(
                TextConnection.source_text_id, TextConnection.source_era,
                TextConnection.source_author, TextConnection.source_work
            )
            
            in_query = db.session.query(
                TextConnection.target_text_id.label('entity'),
                TextConnection.target_era.label('era'),
                TextConnection.target_author.label('author'),
                TextConnection.target_work.label('work'),
                db.func.sum(TextConnection.total_parallels).label('parallels'),
                db.func.sum(TextConnection.gold_count).label('gold'),
                db.func.count(TextConnection.id).label('connections')
            ).filter(*base_filter).group_by(
                TextConnection.target_text_id, TextConnection.target_era,
                TextConnection.target_author, TextConnection.target_work
            )
        
        for row in out_query.all():
            entity = row[0]
            if entity not in nodes:
                if node_type == 'author':
                    nodes[entity] = {
                        'id': entity,
                        'era': row[1],
                        'out_degree': 0,
                        'in_degree': 0,
                        'gold_total': 0,
                        'connection_count': 0
                    }
                else:
                    nodes[entity] = {
                        'id': entity,
                        'era': row[1],
                        'author': row[2],
                        'work': row[3],
                        'out_degree': 0,
                        'in_degree': 0,
                        'gold_total': 0,
                        'connection_count': 0
                    }
            if node_type == 'author':
                nodes[entity]['out_degree'] += int(row[2] or 0)
                nodes[entity]['gold_total'] += int(row[3] or 0)
                nodes[entity]['connection_count'] += int(row[4] or 0)
            else:
                nodes[entity]['out_degree'] += int(row[4] or 0)
                nodes[entity]['gold_total'] += int(row[5] or 0)
                nodes[entity]['connection_count'] += int(row[6] or 0)
        
        for row in in_query.all():
            entity = row[0]
            if entity not in nodes:
                if node_type == 'author':
                    nodes[entity] = {
                        'id': entity,
                        'era': row[1],
                        'out_degree': 0,
                        'in_degree': 0,
                        'gold_total': 0,
                        'connection_count': 0
                    }
                else:
                    nodes[entity] = {
                        'id': entity,
                        'era': row[1],
                        'author': row[2],
                        'work': row[3],
                        'out_degree': 0,
                        'in_degree': 0,
                        'gold_total': 0,
                        'connection_count': 0
                    }
            if node_type == 'author':
                nodes[entity]['in_degree'] += int(row[2] or 0)
            else:
                nodes[entity]['in_degree'] += int(row[4] or 0)
        
        result = list(nodes.values())
        for node in result:
            node['total_degree'] = node['out_degree'] + node['in_degree']
        
        return jsonify({
            'nodes': result,
            'count': len(result),
            'node_type': node_type,
            'language': language
        })
    except Exception as e:
        logger.error(f"Error getting network nodes: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/era-flow', methods=['GET'])
def get_era_flow():
    """
    Get aggregated era-to-era flow data for Sankey diagram.
    Shows how literary influence flows across time periods.
    """
    try:
        language = request.args.get('language', 'la')
        min_connections = request.args.get('min_connections', 1, type=int)
        batch_job_id = request.args.get('batch_job_id', None, type=int)
        
        query = db.session.query(
            TextConnection.source_era,
            TextConnection.target_era,
            db.func.sum(TextConnection.total_parallels).label('flow_strength'),
            db.func.sum(TextConnection.gold_count).label('gold_count'),
            db.func.count(TextConnection.id).label('connection_count')
        ).filter(
            TextConnection.language == language,
            TextConnection.source_era.isnot(None),
            TextConnection.target_era.isnot(None)
        )
        
        if batch_job_id:
            query = query.filter(TextConnection.batch_job_id == batch_job_id)
        
        flows = query.group_by(
            TextConnection.source_era,
            TextConnection.target_era
        ).having(
            db.func.count(TextConnection.id) >= min_connections
        ).all()
        
        result = [{
            'source_era': f[0],
            'target_era': f[1],
            'flow_strength': int(f[2] or 0),
            'gold_count': int(f[3] or 0),
            'connection_count': int(f[4] or 0)
        } for f in flows]
        
        eras = set()
        for f in flows:
            eras.add(f[0])
            eras.add(f[1])
        
        return jsonify({
            'flows': result,
            'eras': list(eras),
            'count': len(result),
            'language': language
        })
    except Exception as e:
        logger.error(f"Error getting era flow: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/centrality', methods=['GET'])
def get_centrality_rankings():
    """
    Get centrality rankings for works/authors.
    Returns the most-cited and most-citing entities.
    """
    try:
        language = request.args.get('language', 'la')
        ranking_type = request.args.get('type', 'cited')  # cited (in-degree) or citing (out-degree)
        entity_type = request.args.get('entity', 'work')  # work or author
        limit = request.args.get('limit', 50, type=int)
        batch_job_id = request.args.get('batch_job_id', None, type=int)
        
        if ranking_type == 'cited':
            entity_col = TextConnection.target_author if entity_type == 'author' else TextConnection.target_text_id
            work_col = TextConnection.target_work
            era_col = TextConnection.target_era
        else:
            entity_col = TextConnection.source_author if entity_type == 'author' else TextConnection.source_text_id
            work_col = TextConnection.source_work
            era_col = TextConnection.source_era
        
        query = db.session.query(
            entity_col.label('entity'),
            work_col.label('work'),
            era_col.label('era'),
            db.func.sum(TextConnection.total_parallels).label('total_parallels'),
            db.func.sum(TextConnection.gold_count).label('gold_count'),
            db.func.count(TextConnection.id).label('connections')
        ).filter(
            TextConnection.language == language
        )
        
        if batch_job_id:
            query = query.filter(TextConnection.batch_job_id == batch_job_id)
        
        query = query.group_by(entity_col, work_col, era_col)
        query = query.order_by(db.func.sum(TextConnection.total_parallels).desc())
        
        rankings = query.limit(limit).all()
        
        result = [{
            'rank': i + 1,
            'entity': r[0],
            'work': r[1],
            'era': r[2],
            'total_parallels': int(r[3] or 0),
            'gold_count': int(r[4] or 0),
            'connections': int(r[5] or 0)
        } for i, r in enumerate(rankings)]
        
        return jsonify({
            'rankings': result,
            'ranking_type': ranking_type,
            'entity_type': entity_type,
            'language': language,
            'count': len(result)
        })
    except Exception as e:
        logger.error(f"Error getting centrality rankings: {e}")
        return jsonify({'error': str(e)}), 500
