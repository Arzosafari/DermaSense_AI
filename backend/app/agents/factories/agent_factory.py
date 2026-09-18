from app.agents.roles.conversation_agent import ConversationAgent
from app.agents.roles.decider_agent import DeciderAgent
from app.agents.roles.disease_info_agent import DiseaseInfoAgent
from app.agents.roles.symptom_matcher_agent import SymptomMatcherAgent
from app.agents.roles.reasoning_agent import ReasoningAgent
from app.agents.roles.image_agent import ImageAgent  # <-- import جدید

class AgentFactory:

    def __init__(self, context):
        self.context = context

        self.registry = {
            "conversation_agent": ConversationAgent,
            "decider_agent": DeciderAgent,
            "disease_info_agent": DiseaseInfoAgent,
            "symptom_matcher_agent": SymptomMatcherAgent,
            "reasoning_agent": ReasoningAgent,
            "image_agent": ImageAgent  # <-- ثبت Agent جدید
        }

    def create(self, name: str):
        if name not in self.registry:
            raise ValueError(f"Unknown agent '{name}'")
        AgentClass = self.registry[name]
        return AgentClass(self.context)