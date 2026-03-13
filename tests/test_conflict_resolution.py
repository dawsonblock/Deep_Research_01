import sys
import os
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.db import db
from backend.services.conflict_resolution import ConflictResolutionService

@pytest.fixture
def setup_db():
    original_conn = db.conn
    db.conn = sqlite3.connect(':memory:')
    db.conn.row_factory = sqlite3.Row
    db.init_schema()
    yield db.conn
    db.conn = original_conn

@pytest.fixture
def conflict_svc(setup_db):
    with patch('backend.services.embeddings.embedding_service') as mock_embedding:
        with patch('backend.services.world_model.world_model_service') as mock_wm:
            service = ConflictResolutionService()
            yield service, mock_embedding, mock_wm

def test_detect_conflicts_with_semantic_clash(conflict_svc):
    s, mock_embedding, mock_wm = conflict_svc
    
    # Insert existing claim
    db.conn.execute(
        "INSERT INTO claims (id, project_id, artifact_id, content, confidence, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ('c_existing', 'p1', 'a_old', 'The product is affordable.', 0.7, 'active', 100, 100)
    )
    db.conn.execute(
        "INSERT INTO artifact_embeddings (artifact_id, model, vector_json, updated_at) VALUES (?, ?, ?, ?)",
        ('a_old', 'test-model', '[0.1, 0.2]', 100)
    )
    
    mock_embedding.embed_text.return_value = [0.1, 0.2]
    mock_embedding.cosine_similarity.return_value = 0.95 
    
    # New artifact with NEGATION to trigger flip
    db.conn.execute(
        "INSERT INTO artifacts (id, project_id, type, status, title, data_json, score, confidence, version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('a_new', 'p1', 'claims', 'pass', 'New Claims', '{"claims": ["The product is NOT affordable."]}', 0.9, 0.9, 1, 100, 100)
    )
    db.conn.execute(
        "INSERT INTO artifact_embeddings (artifact_id, model, vector_json, updated_at) VALUES (?, ?, ?, ?)",
        ('a_new', 'test-model', '[0.11, 0.21]', 100)
    )
    
    new_artifact = {
        'id': 'a_new', 
        'type': 'claims', 
        'data': {'claims': ['The product is NOT affordable.']},
        'confidence': 0.9
    }
    
    conflicts = s.detect_conflicts('p1', new_artifact)
    assert len(conflicts) == 1
    assert conflicts[0]['claim_a_id'] == 'c_existing'

def test_resolve_dominance(conflict_svc):
    s, mock_embedding, mock_wm = conflict_svc
    
    db.conn.execute(
        "INSERT INTO claims (id, project_id, artifact_id, content, confidence, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ('c1', 'p1', 'a0', 'Weak', 0.4, 'active', 100, 100)
    )
    db.conn.execute(
        "INSERT INTO artifacts (id, project_id, type, status, title, data_json, score, confidence, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('a_new', 'p1', 'claims', 'pass', 'Title', '{}', 0.9, 0.9, 1, 100, 100)
    )
    
    conflict_pair = {
        'claim_a_id': 'c1',
        'artifact_ b_id': 'a_new', # Fixed space if it was there
        'artifact_b_id': 'a_new',
        'existing_confidence': 0.4,
        'conflict_type': 'polarity'
    }
    
    s.resolve('p1', [conflict_pair])
    
    row = db.conn.execute("SELECT status FROM claims WHERE id = 'c1'").fetchone()
    assert row['status'] == 'suppressed'

def test_resolve_escalation(conflict_svc):
    s, mock_embedding, mock_wm = conflict_svc
    
    db.conn.execute(
        "INSERT INTO claims (id, project_id, artifact_id, content, confidence, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ('c_old', 'p1', 'a0', 'Claim A', 0.7, 'active', 100, 100)
    )
    db.conn.execute(
        "INSERT INTO artifacts (id, project_id, type, status, title, data_json, score, confidence, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('a_new', 'p1', 'claims', 'pass', 'Title', '{}', 0.72, 0.72, 1, 100, 100)
    )
    
    conflict_pair = {
        'claim_a_id': 'c_old',
        'artifact_b_id': 'a_new',
        'existing_confidence': 0.7,
        'conflict_type': 'polarity'
    }
    
    s.resolve('p1', [conflict_pair])
    
    row = db.conn.execute("SELECT status FROM claims WHERE id = 'c_old'").fetchone()
    assert row['status'] == 'contested'
    mock_wm.create_question.assert_called_once()
