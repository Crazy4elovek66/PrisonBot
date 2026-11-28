from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "deploy.yml"
GITIGNORE_PATH = ROOT / ".gitignore"


def test_deploy_workflow_exists_and_valid_yaml():
    assert WORKFLOW_PATH.is_file(), ".github/workflows/deploy.yml must exist"
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    assert isinstance(data, dict)

    # PyYAML parses unquoted 'on' key as boolean True in YAML 1.1
    on_block = data.get("on") or data.get(True)
    assert isinstance(on_block, dict), "Workflow must define 'on' triggers"
    assert "push" in on_block
    assert "main" in on_block["push"]["branches"]
    assert "task.md" in on_block["push"].get("paths-ignore", [])
    assert "workflow_dispatch" in on_block

    jobs = data.get("jobs", {})
    assert "test" in jobs
    assert "deploy" in jobs

    deploy_needs = jobs["deploy"].get("needs")
    if isinstance(deploy_needs, list):
        assert "test" in deploy_needs
    else:
        assert deploy_needs == "test"


def test_deploy_workflow_uses_secrets_and_no_hardcoded_credentials():
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "${{ secrets.VPS_HOST }}" in raw
    assert "${{ secrets.VPS_USER }}" in raw
    assert "${{ secrets.VPS_SSH_KEY }}" in raw

    forbidden = [
        "178.17.60.16",
        "BEGIN OPENSSH PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "KKeyaruga",
    ]
    for token in forbidden:
        assert token not in raw, f"Forbidden secret/IP token found in deploy.yml: {token}"


def test_gitignore_protects_secrets_and_db():
    assert GITIGNORE_PATH.is_file(), ".gitignore must exist"
    lines = {
        line.strip()
        for line in GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    required_rules = {
        ".env",
        ".env_server",
        "github_setup_keys.txt",
        "*.db",
        "*.session",
    }
    missing = required_rules - lines
    assert not missing, f"Missing required .gitignore rules: {sorted(missing)}"
