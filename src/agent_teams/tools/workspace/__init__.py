from __future__ import annotations

from agent_teams.tools.workspace.glob import register as register_glob
from agent_teams.tools.workspace.grep import register as register_grep
from agent_teams.tools.workspace.read import register as register_read
from agent_teams.tools.workspace.shell import register as register_shell
from agent_teams.tools.workspace.write import register as register_write

TOOLS = {
    'glob': register_glob,
    'grep': register_grep,
    'read': register_read,
    'write': register_write,
    'shell': register_shell,
}
