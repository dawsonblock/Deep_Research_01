from __future__ import annotations

from fastapi import FastAPI, HTTPException

from backend.models import (
    BootstrapProjectRequest,
    CreateNodeRequest,
    CreateProjectRequest,
    CreateTaskRequest,
    ManualArtifactRequest,
    MilestoneRequest,
    ReviseArtifactRequest,
    RunUntilIdleRequest,
    InferRepoProfileRequest,
    RepoInspectRequest,
    SandboxPatchTestLoopRequest,
    SandboxMaterializeRequest,
    SandboxRepoEvalRequest,
    SandboxRunCommandRequest,
    SandboxSessionCreateRequest,
    SearchRequest,
    MergeArtifactsRequest,
)
from backend.services.artifacts import artifact_service
from backend.services.compression import compression_service
from backend.services.conflict_resolution import conflict_resolution_service
from backend.services.execution import execution_service
from backend.services.experiments import experiment_service
from backend.services.llm import llm_service
from backend.services.memory import memory_service
from backend.services.planner import planner_service
from backend.services.project_state import project_state_service
from backend.services.repo_inspection import repo_inspection_service
from backend.services.repo_profiles import repo_profile_service
from backend.services.search import search_service
from backend.services.sandbox_harness import sandbox_harness_service
from backend.services.tasks import task_service
from backend.services.world_model import world_model_service

app = FastAPI(title='Research Engine Scaffold', version='0.9.2')


@app.get('/')
def root() -> dict:
    return {'name': 'research-engine-scaffold', 'status': 'ok', 'llm_available': llm_service.available()}


@app.post('/projects')
def create_project(request: CreateProjectRequest) -> dict:
    return project_state_service.create_project(request.name, request.goal)


@app.get('/projects/{project_id}/summary')
def project_summary(project_id: str) -> dict:
    try:
        return project_state_service.summarize(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/projects/{project_id}/milestones')
def add_milestone(project_id: str, request: MilestoneRequest) -> dict:
    return project_state_service.add_milestone(project_id, request.title, request.success_conditions)


@app.post('/projects/{project_id}/bootstrap')
def bootstrap_project(project_id: str, request: BootstrapProjectRequest) -> dict:
    if request.milestone_titles:
        milestone_map = {
            'Define scope': ['artifact_type:requirements:1'],
            'Gather evidence': ['artifact_type:evidence:1'],
            'Synthesize architecture': ['artifact_type:architecture:1'],
            'Critique and revise': ['artifact_type:critique:1', 'avg_score>=0.55'],
        }
        milestones = [project_state_service.add_milestone(project_id, title, milestone_map.get(title, ['artifact_type:summary:1'])) for title in request.milestone_titles]
    else:
        milestones = []
    goal = project_state_service.get_project(project_id)['goal']
    t1 = task_service.create(project_id, 'Gather evidence for goal', kind='research', priority=5)
    n1 = execution_service.create_node(project_id, t1['id'], 'researcher', metadata={'query': goal})
    t2 = task_service.create(project_id, 'Extract requirements', kind='requirements', priority=5)
    n2 = execution_service.create_node(project_id, t2['id'], 'extract_requirements', dependency_node_ids=[n1['id']])
    t3 = task_service.create(project_id, 'Synthesize architecture', kind='synthesis', priority=4)
    n3 = execution_service.create_node(project_id, t3['id'], 'synthesizer', dependency_node_ids=[n1['id'], n2['id']])
    t4 = task_service.create(project_id, 'Critique architecture', kind='critique', priority=4)
    n4 = execution_service.create_node(project_id, t4['id'], 'critic', dependency_node_ids=[n3['id'], n2['id']])
    t5 = task_service.create(project_id, 'Form initial hypothesis', kind='hypothesis', priority=4)
    n5 = execution_service.create_node(project_id, t5['id'], 'hypothesis_maker', dependency_node_ids=[n3['id'], n4['id']])
    t6 = task_service.create(project_id, 'Plan follow-up tasks', kind='planning', priority=3)
    n6 = execution_service.create_node(project_id, t6['id'], 'planner_agent', dependency_node_ids=[n4['id'], n2['id']])
    return {'milestones': milestones, 'nodes': [n1, n2, n3, n4, n5, n6]}


@app.post('/tasks')
def create_task(request: CreateTaskRequest) -> dict:
    return task_service.create(request.project_id, request.title, request.kind, request.priority, request.rationale, request.metadata)


@app.get('/projects/{project_id}/tasks')
def list_tasks(project_id: str, status: str | None = None) -> list[dict]:
    return task_service.list(project_id, status)


@app.post('/nodes')
def create_node(request: CreateNodeRequest) -> dict:
    return execution_service.create_node(
        request.project_id,
        request.task_id,
        request.operator,
        request.dependency_node_ids,
        request.input_artifact_ids,
        request.metadata,
    )


@app.get('/projects/{project_id}/nodes')
def list_nodes(project_id: str, status: str | None = None) -> list[dict]:
    return execution_service.list_nodes(project_id, status)


@app.post('/projects/{project_id}/run-once')
def run_once(project_id: str) -> dict | None:
    return execution_service.run_once(project_id)


@app.post('/projects/{project_id}/run-until-idle')
def run_until_idle(project_id: str, request: RunUntilIdleRequest) -> dict:
    max_steps = request.max_steps or 25
    return execution_service.run_until_idle(project_id, max_steps)


@app.post('/artifacts/manual')
def create_manual_artifact(request: ManualArtifactRequest) -> dict:
    return artifact_service.create(request.project_id, request.type, request.title, request.data, request.confidence)


@app.post('/artifacts/revise')
def revise_artifact(request: ReviseArtifactRequest) -> dict:
    return artifact_service.create_revision(
        base_artifact_id=request.base_artifact_id,
        title=request.title or '',
        data=request.data,
        confidence=request.confidence,
        revision_note=request.revision_note,
    )


@app.get('/projects/{project_id}/artifacts')
def list_artifacts(project_id: str, artifact_type: str | None = None) -> list[dict]:
    return artifact_service.list(project_id, artifact_type)


@app.get('/artifacts/{artifact_id}')
def get_artifact(artifact_id: str) -> dict:
    artifact = artifact_service.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail='artifact not found')
    return artifact


@app.get('/artifacts/{artifact_id}/lineage')
def get_lineage(artifact_id: str) -> list[dict]:
    artifact = artifact_service.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail='artifact not found')
    return artifact_service.lineage(artifact['lineage_id'])


@app.get('/projects/{project_id}/memory')
def list_memory(project_id: str, query: str | None = None) -> list[dict]:
    if query:
        return memory_service.search(project_id, query)
    return memory_service.search(project_id, 'project architecture')


@app.post('/projects/{project_id}/memory/consolidate')
def consolidate_memory(project_id: str) -> dict:
    return memory_service.consolidate(project_id)


@app.post('/projects/{project_id}/replan')
def replan(project_id: str) -> dict:
    return planner_service.replan(project_id)


@app.post('/projects/{project_id}/compress')
def compress(project_id: str) -> dict:
    return compression_service.compress_artifacts(project_id)


@app.post('/projects/{project_id}/checkpoint')
def checkpoint(project_id: str, label: str = 'manual') -> dict:
    return project_state_service.checkpoint(project_id, label)


@app.get('/projects/{project_id}/experiments')
def list_experiments(project_id: str) -> list[dict]:
    return experiment_service.list_runs(project_id)


@app.get('/projects/{project_id}/experiments/{run_id}')
def get_experiment_run(project_id: str, run_id: str) -> dict:
    run = experiment_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='experiment run not found')
    if run['project_id'] != project_id:
        raise HTTPException(status_code=403, detail='experiment run belongs to another project')
    return run


@app.get('/projects/{project_id}/conflicts')
def list_conflicts(project_id: str) -> list[dict]:
    return conflict_resolution_service.list_conflicts(project_id)


@app.post('/projects/{project_id}/conflicts/{conflict_id}/unresolve')
def unresolve_conflict(project_id: str, conflict_id: str) -> dict:
    try:
        conflict_resolution_service.unresolve(conflict_id)
        return {'status': 'ok'}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/artifacts/merge')
def merge_artifacts(request: MergeArtifactsRequest) -> dict:
    try:
        return artifact_service.merge_artifacts(
            project_id=request.project_id,
            artifact_type=request.type,
            title=request.title,
            data=request.data,
            source_artifact_ids=request.source_artifact_ids,
            confidence=request.confidence,
            revision_note=request.revision_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/search')
def search(request: SearchRequest) -> list[dict]:
    return search_service.search(request.query, request.limit)


@app.get('/projects/{project_id}/world-model')
def world_model(project_id: str) -> dict:
    return {
        'claims': world_model_service.low_confidence_claims(project_id, threshold=1.1),
        'questions': world_model_service.open_questions(project_id),
        'hypotheses': world_model_service.active_hypotheses(project_id),
    }


@app.get('/sandbox/status')
def sandbox_status() -> dict:
    return sandbox_harness_service.status()


@app.get('/projects/{project_id}/sandbox/sessions')
def sandbox_list_sessions(project_id: str) -> list[dict]:
    _ = project_state_service.get_project(project_id) or (_ for _ in ()).throw(HTTPException(status_code=404, detail='project not found'))
    return sandbox_harness_service.list_sessions(project_id)


@app.post('/projects/{project_id}/sandbox/sessions')
def sandbox_create_session(project_id: str, request: SandboxSessionCreateRequest) -> dict:
    _ = project_state_service.get_project(project_id) or (_ for _ in ()).throw(HTTPException(status_code=404, detail='project not found'))
    return sandbox_harness_service.create_session(project_id, image=request.image, working_dir=request.working_dir, metadata=request.metadata, ttl_minutes=request.ttl_minutes)


@app.get('/sandbox/sessions/{session_id}')
def sandbox_get_session(session_id: str) -> dict:
    session = sandbox_harness_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='sandbox session not found')
    return session


@app.get('/sandbox/sessions/{session_id}/runs')
def sandbox_get_session_runs(session_id: str) -> list[dict]:
    session = sandbox_harness_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='sandbox session not found')
    return sandbox_harness_service.list_runs(session_id)



@app.get('/sandbox/sessions/{session_id}/workspace-lineages')
def sandbox_workspace_lineages(session_id: str) -> list[dict]:
    session = sandbox_harness_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='sandbox session not found')
    return sandbox_harness_service.list_workspace_lineages(session_id)


@app.post('/sandbox/sessions/{session_id}/sync-lineages')
def sandbox_sync_lineages(session_id: str, base_path: str = '/workspace/artifacts', artifact_type: str | None = None) -> dict:
    session = sandbox_harness_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='sandbox session not found')
    return sandbox_harness_service.sync_workspace_lineages(session['project_id'], session_id, base_path=base_path, artifact_type=artifact_type)


@app.post('/sandbox/sessions/{session_id}/pause')
def sandbox_pause_session(session_id: str) -> dict:
    try:
        return sandbox_harness_service.pause_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/sandbox/sessions/{session_id}/resume')
def sandbox_resume_session(session_id: str) -> dict:
    try:
        return sandbox_harness_service.resume_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/sandbox/sessions/{session_id}/renew')
def sandbox_renew_session(session_id: str, ttl_minutes: int | None = None) -> dict:
    try:
        return sandbox_harness_service.renew_session(session_id, ttl_minutes=ttl_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete('/sandbox/sessions/{session_id}')
def sandbox_kill_session(session_id: str) -> dict:
    try:
        return sandbox_harness_service.kill_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/sandbox/sessions/{session_id}/materialize')
def sandbox_materialize(session_id: str, request: SandboxMaterializeRequest) -> dict:
    session = sandbox_harness_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='sandbox session not found')
    try:
        return sandbox_harness_service.materialize_artifacts(session['project_id'], session_id, request.artifact_ids, base_path=request.base_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/projects/{project_id}/sandbox/run')
def sandbox_run(project_id: str, request: SandboxRunCommandRequest) -> dict:
    _ = project_state_service.get_project(project_id) or (_ for _ in ()).throw(HTTPException(status_code=404, detail='project not found'))
    try:
        return sandbox_harness_service.run_command(
            project_id=project_id,
            session_id=request.session_id,
            command=request.command,
            image=request.image,
            env=request.env,
            files=request.files,
            working_dir=request.working_dir,
            reuse_project_session=request.reuse_project_session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc




@app.get('/projects/{project_id}/repo-profiles')
def list_repo_profiles(project_id: str) -> list[dict]:
    _ = project_state_service.get_project(project_id) or (_ for _ in ()).throw(HTTPException(status_code=404, detail='project not found'))
    return repo_profile_service.list(project_id)


@app.post('/projects/{project_id}/repo-inspect')
def inspect_repo(project_id: str, request: RepoInspectRequest) -> dict:
    return repo_inspection_service.inspect(
        project_id=project_id,
        repo_url=request.repo_url,
        repo_ref=request.repo_ref,
        session_id=request.session_id,
        image=request.image,
        reuse_project_session=request.reuse_project_session,
        create_artifact=request.create_artifact,
    )


@app.get('/projects/{project_id}/repo-inspections')
def list_repo_inspections(project_id: str) -> list[dict]:
    return artifact_service.list(project_id, 'repo_inspection')


@app.post('/projects/{project_id}/repo-profiles/infer')
def infer_repo_profile(project_id: str, request: InferRepoProfileRequest) -> dict:
    _ = project_state_service.get_project(project_id) or (_ for _ in ()).throw(HTTPException(status_code=404, detail='project not found'))
    artifact_ids = list(request.artifact_ids)
    latest_inspection = repo_inspection_service.latest_for_project(project_id, request.repo_url)
    if latest_inspection and latest_inspection['id'] not in artifact_ids:
        artifact_ids.append(latest_inspection['id'])
    return repo_profile_service.infer_profile(
        project_id=project_id,
        repo_url=request.repo_url,
        repo_ref=request.repo_ref,
        install_command=request.install_command,
        test_command=request.test_command,
        artifact_ids=artifact_ids,
        persist=request.persist,
    )

@app.post('/projects/{project_id}/sandbox/repo-eval')
def sandbox_repo_eval(project_id: str, request: SandboxRepoEvalRequest) -> dict:
    _ = project_state_service.get_project(project_id) or (_ for _ in ()).throw(HTTPException(status_code=404, detail='project not found'))
    try:
        return sandbox_harness_service.run_repo_evaluation(
            project_id=project_id,
            session_id=request.session_id,
            repo_url=request.repo_url,
            repo_ref=request.repo_ref,
            install_command=request.install_command,
            test_command=request.test_command,
            image=request.image,
            reuse_project_session=request.reuse_project_session,
            artifact_ids=request.artifact_ids,
            base_path=request.base_path,
            create_result_artifact=request.create_result_artifact,
            repo_profile_id=request.repo_profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/projects/{project_id}/sandbox/patch-test-loop')
def sandbox_patch_test_loop(project_id: str, request: SandboxPatchTestLoopRequest) -> dict:
    _ = project_state_service.get_project(project_id) or (_ for _ in ()).throw(HTTPException(status_code=404, detail='project not found'))
    try:
        return sandbox_harness_service.run_patch_test_loop(
            project_id=project_id,
            session_id=request.session_id,
            repo_url=request.repo_url,
            repo_ref=request.repo_ref,
            install_command=request.install_command,
            test_command=request.test_command,
            image=request.image,
            reuse_project_session=request.reuse_project_session,
            artifact_ids=request.artifact_ids,
            patch_artifact_ids=request.patch_artifact_ids,
            base_path=request.base_path,
            create_result_artifact=request.create_result_artifact,
            repo_profile_id=request.repo_profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
