* Default config: `anthropic_filemap.yaml`
* `swebench_submissions`: Configs that were used for swebench submissions
* `sweagent_0_7`: Configs from SWE-agent 0.7, similar to the one used in the paper
* `exotic`: Various specific configurations that might be more of niche interest
* `human`: Demo/debug configs that have the human type commands and run without a LM
* `demo`: Configs for demonstrations/talks
* Configs for running with SWE-smith are at https://github.com/SWE-bench/SWE-smith/blob/main/agent/swesmith_infer.yaml

🔗 Tutorial on [adding custom tools](https://swe-agent.com/latest/usage/adding_custom_tools/)
🔗 For more information on config files, visit [our documentation website][docs].

You can also find the corresponding markdown files in the [`docs/` folder][source].

## Base Configuration

The shared defaults for every agent now live in `config/base.yaml`. This file defines the universally enabled tools (`tools/registry`, `tools/edit_anthropic`, `tools/review_on_submit_m`), enforces the documentation-related system prompt, and standardizes history processors plus next-step templates. Specialized configs can extend from this base to avoid duplicating environment variables or parser definitions.

Inheritance is enabled through the `extends` field:

```
extends: ../base.yaml
agent:
  tools:
    bundles:
      - +path: tools/go_specific
```

Entries prefixed with `+` are appended to the inherited list; entries without `+` replace the inherited value entirely. This allows configs to layer base defaults with specialized additions using the config loader.

### Language Layers

Language-specific presets live under `config/languages/` (e.g., `language-node.yaml`, `language-python.yaml`, `language-go.yaml`, `language-java.yaml`). Each inherits from `base.yaml` and injects compiler/runtime environment variables plus broad expertise prompts for that ecosystem. Specialized configs under `config/specialized/` now extend the appropriate language file—or `base.yaml` when no dedicated language exists—and override only the sections they need (like system prompts, registry variables, or extra env vars).

### Addons & Composition

Optional mixins live in `config/addons/` (Docker, Kubernetes, CI/CD). When a config needs multiple layers, provide an ordered list to `extends`:

```
extends:
  - frontend_react.yaml
  - ../../addons/docker.yaml
```

Parents are merged top-to-bottom, so later entries override earlier ones while the `+` prefix still appends to inherited lists. This lets you compose framework configs with operational addons without copying YAML chunks.

[docs]: https://swe-agent.com/latest/config/config
[source]: https://github.com/SWE-agent/SWE-agent/tree/main/docs
