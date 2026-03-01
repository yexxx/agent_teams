import asyncio
from agent_teams.interfaces.sdk.client import AgentTeamsApp
from agent_teams.core.models import IntentInput

async def main():
    app = AgentTeamsApp()
    print("Loaded Roles:")
    for role in app.list_roles():
        print(f"Role: {role.name} - MCPs: {role.mcp_servers}")
        
    print("Running Intent...")
    for ev in app.run_intent_stream(IntentInput(intent="有哪些工具可以执行？")):
        pass
        
if __name__ == "__main__":
    asyncio.run(main())
