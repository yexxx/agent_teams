from __future__ import annotations

from agent_teams.tools.stage.read_stage_input import register as register_read_stage_input
from agent_teams.tools.stage.write_stage_doc import register as register_write_stage_doc

TOOLS = {
    'read_stage_input': register_read_stage_input,
    'write_stage_doc': register_write_stage_doc,
}
