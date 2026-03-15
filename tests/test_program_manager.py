"""Tests for the research program manager."""
from __future__ import annotations

import pytest


class TestProgramState:
    def test_create_state(self):
        from research_engine.programs.program_state import ProgramState
        ps = ProgramState(name="Test Program")
        assert ps.program_id
        assert ps.name == "Test Program"
        assert ps.status == "active"

    def test_to_dict(self):
        from research_engine.programs.program_state import ProgramState
        ps = ProgramState(name="Test")
        d = ps.to_dict()
        assert d["name"] == "Test"


class TestProgramStrategy:
    def test_allocate_to_lowest_progress(self):
        from research_engine.programs.program_strategy import ProgramStrategy
        from research_engine.programs.program_state import ProgramState
        strategy = ProgramStrategy()
        programs = [
            ProgramState(name="A", progress=0.8, budget_remaining=50),
            ProgramState(name="B", progress=0.2, budget_remaining=50),
        ]
        decision = strategy.allocate(programs)
        assert decision is not None
        assert decision.program_id == programs[1].program_id

    def test_allocate_empty(self):
        from research_engine.programs.program_strategy import ProgramStrategy
        strategy = ProgramStrategy()
        assert strategy.allocate([]) is None

    def test_skip_exhausted_budget(self):
        from research_engine.programs.program_strategy import ProgramStrategy
        from research_engine.programs.program_state import ProgramState
        strategy = ProgramStrategy()
        programs = [
            ProgramState(name="A", budget_remaining=0),
        ]
        assert strategy.allocate(programs) is None


class TestProgramScheduler:
    def test_register_and_get(self):
        from research_engine.programs.program_scheduler import ProgramScheduler
        from research_engine.programs.program_state import ProgramState
        scheduler = ProgramScheduler()
        ps = ProgramState(name="Test")
        scheduler.register_program(ps)
        assert scheduler.get_program(ps.program_id) is not None

    def test_next_allocation(self):
        from research_engine.programs.program_scheduler import ProgramScheduler
        from research_engine.programs.program_state import ProgramState
        scheduler = ProgramScheduler()
        scheduler.register_program(ProgramState(name="A"))
        decision = scheduler.next_allocation()
        assert decision is not None

    def test_update_progress(self):
        from research_engine.programs.program_scheduler import ProgramScheduler
        from research_engine.programs.program_state import ProgramState
        scheduler = ProgramScheduler()
        ps = ProgramState(name="A", progress=0.0)
        scheduler.register_program(ps)
        scheduler.update_progress(ps.program_id, 0.5)
        assert scheduler.get_program(ps.program_id).progress == 0.5

    def test_deduct_budget(self):
        from research_engine.programs.program_scheduler import ProgramScheduler
        from research_engine.programs.program_state import ProgramState
        scheduler = ProgramScheduler()
        ps = ProgramState(name="A", budget_remaining=100)
        scheduler.register_program(ps)
        scheduler.deduct_budget(ps.program_id, 30)
        assert scheduler.get_program(ps.program_id).budget_remaining == 70


class TestProgramManager:
    def test_create_program(self):
        from research_engine.programs.program_manager import ProgramManager
        manager = ProgramManager()
        pid = manager.create_program("Test", objectives=["Objective 1"])
        assert pid
        program = manager.get_program(pid)
        assert program.name == "Test"

    def test_next_allocation(self):
        from research_engine.programs.program_manager import ProgramManager
        manager = ProgramManager()
        manager.create_program("A")
        decision = manager.next()
        assert decision is not None

    def test_record_progress_and_cost(self):
        from research_engine.programs.program_manager import ProgramManager
        manager = ProgramManager()
        pid = manager.create_program("A", budget=50)
        manager.record_progress(pid, 0.3)
        manager.record_cost(pid, 10)
        program = manager.get_program(pid)
        assert program.progress == 0.3
        assert program.budget_remaining == 40

    def test_active_programs(self):
        from research_engine.programs.program_manager import ProgramManager
        manager = ProgramManager()
        manager.create_program("A")
        manager.create_program("B")
        assert len(manager.active_programs) == 2
