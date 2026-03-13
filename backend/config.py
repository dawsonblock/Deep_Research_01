from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    db_path: str = Field(default='data/research_engine.db', alias='RESEARCH_ENGINE_DB_PATH')
    searxng_base_url: str | None = Field(default=None, alias='SEARXNG_BASE_URL')
    searxng_timeout_seconds: int = Field(default=8, alias='SEARXNG_TIMEOUT_SECONDS')
    run_loop_max_steps: int = Field(default=50, alias='RUN_LOOP_MAX_STEPS')

    llm_provider: str = Field(default='none', alias='LLM_PROVIDER')
    llm_api_base_url: str = Field(default='https://api.openai.com/v1', alias='LLM_API_BASE_URL')
    llm_api_key: str | None = Field(default=None, alias='LLM_API_KEY')
    llm_model: str = Field(default='gpt-4.1-mini', alias='LLM_MODEL')
    llm_timeout_seconds: int = Field(default=20, alias='LLM_TIMEOUT_SECONDS')

    embedding_provider: str = Field(default='local_hash', alias='EMBEDDING_PROVIDER')
    embedding_model: str = Field(default='text-embedding-3-small', alias='EMBEDDING_MODEL')
    embedding_dim: int = Field(default=256, alias='EMBEDDING_DIM')

    opensandbox_enabled: bool = Field(default=False, alias='OPENSANDBOX_ENABLED')
    opensandbox_domain: str | None = Field(default=None, alias='OPEN_SANDBOX_DOMAIN')
    opensandbox_api_key: str | None = Field(default=None, alias='OPEN_SANDBOX_API_KEY')
    opensandbox_protocol: str = Field(default='http', alias='OPEN_SANDBOX_PROTOCOL')
    opensandbox_timeout_seconds: int = Field(default=180, alias='OPEN_SANDBOX_TIMEOUT_SECONDS')
    opensandbox_use_server_proxy: bool = Field(default=False, alias='OPEN_SANDBOX_USE_SERVER_PROXY')
    opensandbox_default_image: str = Field(default='ubuntu:22.04', alias='OPEN_SANDBOX_DEFAULT_IMAGE')
    opensandbox_python_image: str = Field(default='python:3.11-slim', alias='OPEN_SANDBOX_PYTHON_IMAGE')
    opensandbox_default_workdir: str = Field(default='/workspace', alias='OPEN_SANDBOX_DEFAULT_WORKDIR')
    opensandbox_session_ttl_minutes: int = Field(default=30, alias='OPEN_SANDBOX_SESSION_TTL_MINUTES')
    opensandbox_repo_dir: str = Field(default='/workspace/repo', alias='OPEN_SANDBOX_REPO_DIR')

    # Failure-analysis blame scoring weights (tunable)
    blame_weight_hinted_path: float = Field(default=9.0, alias='BLAME_WEIGHT_HINTED_PATH')
    blame_weight_stack_frame: float = Field(default=7.0, alias='BLAME_WEIGHT_STACK_FRAME')
    blame_weight_symbol_match: float = Field(default=6.0, alias='BLAME_WEIGHT_SYMBOL_MATCH')
    blame_weight_failing_test: float = Field(default=5.0, alias='BLAME_WEIGHT_FAILING_TEST')
    blame_weight_related_source: float = Field(default=4.0, alias='BLAME_WEIGHT_RELATED_SOURCE')
    blame_weight_config_file: float = Field(default=1.5, alias='BLAME_WEIGHT_CONFIG_FILE')
    blame_weight_fallback: float = Field(default=1.0, alias='BLAME_WEIGHT_FALLBACK')
    blame_max_ranked_targets: int = Field(default=16, alias='BLAME_MAX_RANKED_TARGETS')
    blame_max_derived_symbols: int = Field(default=20, alias='BLAME_MAX_DERIVED_SYMBOLS')

    # AST analysis settings
    ast_use_tree_sitter: bool = Field(default=False, alias='AST_USE_TREE_SITTER')
    ast_max_slice_lines: int = Field(default=200, alias='AST_MAX_SLICE_LINES')
    ast_max_symbols_per_file: int = Field(default=60, alias='AST_MAX_SYMBOLS_PER_FILE')

    # Patch synthesis settings
    patch_max_slice_tokens: int = Field(default=4000, alias='PATCH_MAX_SLICE_TOKENS')
    patch_max_targets: int = Field(default=10, alias='PATCH_MAX_TARGETS')

    # Iterative patch-test loop
    patch_loop_max_iterations: int = Field(default=3, alias='PATCH_LOOP_MAX_ITERATIONS')
    patch_loop_improvement_threshold: float = Field(default=0.05, alias='PATCH_LOOP_IMPROVEMENT_THRESHOLD')

    def ensure_dirs(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
