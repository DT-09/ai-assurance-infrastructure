from .models import Agent, AgentStatus


def is_agent_active(agent: Agent) -> bool:
    return agent.status == AgentStatus.ACTIVE


def suspend_agent(agent: Agent) -> Agent:
    agent.status = AgentStatus.SUSPENDED
    return agent


def revoke_agent(agent: Agent) -> Agent:
    agent.status = AgentStatus.REVOKED
    return agent