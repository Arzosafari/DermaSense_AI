# backend/app/agents/roles/disease_info_agent.py
import logging
import json
import time
import re
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from app.agents.base.base_agent import BaseAgent
from app.tools.medical.biomedical_ner_tool import BiomedicalNERTool
from app.tools.medical.disease_info_tool import DiseaseInfoRetrieverTool
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class DiseaseInfoState(TypedDict):
    user_message: str
    ner_entities: Dict[str, Any]
    llm_output: str
    extracted_disease: str
    disease_info: str
    db_success: bool
    detected_language: str
    run_id: str


class DiseaseInfoAgent(BaseAgent):
    agent_name = "disease_info_agent"

    def __init__(self, context):
        super().__init__(context)
        if not hasattr(self, "tools") or self.tools is None:
            self.tools = {}

        if "biomedical_ner_tool" not in self.tools:
            self.tools["biomedical_ner_tool"] = BiomedicalNERTool()
        if "disease_info_retriever_tool" not in self.tools:
            self.tools["disease_info_retriever_tool"] = DiseaseInfoRetrieverTool()

        self.ner_tool = self.tools["biomedical_ner_tool"]
        self.db_tool = self.tools["disease_info_retriever_tool"]

        # غیرفعال کردن Google Search (حالت آفلاین)
        self.google = None
        logger.info(f"Agent '{self.agent_name}' initialized without Google Search (offline mode)")

    def _detect_language(self, text: str) -> str:
        """تشخیص زبان متن کاربر"""
        if not text:
            return "en"
        
        persian_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
        persian_chars = len(persian_pattern.findall(text))
        
        english_pattern = re.compile(r'[a-zA-Z]')
        english_chars = len(english_pattern.findall(text))
        
        total_alpha = persian_chars + english_chars
        
        if total_alpha == 0:
            return "en"
        
        if persian_chars / total_alpha > 0.3:
            return "fa"
        
        return "en"

    async def ner_node(self, state: DiseaseInfoState):
        run_id = state["run_id"]
        logger.info("Node: ner", extra={"run_id": run_id, "agent": self.agent_name})
        
        language = self._detect_language(state["user_message"])
        state["detected_language"] = language
        logger.info(f"Detected language: {language}")
        
        entities = await self.ner_tool.run(state["user_message"], run_id=run_id)
        state["ner_entities"] = entities
        return state

    async def llm_node(self, state: DiseaseInfoState):
        run_id = state["run_id"]
        logger.info("Node: llm", extra={"run_id": run_id, "agent": self.agent_name})
        template = load_prompt("disease_info_prompt.txt")

        prompt = template.replace("{{INPUT}}", state["user_message"]).replace(
            "{{NER_CONTEXT}}", json.dumps(state["ner_entities"])
        )

        raw = await self.llm_call(prompt, run_id=run_id)
        state["llm_output"] = raw.strip()
        return state

    async def parse_node(self, state):
        run_id = state["run_id"]
        logger.info("Node: parse", extra={"run_id": run_id, "agent": self.agent_name})
        
        diseases = state["ner_entities"].get("diseases", [])
        if diseases:
            state["extracted_disease"] = diseases[0]
            return state

        raw = state["llm_output"]
        try:
            parsed = json.loads(raw)
            state["extracted_disease"] = parsed.get("disease", "none")
        except:
            state["extracted_disease"] = "none"

        return state

    async def local_db_node(self, state: DiseaseInfoState):
        run_id = state["run_id"]
        logger.info("Node: local_db", extra={"run_id": run_id, "agent": self.agent_name})
        disease = state.get("extracted_disease")

        if not disease or disease == "none":
            state["db_success"] = False
            state["disease_info"] = {
                "error": "No disease name could be extracted.",
                "suggestion": "Please specify a disease name."
            }
            return state

        try:
            retrieved = await self.db_tool.run(disease, run_id=run_id)

            if retrieved and isinstance(retrieved, dict) and "error" not in retrieved:
                state["disease_info"] = retrieved
                state["db_success"] = True
            else:
                state["db_success"] = False
                state["disease_info"] = {
                    "error": f"No information found for disease: {disease}",
                    "disease": disease
                }

        except Exception as e:
            logger.error(f"Error while querying DB for disease: {disease}", exc_info=True)
            state["db_success"] = False
            state["disease_info"] = {"error": f"Database error: {str(e)}"}

        return state

    def build_graph(self):
        workflow = StateGraph(DiseaseInfoState)

        workflow.add_node("ner", self.ner_node)
        workflow.add_node("llm", self.llm_node)
        workflow.add_node("parse", self.parse_node)
        workflow.add_node("local_db", self.local_db_node)

        workflow.set_entry_point("ner")
        workflow.add_edge("ner", "llm")
        workflow.add_edge("llm", "parse")
        workflow.add_edge("parse", "local_db")
        workflow.add_edge("local_db", END)  # مستقیم به END - memory در orchestrator ذخیره می‌شه

        return workflow.compile()

    async def run(self, user_message: str, run_id: str, **kwargs):
        start_time = time.time()
        logger.info("Agent run started", extra={"run_id": run_id, "agent": self.agent_name})
        
        language = self._detect_language(user_message)
        logger.info(f"Detected language for '{user_message[:50]}...': {language}")

        graph = self.build_graph()

        # مسیر مستقیم (اگر disease_matched از قبل وجود دارد)
        if "disease_matched" in kwargs and kwargs["disease_matched"]:
            disease_raw = kwargs["disease_matched"]
            if isinstance(disease_raw, dict):
                disease = disease_raw.get("disease") or disease_raw.get("name")
            else:
                disease = disease_raw

            db_data = await self.db_tool.run(disease, run_id=run_id)

            if db_data and isinstance(db_data, dict) and "error" not in db_data:
                info = db_data
            else:
                info = {"error": f"No information found for disease: {disease}"}

            latency = time.time() - start_time
            logger.info("Agent run finished (direct path)", extra={"run_id": run_id, "agent": self.agent_name, "latency": latency})
            
            return {"disease": disease, "info": info, "language": language}

        # مسیر گراف
        result = await graph.ainvoke(
            {
                "user_message": user_message,
                "ner_entities": {},
                "llm_output": "",
                "extracted_disease": "",
                "disease_info": "",
                "db_success": False,
                "detected_language": language,
                "run_id": run_id
            }
        )

        latency = time.time() - start_time
        logger.info("Agent run finished (graph path)", extra={"run_id": run_id, "agent": self.agent_name, "latency": latency})

        return {
            "disease": result["extracted_disease"], 
            "info": result["disease_info"],
            "language": result.get("detected_language", language)
        }


# Manual debug runner
if __name__ == "__main__":
    import asyncio
    from app.core.agent_context import AgentContext

    async def test():
        context = AgentContext()
        context.debug = True

        agent = DiseaseInfoAgent(context)
        
        # تست انگلیسی
        result = await agent.run(
            "Tell me about impetigo",
            run_id="debug"
        )
        print("\nEnglish test:")
        print(f"  Disease: {result.get('disease')}")
        print(f"  Language: {result.get('language')}")
        
        # تست فارسی
        result = await agent.run(
            "در مورد بیماری زردزخم توضیح بده",
            run_id="debug"
        )
        print("\nPersian test:")
        print(f"  Disease: {result.get('disease')}")
        print(f"  Language: {result.get('language')}")

    asyncio.run(test())