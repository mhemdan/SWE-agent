from __future__ import annotations

from typing import Any

ALLOWED_BUNDLE_PREFIXES: tuple[str, ...] = (
    'tools/',
)
DISALLOWED_BUNDLE_PREFIXES: tuple[str, ...] = (
    'tools/experimental',
    'tools/fs_write',
    'tools/system_shell',
)
REQUIRED_AGENT_KEYS = ('tools', 'templates')
REQUIRED_TEMPLATE_KEYS = ('system_template',)
REQUIRED_HISTORY_PROCESSORS = ('cache_control',)


def validate_config_schema(config: dict[str, Any]) -> None:
    if 'agent' not in config:
        raise ValueError('Config missing top-level "agent" section')
    agent = config['agent']
    if not isinstance(agent, dict):
        raise ValueError('agent must be a mapping')

    for key in REQUIRED_AGENT_KEYS:
        if key not in agent:
            raise ValueError(f'agent.{key} is required')

    templates = agent['templates']
    if not isinstance(templates, dict):
        raise ValueError('agent.templates must be a mapping')
    for key in REQUIRED_TEMPLATE_KEYS:
        if key not in templates or not isinstance(templates[key], str):
            raise ValueError(f'agent.templates.{key} must be provided as text')

    tools = agent['tools']
    if not isinstance(tools, dict):
        raise ValueError('agent.tools must be a mapping')

    bundles = tools.get('bundles', [])
    if not isinstance(bundles, list):
        raise ValueError('agent.tools.bundles must be a list')

    for bundle in bundles:
        path = bundle.get('path') if isinstance(bundle, dict) else bundle
        if not isinstance(path, str):
            raise ValueError('tool bundles must include a string path')
        if not path.startswith(ALLOWED_BUNDLE_PREFIXES):
            raise ValueError(f'Bundle path {path} must live under tools/')
        if path.startswith(DISALLOWED_BUNDLE_PREFIXES):
            raise ValueError(f'Bundle path {path} is not permitted in dynamic configs')

    history_processors = config.get('agent', {}).get('history_processors', [])
    required_processors = set(REQUIRED_HISTORY_PROCESSORS)
    for processor in history_processors:
        if isinstance(processor, dict):
            processor_type = processor.get('type')
            required_processors.discard(processor_type)
    if required_processors:
        missing = ', '.join(sorted(required_processors))
        raise ValueError(f'Missing required history processors: {missing}')
