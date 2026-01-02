from pathlib import Path

import pytest

from sweagent.config import ConfigLoader

TEST_DATA_DIR = Path(__file__).parent / "test_data" / "config_loader"


@pytest.fixture
def loader():
    return ConfigLoader(base_dir=TEST_DATA_DIR)


def test_simple_inheritance(loader: ConfigLoader):
    config = loader.load_config("language_go.yaml")

    bundles = config["agent"]["tools"]["bundles"]
    assert bundles == [
        {"path": "tools/base_bundle"},
        {"path": "tools/go_bundle"},
    ]
    env_vars = config["agent"]["tools"]["env_variables"]
    assert env_vars["BASE_FLAG"] == "enabled"
    assert env_vars["GO111MODULE"] == "on"
    assert config["custom_steps"] == ["setup", "compile"]


def test_multiple_inheritance_layers(loader: ConfigLoader):
    config = loader.load_config("docker_go.yaml")

    bundles = config["agent"]["tools"]["bundles"]
    assert bundles == [
        {"path": "tools/base_bundle"},
        {"path": "tools/go_bundle"},
        {"path": "tools/docker_bundle"},
    ]
    assert config["custom_steps"] == ["setup", "compile", "deploy", "smoke"]
    env = config["agent"]["tools"]["env_variables"]
    assert env["BASE_FLAG"] == "enabled"
    assert env["GO111MODULE"] == "on"
    assert env["DOCKER_BUILDKIT"] == "1"
    assert env["EXTRA_FLAG"] == "enabled"


def test_override_replaces_template(loader: ConfigLoader):
    config = loader.load_config("override_template.yaml")
    assert config["agent"]["templates"]["system_template"] == "Specialized Template"


def test_multiple_extends_not_supported(loader: ConfigLoader):
    config = loader.load_config("priority_combo.yaml")
    assert config["settings"]["prompt"] == "second"
    assert config["settings"]["steps"] == ["alpha", "beta", "gamma"]
