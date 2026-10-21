# Target agent profile: <agent name and version>

Mark every field: **verified** (observed in this environment), **documented** (read in official docs), or **assumed** (not confirmed). Do not build on assumed fields without telling the user.

| Field | Finding | Status | How I found out |
|---|---|---|---|
| Skill format (SKILL.md folder? rules file? plugin? command?) | | | |
| Where skills are discovered (path / config) | | | |
| Activation (automatic from description / explicit command / always-on / manual) | | | |
| Tools available (file, shell, search, web, edit) and permission prompts | | | |
| Context window, on-demand file loading, memory or notes | | | |
| Delegation (subagents / parallel workers / background tasks / none) | | | |
| Model access (models configured, local or cloud) | | | |
| Automation interfaces (headless mode, hooks, MCP/tool servers, scheduling) | | | |
| Limits and risks (sandbox, network, rate limits) | | | |

## User and environment (Layer 3)
| Field | Finding | Source (user said / found in config / default) |
|---|---|---|
| Tasks the user will use this skill for | | |
| Workflow preferences (output locations, naming, approvals, verbosity, language) | | |
| Local or cloud execution; may data leave the machine? | | |
| Available models | | |
| Operating system and shell | | |
| Permissions (read / write / run / network) | | |
| Resource limits (memory, disk, GPU, time, budget) | | |
| Existing tools and skills that overlap | | |
