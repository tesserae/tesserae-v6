#!/usr/bin/env python3
"""
Tesserae V6 - Import Pre-computed Connections

This script imports connection data from JSON files computed locally
back into the Tesserae database.

USAGE:
    python import_connections.py connections_latin_t1.json
    python import_connections.py --batch connections_*.json
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db, TextConnection, BatchJob


def import_connections_file(filepath, job_id=None):
    """Import connections from a JSON file."""
    print(f"Importing from: {filepath}")
    
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    connections = data.get('connections', [])
    language = data.get('language', 'la')
    tier = data.get('tier', 1)
    
    print(f"Found {len(connections)} connections for {language} tier {tier}")
    
    imported = 0
    skipped = 0
    
    for conn in connections:
        existing = TextConnection.query.filter_by(
            source_text_id=conn['source_text_id'],
            target_text_id=conn['target_text_id'],
            language=conn['language']
        ).first()
        
        if existing:
            skipped += 1
            continue
        
        new_conn = TextConnection(
            batch_job_id=job_id,
            source_text_id=conn['source_text_id'],
            target_text_id=conn['target_text_id'],
            source_author=conn.get('source_author', ''),
            source_work=conn.get('source_work', ''),
            target_author=conn.get('target_author', ''),
            target_work=conn.get('target_work', ''),
            language=conn['language'],
            total_parallels=conn.get('total_parallels', 0),
            gold_count=conn.get('gold_count', 0),
            silver_count=conn.get('silver_count', 0),
            bronze_count=conn.get('bronze_count', 0),
            copper_count=conn.get('copper_count', 0),
            connection_strength=conn.get('connection_strength', 0),
            lemma_match_count=conn.get('total_parallels', 0),
            semantic_match_count=0,
            sound_match_count=0
        )
        db.session.add(new_conn)
        imported += 1
        
        if imported % 100 == 0:
            db.session.commit()
            print(f"  Imported {imported}...")
    
    db.session.commit()
    print(f"Imported: {imported}, Skipped (duplicates): {skipped}")
    return imported, skipped


def main():
    parser = argparse.ArgumentParser(description='Import pre-computed connections into Tesserae')
    parser.add_argument('files', nargs='+', help='JSON files to import')
    parser.add_argument('--job-name', default='Local Import', help='Name for the batch job')
    
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        job = BatchJob(
            name=args.job_name,
            description=f'Importing {len(args.files)} connection files',
            job_type='import',
            language='mixed',
            status='running',
            started_at=datetime.utcnow()
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id
        
        total_imported = 0
        total_skipped = 0
        
        for filepath in args.files:
            if not os.path.exists(filepath):
                print(f"File not found: {filepath}", file=sys.stderr)
                continue
            
            imported, skipped = import_connections_file(filepath, job_id)
            total_imported += imported
            total_skipped += skipped
        
        job.status = 'completed'
        job.completed_pairs = total_imported
        job.completed_at = datetime.utcnow()
        db.session.commit()
        
        print(f"\n=== IMPORT COMPLETE ===")
        print(f"Total imported: {total_imported}")
        print(f"Total skipped: {total_skipped}")
        print(f"Batch job ID: {job_id}")


if __name__ == '__main__':
    main()
