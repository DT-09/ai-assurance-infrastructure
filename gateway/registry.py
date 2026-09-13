from .models import Agent, AgentStatus
from .storage import SQLiteStorage


class AgentRegistry:
    def __init__(self, database_path: str = "gateway.db"):
        self.storage = SQLiteStorage(database_path)

    def register(self, agent: Agent) -> Agent:
        self.storage.save_agent(agent)
        return agent

    def get(self, agent_id: str) -> Agent | None:
        return self.storage.get_agent(agent_id)

    def remove(self, agent_id: str) -> None:
        self.storage.delete_agent(agent_id)

    def all(self) -> dict[str, Agent]:
        return self.storage.get_all_agents()

    def suspend(self, agent_id: str) -> Agent | None:
        agent = self.get(agent_id)

        if agent is None:
            return None

        agent.status = AgentStatus.SUSPENDED
        self.storage.save_agent(agent)

        return agent

    def revoke(self, agent_id: str) -> Agent | None:
        agent = self.get(agent_id)

        if agent is None:
            return None

        agent.status = AgentStatus.REVOKED
        self.storage.save_agent(agent)

        return agent