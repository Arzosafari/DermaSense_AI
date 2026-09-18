# backend/app/agents/roles/conversation_agent.py
import json
import time
import logging
from app.agents.base.base_agent import BaseAgent
from app.utils.prompt_loader import load_prompt
from typing import List, TypedDict
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    user_message: str
    llm_output: str
    run_id: str
    chat_history: list


class ConversationAgent(BaseAgent):
    agent_name = "conversation_agent"

    async def llm_node(self, state: dict):
        run_id = state["run_id"]
        print(f"=== CONVERSATION AGENT LLM NODE ===")
        logger.info("Node: llm", extra={"run_id": run_id, "agent": self.agent_name})
        
        # SAFE DEBUG LOGGING
        logger.info("=" * 80)
        logger.info("CONVERSATION AGENT STATE DIAGNOSTICS")
        logger.info("=" * 80)
        logger.info(f"User message: '{state.get('user_message', 'No message')[:100]}'")
        logger.info(f"Has chat_history in state: {'chat_history' in state}")
        if 'chat_history' in state and state['chat_history']:
            chat_history = state['chat_history']
            logger.info(f"Chat history length: {len(chat_history)} messages")
            logger.info(f"Chat history size: {len(json.dumps(chat_history)):,} characters")
            # Count messages with analysis_data
            analysis_messages = [m for m in chat_history if m.get('analysis_data')]
            logger.info(f"Messages with analysis_data: {len(analysis_messages)}")
            # Log largest message
            if chat_history:
                largest_msg = max(chat_history, key=lambda m: len(json.dumps(m)))
                logger.info(f"Largest message size: {len(json.dumps(largest_msg)):,} characters")
        logger.info("=" * 80)
        
        # Detect language from user message
        from app.core.domain_filter import detect_language
        user_message = state.get("user_message", "")
        detected_language = detect_language(user_message)
        logger.info(f"Detected language: {detected_language}", extra={"run_id": run_id, "agent": self.agent_name})
        
        # get past memory from context chat history (more complete)
        past = []
        
        # Try to get chat history from state first (passed from orchestrator)
        if "chat_history" in state and state["chat_history"]:
            # Filter to include only messages with analysis data first, then regular messages
            analysis_messages = [m for m in state["chat_history"] if m.get('analysis_data')]
            regular_messages = [m for m in state["chat_history"] if not m.get('analysis_data')]
            
            # Take up to 2 analysis messages and 3 regular messages
            past = analysis_messages[-2:] + regular_messages[-3:]
            print(f"✅ Using chat history from state: {len(past)} messages ({len(analysis_messages)} with analysis)")
            logger.info(f"✅ Using chat history from state: {len(past)} messages", extra={"run_id": run_id, "agent": self.agent_name})
            print(f"📜 Chat history content: {past[:2] if past else 'Empty'}")
            logger.info(f"📜 Chat history content: {past[:2] if past else 'Empty'}", extra={"run_id": run_id, "agent": self.agent_name})
        # Then try context.chat_history
        elif hasattr(self.context, 'chat_history') and self.context.chat_history:
            past = self.context.chat_history[-20:]  # Get last 20 messages for context (increased to include analysis)
            print(f"✅ Using chat history from context: {len(past)} messages")
            logger.info(f"✅ Using chat history from context: {len(past)} messages", extra={"run_id": run_id, "agent": self.agent_name})
            print(f"📜 Chat history content: {past[:2] if past else 'Empty'}")
            logger.info(f"📜 Chat history content: {past[:2] if past else 'Empty'}", extra={"run_id": run_id, "agent": self.agent_name})
        else:
            # Fallback to memory recall
            past = await self.recall_memory(run_id=run_id, n=5)
            print(f"⚠️ No chat history in context or state, using memory recall: {len(past)} messages")
            logger.info(f"⚠️ No chat history in context or state, using memory recall: {len(past)} messages", extra={"run_id": run_id, "agent": self.agent_name})
            logger.debug(f"Recalled memory: {past}", extra={"run_id": run_id, "agent": self.agent_name})

        # format memory into text
        past_text = "\n".join(
            [f"User: {m['user_message']}\nAssistant: {m['agent_output']}" for m in past if m.get('user_message') and m.get('agent_output')]
        )
        
        # Add analysis data from previous image analyses if available
        analysis_context = ""
        analysis_count = 0
        for m in past:
            print(f"🔍 Checking message for analysis_data: {bool(m.get('analysis_data'))}")
            if m.get('analysis_data'):
                analysis = m['analysis_data']
                print(f"🔍 Analysis keys: {list(analysis.keys())}")
                analysis_size = len(json.dumps(analysis))
                print(f"🔍 Analysis size: {analysis_size:,} characters")
                
                # CRITICAL: Check if analysis is too large and would cause payload issues
                if analysis_size > 5000:
                    logger.warning(f"⚠️ WARNING: Analysis data is very large ({analysis_size:,} chars) - this could cause payload issues")
                    logger.warning(f"⚠️ Only extracting minimal information to avoid payload bloat")
                
                # CRITICAL: Check if analysis contains image data
                if 'input' in analysis and analysis['input'].get('image'):
                    print(f"⚠️ WARNING: Analysis contains image flag - checking for base64")
                    # Check if there's actual base64 data
                    if any('base64' in str(v).lower() for v in analysis.values()):
                        logger.error("🚨 CRITICAL: Analysis contains base64 image data - this will cause payload bloat!")
                
                # Try different possible structures
                if isinstance(analysis, dict):
                    predicted_class = "Unknown"
                    confidence = 0
                    screening_level = "Unknown"
                    
                    # Try to get predicted_class from different possible locations
                    if analysis.get('model', {}).get('predicted_class'):
                        predicted_class = analysis['model']['predicted_class']
                        confidence = analysis['model'].get('confidence', 0)
                        screening_level = analysis.get('risk_assessment', {}).get('screening_level', 'Unknown')
                    elif analysis.get('predicted_class'):
                        predicted_class = analysis['predicted_class']
                        confidence = analysis.get('confidence', 0)
                        screening_level = analysis.get('screening_level', 'Unknown')
                    
                    if predicted_class != "Unknown":
                        analysis_count += 1
                        # Keep it concise to avoid token limit
                        analysis_context += f"\n- {predicted_class} ({confidence:.0%} confidence, {screening_level} risk)"
                        print(f"🔍 Found analysis: {predicted_class}")
                        # Only include the most recent analysis to keep prompt small
                        if analysis_count >= 1:
                            break
        
        if analysis_context:
            past_text += f"\n\nPrevious skin analyses:{analysis_context}"
            print(f"🔍 Added analysis context to prompt")
            print(f"🔍 Analysis context content: {analysis_context}")
        else:
            print(f"⚠️ No analysis data found in history")
        
        print(f"📝 Formatted past text length: {len(past_text)} characters")
        logger.info(f"📝 Formatted past text length: {len(past_text)} characters", extra={"run_id": run_id, "agent": self.agent_name})
        print(f"📝 Formatted past text preview: {past_text[:300]}...")
        logger.debug(f"Formatted past text: {past_text[:500]}...", extra={"run_id": run_id, "agent": self.agent_name})

        template = load_prompt("conversation_prompt.txt")

        # Add language instruction to prompt based on detection
        language_instruction = ""
        if detected_language == "persian":
            language_instruction = "\n\nIMPORTANT: The user wrote in Persian (فارسی). You MUST respond in Persian only. Use formal/polite Persian (شما form) and proper Persian grammar."
        else:
            language_instruction = "\n\nIMPORTANT: The user wrote in English. You MUST respond in English only."

        prompt = template.replace("{{PAST}}", past_text).replace(
            "{{INPUT}}", state["user_message"]
        ) + language_instruction
        
        # Truncate prompt if too long to avoid API errors
        max_prompt_length = 6000  # Conservative limit
        if len(prompt) > max_prompt_length:
            original_length = len(prompt)
            prompt = prompt[:max_prompt_length] + "... [truncated due to length]"
            logger.warning(f"⚠️ Conversation Agent prompt truncated from {original_length:,} to {max_prompt_length:,} characters")
        
        print(f"🎯 LLM prompt length: {len(prompt)} characters")
        logger.info(f"🎯 LLM prompt length: {len(prompt)} characters", extra={"run_id": run_id, "agent": self.agent_name})
        print(f"🎯 LLM prompt preview: {prompt[:200]}...")
        logger.debug(f"LLM prompt preview: {prompt[:300]}...", extra={"run_id": run_id, "agent": self.agent_name})

        raw = await self.llm_call(prompt, run_id=run_id)
        print(f"💬 Raw LLM response length: {len(raw)} characters")
        logger.info(f"💬 Raw LLM response length: {len(raw)} characters", extra={"run_id": run_id, "agent": self.agent_name})
        print(f"💬 Raw LLM response preview: {raw[:200]}...")
        logger.debug(f"Raw LLM response: {raw[:300]}...", extra={"run_id": run_id, "agent": self.agent_name})
        state["llm_output"] = raw.strip()
        return state

    def build_graph(self):
        workflow = StateGraph(ConversationState)

        async def llm_wrapper(state):
            return await self.llm_node(state)

        workflow.add_node("llm", llm_wrapper)

        workflow.set_entry_point("llm")
        workflow.add_edge("llm", END)  # مستقیم به END - memory در orchestrator ذخیره می‌شه

        return workflow.compile()

    async def run(self, user_message: str, run_id: str, **kwargs):
        start_time = time.time()
        logger.info("Agent run started", extra={"run_id": run_id, "agent": self.agent_name})
        logger.info(f"🔧 ConversationAgent kwargs keys: {list(kwargs.keys())}")
        logger.info(f"🔧 ConversationAgent chat_history in kwargs: {'chat_history' in kwargs}")
        if 'chat_history' in kwargs:
            logger.info(f"🔧 ConversationAgent chat_history length: {len(kwargs['chat_history'])}")
        
        graph = self.build_graph()

        # Build state with chat_history
        initial_state = {
            "user_message": user_message, 
            "llm_output": "", 
            "run_id": run_id,
            "chat_history": kwargs.get("chat_history", [])
        }
        logger.info(f"🎯 Initial state for conversation agent: chat_history={len(initial_state['chat_history'])}")
        
        result = await graph.ainvoke(initial_state)
        
        end_time = time.time()
        latency = end_time - start_time
        logger.info("Agent run finished", extra={"run_id": run_id, "agent": self.agent_name, "latency": latency})

        return {"llm_output": result["llm_output"]}


# Manual debug runner
if __name__ == "__main__":
    import asyncio
    from app.core.agent_context import AgentContext

    async def test():
        context = AgentContext()
        context.debug = True

        agent = ConversationAgent(context)
        result = await agent.run("Hi who are you?", run_id="debug")
        print("\nFinal Output:", result)

    asyncio.run(test())