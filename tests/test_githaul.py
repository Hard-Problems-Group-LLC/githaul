import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import githaul
from rich.console import Console


def test_parse_org_user_alias_user_only():
    org, user, alias = githaul.parse_org_user_alias("alice@gh")
    assert org is None
    assert user == "alice"
    assert alias == "gh"


def test_parse_org_user_alias_org_prefix():
    org, user, alias = githaul.parse_org_user_alias("Acme:alice@gh")
    assert org == "Acme"
    assert user == "alice"
    assert alias == "gh"


def test_display_table_has_visibility_column():
    githaul.console = Console(record=True)
    sample = [{
        'name': 'repo1',
        'visibility': 'PUBLIC',
        'status': 'SYNCHRONIZED',
        'branch': 'main',
        'path': '',
        'remote_url': '',
        'has_submodules': False
    }]
    githaul.display_repos_table(sample, title="Test")
    out = githaul.console.export_text()
    assert "VISIBILITY" in out
