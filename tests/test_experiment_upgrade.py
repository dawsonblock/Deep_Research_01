import sys
import os
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.db import db
from backend.services.experiments import ExperimentService
from backend.services.llm import llm_service

@pytest.fixture
def setup_db():
    original_conn = db.conn
    db.conn = sqlite3.connect(':memory:')
    db.conn.row_factory = sqlite3.Row
    db.init_schema()
    yield db.conn
    db.conn = original_conn

@pytest.fixture
def exp_svc(setup_db):
    with patch.object(llm_service, 'available', return_value=True):
        with patch.object(llm_service, 'complete_json') as mock_json:
            service = ExperimentService()
            yield service, mock_json

def test_run_plan_llm_benchmark_integration(exp_svc):
    s, mock_json = exp_svc
    mock_json.return_value = {
        'requirement_coverage': 0.85,
        'linear_contradiction_rate': 0.3,
        'graph_contradiction_rate': 0.15,
        'replayability_score': 0.8,
        'architecture_quality_score': 0.9,
        'verdict': 'LLM says yes',
        'recommendation': 'Good'
    }
    
    # Provide version and other required fields
    db.conn.execute(
        "INSERT INTO artifacts (id, project_id, type, status, title, data_json, score, confidence, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('a1', 'p1', 'architecture', 'pass', 'Arch', '{}', 0.8, 0.9, 1, 100, 100)
    )
    
    plan_artifact = {
        'id': 'plan1', 
        'data': {'statement': 'Testing LLM runner', 'method': 'project_state_benchmark'}
    }
    
    s._latest_project_artifacts = MagicMock(return_value={
        'architecture': {'id': 'a1', 'data': {'components': ['A', 'B', 'C']}},
        'requirements': {'id': 'r1', 'data': {'items': ['R1', 'R2']}},
        'critique': {'id': 'cr1', 'data': {'issues': []}}
    })
    
    result = s.run_plan('p1', plan_artifact, [])
    
    assert result['summary']['method'] == 'llm_benchmark'
    assert result['metrics']['llm_verdict'] == 'LLM says yes'

def test_run_plan_fallback_to_stub_integration(exp_svc):
    s, mock_json = exp_svc
    with patch.object(llm_service, 'available', return_value=False):
        plan_artifact = {
            'id': 'plan1', 
            'data': {'statement': 'Testing fallback', 'method': 'project_state_benchmark'}
        }
        
        s._latest_project_artifacts = MagicMock(return_value={
            'architecture': {'id': 'a1', 'data': {'components': ['A', 'B', 'C']}},
            'requirements': {'id': 'r1', 'data': {'items': ['R1', 'R2']}},
            'critique': {'id': 'cr1', 'data': {'issues': []}}
        })
        
        result = s.run_plan('p1', plan_artifact, [])
        assert result['summary']['method'] == 'deterministic_stub'
