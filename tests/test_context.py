from pathlib import Path

from phi_coding.context import discover_project_context
from phi_coding.paths import PhiPaths
from phi_coding.resources import PhiResourcePaths


def test_discovers_user_project_and_agents_context_files(tmp_path: Path) -> None:
    phi_home = tmp_path / "home" / ".phi"
    agents_home = tmp_path / "home" / ".agents"
    project = tmp_path / "project"
    nested = project / "pkg"
    nested.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (phi_home).mkdir(parents=True)
    (agents_home).mkdir(parents=True)
    (project / ".phi").mkdir()
    (project / ".agents").mkdir()

    (phi_home / "AGENTS.md").write_text("User Phi instructions", encoding="utf-8")
    (agents_home / "AGENTS.md").write_text("User agents instructions", encoding="utf-8")
    (project / "AGENTS.md").write_text("Project instructions", encoding="utf-8")
    (nested / "AGENTS.md").write_text("Nested instructions", encoding="utf-8")
    (nested / ".phi").mkdir()
    (nested / ".agents").mkdir()
    (nested / ".phi" / "AGENTS.md").write_text("Project Phi instructions", encoding="utf-8")
    (nested / ".agents" / "AGENTS.md").write_text("Project agents instructions", encoding="utf-8")

    context_files = discover_project_context(
        PhiResourcePaths(
            root=phi_home,
            agents_root=agents_home,
            cwd=nested,
            paths=PhiPaths(home=phi_home, agents_home=agents_home),
        )
    )

    assert [Path(context_file.path) for context_file in context_files] == [
        phi_home / "AGENTS.md",
        agents_home / "AGENTS.md",
        project / "AGENTS.md",
        nested / "AGENTS.md",
        nested / ".phi" / "AGENTS.md",
        nested / ".agents" / "AGENTS.md",
    ]
    assert [context_file.content for context_file in context_files] == [
        "User Phi instructions",
        "User agents instructions",
        "Project instructions",
        "Nested instructions",
        "Project Phi instructions",
        "Project agents instructions",
    ]
