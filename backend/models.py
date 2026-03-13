from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str
    goal: str


class BootstrapProjectRequest(BaseModel):
    milestone_titles: list[str] = Field(default_factory=lambda: [
        'Define scope',
        'Gather evidence',
        'Synthesize architecture',
        'Critique and revise',
    ])


class CreateTaskRequest(BaseModel):
    project_id: str
    title: str
    kind: str = 'analysis'
    priority: int = 0
    rationale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateNodeRequest(BaseModel):
    project_id: str
    task_id: str
    operator: str
    dependency_node_ids: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunUntilIdleRequest(BaseModel):
    max_steps: int | None = None


class ManualArtifactRequest(BaseModel):
    project_id: str
    type: str
    title: str
    data: dict[str, Any]
    confidence: float = 0.5


class ReviseArtifactRequest(BaseModel):
    base_artifact_id: str
    title: str | None = None
    data: dict[str, Any]
    confidence: float = 0.6
    revision_note: str | None = None


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class MilestoneRequest(BaseModel):
    title: str
    success_conditions: list[str]


class SandboxSessionCreateRequest(BaseModel):
    image: str | None = None
    working_dir: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ttl_minutes: int | None = None


class SandboxMaterializeRequest(BaseModel):
    artifact_ids: list[str]
    base_path: str = '/workspace/artifacts'


class SandboxRunCommandRequest(BaseModel):
    session_id: str | None = None
    command: str
    image: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    files: list[dict[str, Any]] = Field(default_factory=list)
    working_dir: str | None = None
    reuse_project_session: bool = False


class SandboxRepoEvalRequest(BaseModel):
    session_id: str | None = None
    repo_url: str
    repo_ref: str | None = None
    install_command: str | None = None
    test_command: str = 'pytest -q'
    image: str | None = None
    reuse_project_session: bool = True
    artifact_ids: list[str] = Field(default_factory=list)
    base_path: str = '/workspace/artifacts'
    create_result_artifact: bool = True
    repo_profile_id: str | None = None




class RepoInspectRequest(BaseModel):
    repo_url: str
    repo_ref: str | None = None
    session_id: str | None = None
    image: str | None = None
    reuse_project_session: bool = True
    create_artifact: bool = True

class InferRepoProfileRequest(BaseModel):
    repo_url: str | None = None
    repo_ref: str | None = None
    install_command: str | None = None
    test_command: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    persist: bool = True


class SandboxPatchTestLoopRequest(BaseModel):
    session_id: str | None = None
    repo_url: str
    repo_ref: str | None = None
    install_command: str | None = None
    test_command: str | None = None
    image: str | None = None
    reuse_project_session: bool = True
    artifact_ids: list[str] = Field(default_factory=list)
    patch_artifact_ids: list[str] = Field(default_factory=list)
    base_path: str = '/workspace/artifacts'
    create_result_artifact: bool = True
    repo_profile_id: str | None = None


class MergeArtifactsRequest(BaseModel):
    project_id: str
    type: str
    title: str
    data: dict[str, Any] = Field(default_factory=dict)
    source_artifact_ids: list[str]
    confidence: float = 0.6
    revision_note: str | None = None
