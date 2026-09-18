# backend/app/agents/roles/symptom_matcher_agent.py
import json
import time
import logging
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from app.agents.base.base_agent import BaseAgent
from app.tools.medical.biomedical_ner_tool import BiomedicalNERTool
from app.tools.medical.symptom_matcher_tool import SymptomDiseaseMatcherTool
from app.utils.prompt_loader import load_prompt


logger = logging.getLogger(__name__)


class SymptomMatcherState(TypedDict):
    user_message: str
    ner_entities: Dict[str, Any]
    disease_matched: str
    llm_output: str
    symptoms: List[str]
    run_id: str


class SymptomMatcherAgent(BaseAgent):
    agent_name = "symptom_matcher_agent"

    def __init__(self, context):
        super().__init__(context)
        if not hasattr(self, "tools") or self.tools is None:
            self.tools = {}

        if "biomedical_ner_tool" not in self.tools:
            self.tools["biomedical_ner_tool"] = BiomedicalNERTool()
        if "symptom_disease_matcher_tool" not in self.tools:
            self.tools["symptom_disease_matcher_tool"] = SymptomDiseaseMatcherTool()

        self.ner_tool = self.tools["biomedical_ner_tool"]
        self.symp_match_tool = self.tools["symptom_disease_matcher_tool"]

    async def ner_node(self, state: SymptomMatcherState):
        run_id = state["run_id"]
        logger.info("Node: ner", extra={"run_id": run_id, "agent": self.agent_name})
        entities = await self.ner_tool.run(state["user_message"], run_id=run_id)
        state["ner_entities"] = entities
        return state

    async def llm_node(self, state: SymptomMatcherState):
        run_id = state["run_id"]
        logger.info("Node: llm", extra={"run_id": run_id, "agent": self.agent_name})
        template = load_prompt("symptom_matcher_prompt.txt")
        prompt = template.replace("{{INPUT}}", state["user_message"]).replace(
            "{{NER_CONTEXT}}", json.dumps(state["ner_entities"])
        )

        raw = await self.llm_call(prompt, run_id=run_id)
        state["llm_output"] = raw.strip()
        return state

    async def parse_node(self, state: SymptomMatcherState):
        run_id = state["run_id"]
        logger.info("Node: parse", extra={"run_id": run_id, "agent": self.agent_name})
        raw = state.get("llm_output", "")

        try:
            parsed = json.loads(raw)
        except:
            parsed = {"symptoms": ["None"]}

        state["symptoms"] = parsed.get("symptoms", ["None"])
        return state

    async def matcher_node(self, state: SymptomMatcherState):
        run_id = state["run_id"]
        logger.info("Node: matcher", extra={"run_id": run_id, "agent": self.agent_name})
        matches = await self.symp_match_tool.run(state["symptoms"], run_id=run_id)

        disease_name = None

        # Case 1: tool returns dict with a list of matches
        if isinstance(matches, dict) and "matched_diseases" in matches:
            ranked = matches["matched_diseases"]
            if isinstance(ranked, list) and len(ranked) > 0:
                disease_name = ranked[0].get("disease")

        # Case 2: tool already returns a string
        elif isinstance(matches, str):
            disease_name = matches

        # Safety fallback
        if not disease_name:
            disease_name = "unknown"

        state["disease_matched"] = disease_name
        return state

    def build_graph(self):
        workflow = StateGraph(SymptomMatcherState)

        async def ner_wrapper(state):
            return await self.ner_node(state)

        async def llm_wrapper(state):
            return await self.llm_node(state)

        async def parse_wrapper(state):
            return await self.parse_node(state)

        async def matcher_wrapper(state):
            return await self.matcher_node(state)

        workflow.add_node("ner", ner_wrapper)
        workflow.add_node("llm", llm_wrapper)
        workflow.add_node("parse", parse_wrapper)
        workflow.add_node("matcher", matcher_wrapper)

        workflow.set_entry_point("ner")

        workflow.add_edge("ner", "llm")
        workflow.add_edge("llm", "parse")
        workflow.add_edge("parse", "matcher")
        workflow.add_edge("matcher", END)  # مستقیم به END - memory در orchestrator ذخیره می‌شه

        return workflow.compile()

    async def run(self, user_message: str, run_id: str, **kwargs):
        start_time = time.time()
        logger.info("Agent run started", extra={"run_id": run_id, "agent": self.agent_name})
        
        graph = self.build_graph()

        result = await graph.ainvoke(
            {
                "user_message": user_message,
                "ner_entities": {},
                "disease_matched": "",
                "llm_output": "",
                "symptoms": [],
                "run_id": run_id,
            }
        )
        
        end_time = time.time()
        latency = end_time - start_time
        logger.info("Agent run finished", extra={"run_id": run_id, "agent": self.agent_name, "latency": latency})

        return {
            "symptoms": result["symptoms"],
            "disease_matched": result["disease_matched"],
        }


# Manual debug runner
if __name__ == "__main__":
    import asyncio
    from app.core.agent_context import AgentContext

    async def test():
        context = AgentContext()
        context.debug = True

        agent = SymptomMatcherAgent(context)
        result = await agent.run(
            user_message="I have red itchy patches on my face",
            run_id="debug"
        )
        print("\nFinal Output:", result)

    asyncio.run(test())