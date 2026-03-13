import sys
import os
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.db import db
from backend.services.artifacts import ArtifactService

@pytest.fixture
def setup_db():
    original_conn = db.conn
    db.conn = sqlite3.connect(':memory:')
    db.conn.row_factory = sqlite3.Row
    db.init_schema()
    yield db.conn
    db.conn = original_conn

@pytest.fixture
def art_svc(setup_db):
    with patch('backend.services.embeddings.embedding_service'):
        with patch('backend.services.world_model.world_model_service'):
            with patch('backend.services.memory.memory_service'):
                with patch('backend.services.project_state.project_state_service'):
                    service = ArtifactService()
                    yield service

def test_merge_artifacts_lineage_inheritance_integration(art_svc):
    s = art_svc
    
    # Insert source artifacts into DB
    db.conn.execute(
        "INSERT INTO artifacts (id, project_id, type, status, title, data_json, confidence, score, version, lineage_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('s1', 'p1', 'architecture', 'pass', 'S1', '{}', 0.9, 0.8, 5, 'L1', 100, 100)
    )
    db.conn.execute(
        "INSERT INTO artifacts (id, project_id, type, status, title, data_json, confidence, score, version, lineage_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('s2', 'p1', 'architecture', 'pass', 'S2', '{}', 0.4, 0.5, 2, 'L2', 100, 100)
    )
    
    with patch('backend.services.validation.validation_service.validate') as mock_val:
        mock_val.return_value = ('pass', 0.8, {})
        
        result = s.merge_artifacts(
            project_id='p1',
            artifact_type='architecture',
            title='Merged Arch',
            data={'components': []},
            source_artifact_ids=['s1', 's2']
        )
        
        # Verify result
        assert result['lineage_id'] == 'L1' # Inherited from s1
        assert result['version'] == 6       # 5 + 1
        
        # Check DB links
        links = db.conn.execute("SELECT * FROM artifact_links WHERE target_artifact_id = ?", (result['id'],)).fetchall()
        assert len(links) == 2
        sources = [l['source_artifact_id'] for l in links]
        assert 's1' in sources
        assert 's2' in sources
