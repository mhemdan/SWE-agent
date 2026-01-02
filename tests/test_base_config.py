import yaml

from sweagent import CONFIG_DIR


def test_base_config_loads_universal_settings():
    base_config_path = CONFIG_DIR / "base.yaml"
    data = yaml.safe_load(base_config_path.read_text())

    agent = data["agent"]
    tools = agent["tools"]
    bundles = tools["bundles"]

    assert bundles == [
        {"path": "tools/registry"},
        {"path": "tools/edit_anthropic"},
        {"path": "tools/review_on_submit_m"},
    ]
    assert tools["env_variables"] == {
        "PAGER": "cat",
        "MANPAGER": "cat",
        "GIT_PAGER": "cat",
    }
    assert tools["registry_variables"] == {
        "USE_FILEMAP": "true",
    }
    assert tools["parse_function"] == {"type": "thought_action"}

    processors = agent["history_processors"]
    assert processors == [{"type": "cache_control", "last_n_messages": 2}]

    templates = agent["templates"]
    system_prompt = templates["system_template"]
    assert "CRITICAL CONSTRAINTS" in system_prompt
    assert "Do NOT create README" in system_prompt

    assert templates["next_step_template"].strip().startswith("OBSERVATION:")
    assert "did not produce any output" in templates["next_step_no_output_template"]
