# backend/app/core/agent_orchestrator.py
from app.agents.factories.agent_factory import AgentFactory
from app.core.agent_context import AgentContext
from app.core.metrics_tracker import metrics_tracker
import logging
import uuid
import traceback

logger = logging.getLogger(__name__)


class AgentOrchetrator:
    def __init__(self, context: AgentContext):
        self.context = context
        self.factory = AgentFactory(context)

    async def run(
        self,
        user_message: str,
        image_base64: str = None,
        capture_trace: bool = False,
        user_profile: dict = None,
        chat_history: list = None
    ):
        run_id = str(uuid.uuid4())
        session_id = getattr(self.context, "session_id", "unknown-session")
        print(f"🔵 Orchestrator run started | session_id={session_id} | run_id={run_id}")
        logger.info(f"🔵 Orchestrator run started | session_id={session_id} | run_id={run_id}")
        print(f"🔵 User message: {user_message[:100]}...")
        logger.info(f"🔵 User message: {user_message[:100]}...")
        print(f"🔵 Chat history provided: {len(chat_history) if chat_history else 0} messages")
        logger.info(f"🔵 Chat history provided: {len(chat_history) if chat_history else 0} messages")
        metrics_tracker.start_run(run_id=run_id, session_id=session_id, user_message=user_message)
        
        # Store chat history in context for agents to use
        if chat_history:
            self.context.chat_history = chat_history
            print(f"✅ Loaded {len(chat_history)} messages from chat history for context")
            logger.info(f"✅ Loaded {len(chat_history)} messages from chat history for context")
            print(f"📜 Chat history sample: {chat_history[:2] if chat_history else 'Empty'}")
            logger.info(f"📜 Chat history sample: {chat_history[:2] if chat_history else 'Empty'}")
        else:
            print(f"⚠️ No chat history provided for context")
            logger.warning(f"⚠️ No chat history provided for context")
        
        try:
            # ========== مسیر تصویر ==========
            if image_base64:
                logger.info("Image detected. Running ImageAgent directly.", extra={"run_id": run_id})
                agent = self.factory.create("image_agent")
                result = await agent.run(
                    user_message=user_message,
                    run_id=run_id,
                    image_base64=image_base64,
                    user_profile=user_profile,
                    chat_history=chat_history or []
                )
                final_output = result.get("final_output", "Could not analyze the image.")
                
                # 🆕 ذخیره‌سازی غیرفعال شد - chat.py خودش save می‌کند
                # try:
                #     await self.context.short_memory.save(...)
                #     await self.context.long_memory.save(...)
                # except Exception as e:
                #     logger.warning(f"Memory save failed: {e}")

                metrics_tracker.end_run(run_id=run_id, final_output=final_output)
                # Return both final_output and structured analysis data
                return {
                    "final_output": final_output,
                    "run_id": run_id,
                    "analysis": result.get("analysis", {})
                }

            # ========== مسیر متن ==========
            logger.info(f"Starting text pipeline for: {user_message[:100]}", extra={"run_id": run_id})

            # 1. Decider
            decider = self.factory.create("decider_agent")
            plan = await decider.run(user_message, run_id=run_id)
            
            metrics_tracker.record_route(
                run_id=run_id,
                intent=plan.get("intent", "unknown"),
                agents=plan.get("agents") or ["conversation_agent"],
            )

            state = {
                "user_message": user_message,
                "run_id": run_id,
                "intent": plan.get("intent", "unknown"),
                "user_profile": user_profile or {},
                "chat_history": chat_history or []
            }
            logger.info(f"📝 State built with chat_history: {len(state.get('chat_history', []))} messages")
            agent_sequence = plan.get("agents") or ["conversation_agent"]

            # 2. اجرای عامل‌های متنی
            for agent_name in agent_sequence:
                logger.info(f"Invoking agent: {agent_name}", extra={"run_id": run_id})
                try:
                    agent = self.factory.create(agent_name)
                except ValueError:
                    continue

                try:
                    result = await agent.run(**state)
                    state.update(result)
                except Exception as e:
                    logger.error(f"Agent {agent_name} failed: {e}")
                    state["error"] = str(e)

            # 3. Reasoning
            reasoner = self.factory.create("reasoning_agent")
            final = await reasoner.run(**state)
            final_output = final.get("final_output", "I'm sorry, I couldn't process your request.")

            # 🆕 ذخیره‌سازی غیرفعال شد - chat.py خودش save می‌کند
            # try:
            #     await self.context.short_memory.save(...)
            #     await self.context.long_memory.save(...)
            # except Exception as e:
            #     logger.warning(f"Memory save failed: {e}")

            metrics_tracker.end_run(run_id=run_id, final_output=final_output)
            return {"final_output": final_output, "run_id": run_id}
            
        except Exception as exc:
            logger.error(f"Orchestrator run failed: {exc}", extra={"run_id": run_id})
            metrics_tracker.end_run(run_id=run_id, error=str(exc))
            return {
                "final_output": "System error. Please try again.",
                "run_id": run_id,
                "error": True
            }


AgentOrchestrator = AgentOrchetrator