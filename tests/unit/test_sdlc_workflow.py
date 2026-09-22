"""The project-specific lifecycle workflow.

A lifecycle label tells a team what to call their process; the brief asks for
the workflow that tells them how to run it. These fix the properties that make
the generated workflow trustworthy rather than decorative.
"""

from __future__ import annotations

import pytest

from nyaya.core.enums import SDLCModel
from nyaya.graph.gates import GATES
from nyaya.mcda.workflow import CADENCE, generate


@pytest.mark.parametrize("model", list(SDLCModel))
def test_every_lifecycle_produces_a_complete_workflow(model: SDLCModel):
    workflow = generate(model)

    assert workflow.cadence == CADENCE[model]
    assert len(workflow.phases) >= 5
    for phase in workflow.phases:
        assert phase.entry_criteria, f"{phase.name} has no entry criteria"
        assert phase.exit_criteria, f"{phase.name} has no exit criteria"
        assert phase.activities, f"{phase.name} has no activities"
        assert phase.roles, f"{phase.name} names no responsible role"


@pytest.mark.parametrize("model", list(SDLCModel))
def test_every_named_gate_exists_in_the_engine(model: SDLCModel):
    """A plan promising checkpoints the machinery does not implement is worse
    than no plan. The workflow may only name gates the graph actually stops at."""
    for gate in generate(model).gates:
        assert gate in GATES, f"{gate} is not a real gate"


def test_findings_add_activities_and_each_says_why():
    """Nothing appears in the workflow without a stated reason."""
    workflow = generate(
        SDLCModel.AGILE_DEVSECOPS_HYBRID,
        blocking_gaps=8,
        critical_requirements=2,
        open_questions=3,
        legacy_integration=True,
    )
    added = [a for phase in workflow.phases for a in phase.activities if a.because]

    assert added, "no activity was attributed to a finding"
    assert all(a.because for a in added)
    assert any("blocking" in a.because for a in added)
    assert any("critical" in a.because for a in added)
    assert any("existing systems" in a.because for a in added)


def test_a_clean_project_gets_only_the_skeleton():
    """No findings, no added activities - the workflow must not invent work."""
    workflow = generate(SDLCModel.AGILE)
    assert not [a for phase in workflow.phases for a in phase.activities if a.because]
    assert not workflow.notes


def test_blocking_gaps_become_an_exit_criterion_not_just_a_note():
    """A note can be read past. An exit criterion stops the phase."""
    workflow = generate(SDLCModel.WATERFALL, blocking_gaps=3)
    requirements = workflow.phases[0]

    assert any("blocking control gap" in c for c in requirements.exit_criteria)
    assert any("3 blocking" in n for n in workflow.notes)


def test_security_and_compliance_activities_are_marked_throughout():
    """The brief asks for security activities and compliance checkpoints by name,
    so they have to be identifiable rather than buried in the activity list."""
    workflow = generate(SDLCModel.DEVSECOPS, critical_requirements=1)
    activities = [a for phase in workflow.phases for a in phase.activities]

    assert sum(1 for a in activities if a.security) >= 3
    assert sum(1 for a in activities if a.compliance) >= 3


def test_iterative_and_sequential_models_differ_in_cadence():
    assert generate(SDLCModel.AGILE).cadence != generate(SDLCModel.WATERFALL).cadence
