"""CI validates the portable/backend suite, not Ghidra or a live account."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_runs_only_local_checks_with_pinned_actions_and_matching_cache_path():
    path = ROOT / '.github/workflows/checks.yml'
    assert path.is_file(), 'Backend prototype has no repository CI workflow'
    text = path.read_text()
    assert 'contents: read' in text
    assert 'cache-dependency-path: requirements-dev.txt' in text
    assert 'pip install -r requirements-dev.txt' in text
    assert 'python -m pytest -q' in text
    assert 'node --check web/usage-config/app.js' in text
    actions = re.findall(r'uses: (actions/[a-z-]+)@([0-9a-f]{40})', text)
    assert len(actions) == 3
    assert {name for name, _ in actions} == {'actions/checkout', 'actions/setup-python', 'actions/setup-node'}
    assert '${{ secrets.' not in text
    assert 'claude auth' not in text and 'analyzeHeadless' not in text
