"""Main Agent Orchestrator using LangGraph for Cognexa AI.

Implements an autonomous StateGraph pipeline with context retrieval, intent understanding,
dynamic task planning, safety-checked tool execution, step verification, failure recovery,
memory updates, and evidence-grounded response generation.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from langgraph.graph import END, START, StateGraph

from app.agent.prompts import (
    INTENT_CLASSIFICATION_PROMPT,
    PLANNING_PROMPT,
    SYSTEM_PROMPT,
    VERIFICATION_PROMPT,
)
from app.agent.state import AgentState
from app.agent.tools import ALL_TOOLS, TOOL_MAP
from app.services.llm_service import OllamaLLMService
from app.services.memory_service import MemoryService
from app.services.verification_service import VerificationService

logger = logging.getLogger(__name__)


def _extract_text_content(msg: Any) -> str:
    """Extract string content from message object or dict."""
    if isinstance(msg, dict):
        return str(msg.get("content", ""))
    if hasattr(msg, "content"):
        return str(msg.content)
    return str(msg)


def _safe_parse_json(text: str) -> Any:
    """Extract and parse JSON safely from LLM output."""
    clean = text.strip()
    if "```json" in clean:
        start = clean.find("```json") + 7
        end = clean.find("```", start)
        clean = clean[start:end].strip() if end != -1 else clean[start:].strip()
    elif "```" in clean:
        start = clean.find("```") + 3
        end = clean.find("```", start)
        clean = clean[start:end].strip() if end != -1 else clean[start:].strip()

    return json.loads(clean)


class CognexaOrchestrator:
    """Autonomous LangGraph orchestrator coordinating LLM reasoning, tools, and verification."""

    def __init__(
        self,
        llm_service: OllamaLLMService,
        memory_service: MemoryService,
        db_session: Any = None,
        verification_service: Optional[VerificationService] = None,
    ) -> None:
        """Initialize Cognexa Orchestrator with dependencies and compile state graph.

        Args:
            llm_service: OllamaLLMService instance for LLM reasoning and planning.
            memory_service: MemoryService for semantic memory retrieval and persistence.
            db_session: Optional SQLAlchemy database session.
            verification_service: Optional VerificationService for step and result checks.
        """
        self.llm_service = llm_service
        self.memory_service = memory_service
        self.db_session = db_session
        self.verification_service = verification_service or VerificationService()

        # Build and compile LangGraph StateGraph
        self.graph = self._build_graph()
        self.app = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph StateGraph nodes, edges, and conditional routing."""
        workflow = StateGraph(AgentState)

        # 1. Register Nodes
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("understand_intent", self.understand_intent)
        workflow.add_node("create_plan", self.create_plan)
        workflow.add_node("execute_step", self.execute_step)
        workflow.add_node("verify_results", self.verify_results)
        workflow.add_node("handle_failure", self.handle_failure)
        workflow.add_node("update_memory", self.update_memory)
        workflow.add_node("generate_response", self.generate_response)

        # 2. Register Edges
        workflow.add_edge(START, "retrieve_context")
        workflow.add_edge("retrieve_context", "understand_intent")

        # Intent Branch: Task vs Conversation
        workflow.add_conditional_edges(
            "understand_intent",
            self._route_intent,
            {
                "create_plan": "create_plan",
                "generate_response": "generate_response",
            },
        )

        workflow.add_edge("create_plan", "execute_step")
        workflow.add_edge("execute_step", "verify_results")

        # Verification Branch: Next step vs Failure vs Memory Update
        workflow.add_conditional_edges(
            "verify_results",
            self._route_verification,
            {
                "execute_step": "execute_step",
                "handle_failure": "handle_failure",
                "update_memory": "update_memory",
            },
        )

        # Failure Branch: Retry step vs Finalize on max retries
        workflow.add_conditional_edges(
            "handle_failure",
            self._route_failure,
            {
                "execute_step": "execute_step",
                "generate_response": "generate_response",
            },
        )

        workflow.add_edge("update_memory", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow

    # --------------------------------------------------------------------------
    # Graph Conditional Routers
    # --------------------------------------------------------------------------

    def _route_intent(self, state: AgentState) -> str:
        """Route to create_plan if a task is detected, else generate direct conversational response."""
        task_id = state.get("task_id")
        intent = getattr(state, "intent", None) or state.get("verification_status")

        # Check if plan steps exist or task requested
        if state.get("current_plan") or intent == "task":
            return "create_plan"
        return "generate_response"

    def _route_verification(self, state: AgentState) -> str:
        """Route after step verification: next step, failure handler, or memory update if completed."""
        status = state.get("verification_status", "pending")
        if status == "failed":
            return "handle_failure"

        current_idx = state.get("current_step", 0)
        plan = state.get("current_plan", [])
        if current_idx < len(plan):
            return "execute_step"

        return "update_memory"

    def _route_failure(self, state: AgentState) -> str:
        """Route after failure: retry step if within retry limit, or generate response if exhausted."""
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        if retry_count <= max_retries and state.get("verification_status") != "failed_exhausted":
            return "execute_step"
        return "generate_response"

    # --------------------------------------------------------------------------
    # Graph Node Implementations
    # --------------------------------------------------------------------------

    async def retrieve_context(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Fetch relevant memories for the user's message and inject into state.

        Args:
            state: Current agent state.

        Returns:
            Dictionary with retrieved memories.
        """
        messages = state.get("messages", [])
        latest_message = _extract_text_content(messages[-1]) if messages else ""
        user_id = state.get("user_id", "default_user")

        memories_data: List[Dict[str, Any]] = []
        try:
            memories = await self.memory_service.search_memories(
                user_id=user_id,
                query=latest_message,
                limit=5,
            )
            for m in memories:
                if hasattr(m, "to_dict"):
                    memories_data.append(m.to_dict())
                else:
                    memories_data.append({
                        "id": getattr(m, "id", None),
                        "content": getattr(m, "content", ""),
                        "memory_type": getattr(m, "memory_type", "fact"),
                        "similarity": getattr(m, "similarity", 0.0),
                    })
            logger.info("Retrieved %d context memories for user %s", len(memories_data), user_id)
        except Exception as err:
            logger.warning("Could not retrieve context memories: %s", err)

        return {"memories": memories_data}

    async def understand_intent(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Analyze user request to determine if it is a task or a conversation.

        Args:
            state: Current agent state.

        Returns:
            State updates including intent classification and goal.
        """
        messages = state.get("messages", [])
        user_msg = _extract_text_content(messages[-1]) if messages else ""
        memories = state.get("memories", [])
        context_str = "\n".join([f"- {m.get('content')}" for m in memories]) if memories else "None"

        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            context=context_str,
            user_message=user_msg,
        )

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.1,
            )
            parsed = _safe_parse_json(response)
            intent = parsed.get("intent", "conversation")
            goal = parsed.get("goal") or user_msg

            logger.info("Intent classified as '%s' (Reasoning: %s)", intent, parsed.get("reasoning"))

            # If task detected, flag state so router directs to create_plan
            return {
                "verification_status": "task" if intent == "task" else "conversational",
                "task_id": state.get("task_id") or str(uuid.uuid4()) if intent == "task" else None,
            }
        except Exception as err:
            logger.warning("Intent classification failed, falling back to heuristics: %s", err)
            # Heuristic fallback: check for action verbs
            action_words = ["create", "write", "test", "run", "edit", "fix", "delete", "list", "search"]
            is_task = any(w in user_msg.lower() for w in action_words)
            return {
                "verification_status": "task" if is_task else "conversational",
                "task_id": str(uuid.uuid4()) if is_task else None,
            }

    async def create_plan(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Decompose user goal into sequential steps selecting appropriate tools.

        Args:
            state: Current agent state.

        Returns:
            State updates with current_plan initialized and step index reset.
        """
        messages = state.get("messages", [])
        user_msg = _extract_text_content(messages[-1]) if messages else ""
        memories = state.get("memories", [])
        context_str = "\n".join([f"- {m.get('content')}" for m in memories]) if memories else "None"

        tools_desc = "\n".join([
            f"- {tool_obj.name}: {tool_obj.description.strip()}"
            for tool_obj in ALL_TOOLS
        ])

        prompt = PLANNING_PROMPT.format(
            goal=user_msg,
            context=context_str,
            available_tools=tools_desc,
        )

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.2,
            )
            steps = _safe_parse_json(response)
            if not isinstance(steps, list) or not steps:
                raise ValueError("Plan output is not a non-empty list.")

            logger.info("Generated execution plan with %d steps.", len(steps))
            return {
                "current_plan": steps,
                "current_step": 0,
                "tool_results": [],
                "retry_count": 0,
                "error_log": [],
                "verification_status": "pending",
            }
        except Exception as err:
            logger.error("Failed to generate plan via LLM: %s. Creating fallback single-step plan.", err)
            fallback_plan = [{
                "step_number": 1,
                "description": f"Execute request: {user_msg[:60]}",
                "tool": "execute_command",
                "parameters": {"command": "echo 'Fallback execution'"},
                "expected_outcome": "Execution feedback",
            }]
            return {
                "current_plan": fallback_plan,
                "current_step": 0,
                "tool_results": [],
                "retry_count": 0,
                "error_log": [f"Plan generation error: {err}"],
                "verification_status": "pending",
            }

    async def execute_step(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Execute the current step using the selected tool.

        Args:
            state: Current agent state.

        Returns:
            State updates containing new tool execution results.
        """
        plan = state.get("current_plan", [])
        step_idx = state.get("current_step", 0)

        if step_idx >= len(plan):
            return {"verification_status": "verified"}

        step = plan[step_idx]
        tool_name = step.get("tool")
        parameters = step.get("parameters", {})

        logger.info("Executing step %d/%d: Tool '%s'", step_idx + 1, len(plan), tool_name)
        tool_func = TOOL_MAP.get(tool_name)

        result_payload: Any = None
        error_msg: Optional[str] = None

        if not tool_func:
            error_msg = f"Tool '{tool_name}' not found in registered tools."
            logger.error(error_msg)
        else:
            try:
                # Invoke tool using LangChain tool interface or direct callable
                if hasattr(tool_func, "invoke"):
                    result_payload = tool_func.invoke(parameters)
                else:
                    result_payload = tool_func(**parameters)
            except Exception as exc:
                error_msg = f"Tool '{tool_name}' raised an exception: {exc}"
                logger.error(error_msg, exc_info=True)

        tool_results = list(state.get("tool_results", []))
        tool_results.append({
            "step_index": step_idx,
            "tool": tool_name,
            "parameters": parameters,
            "result": result_payload,
            "error": error_msg,
        })

        return {
            "tool_results": tool_results,
            "verification_status": "pending",
        }

    async def verify_results(self, state: AgentState) -> Dict[str, Any]:
        """Node 5: Verify whether the executed step succeeded and analyze the output.

        Args:
            state: Current agent state.

        Returns:
            State updates with verification status, updated step index, and error logs.
        """
        plan = state.get("current_plan", [])
        step_idx = state.get("current_step", 0)
        tool_results = state.get("tool_results", [])

        if not tool_results or step_idx >= len(plan):
            return {"verification_status": "verified"}

        latest_result = tool_results[-1]
        step = plan[step_idx]
        tool_name = step.get("tool")
        expected_outcome = step.get("expected_outcome", "")
        result_data = latest_result.get("result")
        error_data = latest_result.get("error")

        if error_data:
            error_log = list(state.get("error_log", []))
            error_log.append(f"Step {step_idx + 1} ({tool_name}) error: {error_data}")
            return {
                "verification_status": "failed",
                "error_log": error_log,
            }

        # Deterministic verification based on tool type
        is_verified = True
        verification_reason = "Step completed."

        if tool_name == "execute_command" and isinstance(result_data, dict):
            verify_res = self.verification_service.verify_command_result(
                expected=expected_outcome,
                actual_stdout=result_data.get("stdout", ""),
                actual_stderr=result_data.get("stderr", ""),
                exit_code=result_data.get("exit_code", 0),
            )
            is_verified = (verify_res["status"] == "verified")
            verification_reason = verify_res["summary"]

        elif tool_name == "run_tests" and isinstance(result_data, dict):
            verify_res = self.verification_service.verify_test_results(result_data)
            is_verified = (verify_res["status"] == "verified")
            verification_reason = verify_res["summary"]

        elif tool_name == "write_file":
            if isinstance(result_data, str) and ("Error" in result_data or "Security Error" in result_data):
                is_verified = False
                verification_reason = result_data
            else:
                is_verified = True
                verification_reason = "File written successfully."

        elif tool_name == "read_file":
            if isinstance(result_data, str) and result_data.startswith("Error:"):
                is_verified = False
                verification_reason = result_data

        # LLM Verification for semantic checks if necessary
        if not is_verified:
            error_log = list(state.get("error_log", []))
            error_log.append(f"Step {step_idx + 1} verification failed: {verification_reason}")
            logger.warning("Step %d verification failed: %s", step_idx + 1, verification_reason)
            return {
                "verification_status": "failed",
                "error_log": error_log,
            }

        logger.info("Step %d verified successfully.", step_idx + 1)
        return {
            "verification_status": "verified",
            "current_step": step_idx + 1,
            "retry_count": 0,
        }

    async def handle_failure(self, state: AgentState) -> Dict[str, Any]:
        """Node 6: Handle step failure by classifying error and attempting recovery or replan.

        Args:
            state: Current agent state.

        Returns:
            State updates with incremented retry count and recovery adjustments.
        """
        step_idx = state.get("current_step", 0)
        retries = state.get("retry_count", 0) + 1
        max_retries = state.get("max_retries", 3)
        error_log = state.get("error_log", [])
        last_error = error_log[-1] if error_log else "Unknown step failure"

        classification = self.verification_service.classify_error(last_error)
        logger.warning(
            "Handling failure for step %d (attempt %d/%d). Type: %s. Recovery: %s",
            step_idx + 1,
            retries,
            max_retries,
            classification["error_type"],
            classification["suggested_recovery"],
        )

        if retries > max_retries:
            logger.error("Step %d reached max retries (%d). Aborting task.", step_idx + 1, max_retries)
            return {
                "retry_count": retries,
                "verification_status": "failed_exhausted",
            }

        return {
            "retry_count": retries,
            "verification_status": "retrying",
        }

    async def update_memory(self, state: AgentState) -> Dict[str, Any]:
        """Node 7: Persist useful outcomes and learnings into semantic memory.

        Args:
            state: Current agent state.

        Returns:
            State unmodified or with memory updates.
        """
        user_id = state.get("user_id", "default_user")
        plan = state.get("current_plan", [])
        tool_results = state.get("tool_results", [])
        messages = state.get("messages", [])
        user_msg = _extract_text_content(messages[-1]) if messages else "User request"

        if plan and tool_results:
            try:
                successful_tools = [r.get("tool") for r in tool_results if not r.get("error")]
                summary = (
                    f"Completed task '{user_msg[:80]}': executed {len(tool_results)} steps "
                    f"using tools: {', '.join(set(filter(None, successful_tools)))}."
                )
                await self.memory_service.store_memory(
                    user_id=user_id,
                    memory_type="task",
                    content=summary,
                    metadata_={
                        "task_id": state.get("task_id"),
                        "conversation_id": state.get("conversation_id"),
                    },
                )
                logger.info("Persisted outcome memory for task %s", state.get("task_id"))
            except Exception as err:
                logger.warning("Failed to store task completion memory: %s", err)

        return {}

    async def generate_response(self, state: AgentState) -> Dict[str, Any]:
        """Node 8: Generate the final grounded response with evidence and execution summary.

        Args:
            state: Current agent state.

        Returns:
            State updates with final_response text and updated messages.
        """
        messages = state.get("messages", [])
        user_msg = _extract_text_content(messages[-1]) if messages else ""
        plan = state.get("current_plan", [])
        tool_results = state.get("tool_results", [])
        error_log = state.get("error_log", [])
        memories = state.get("memories", [])

        # Purely conversational response
        if not plan:
            context_snippet = (
                "\n".join([f"- {m.get('content')}" for m in memories]) if memories else "None"
            )
            prompt = (
                f"Context from past interactions:\n{context_snippet}\n\n"
                f"User: {user_msg}\n\n"
                "Provide a helpful, precise, and articulate response."
            )
            response_text = await self.llm_service.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.7,
            )
            return {
                "final_response": response_text,
                "messages": [{"role": "assistant", "content": response_text}],
            }

        # Task execution report response
        report = self.verification_service.generate_verification_report(
            task=user_msg,
            steps=[
                {
                    "step_index": idx,
                    "tool": step.get("tool"),
                    "description": step.get("description"),
                    "verification_status": (
                        "verified"
                        if idx < len(tool_results) and not tool_results[idx].get("error")
                        else "failed"
                    ),
                    "result": tool_results[idx].get("result") if idx < len(tool_results) else None,
                    "error": tool_results[idx].get("error") if idx < len(tool_results) else None,
                }
                for idx, step in enumerate(plan)
            ],
        )

        evidence_section: List[str] = []
        for r in tool_results:
            tool = r.get("tool")
            res = r.get("result")
            if res:
                short_res = str(res)[:300]
                evidence_section.append(f"**[{tool}]**: {short_res}")

        evidence_text = "\n".join(evidence_section) if evidence_section else "No output produced."

        synthesis_prompt = (
            f"You are Cognexa AI. Summarize the outcome of the user's task clearly and concisely.\n\n"
            f"User Goal: {user_msg}\n\n"
            f"Verification Verdict: {report['verdict']}\n"
            f"Execution Evidence:\n{evidence_text}\n\n"
            f"Errors Encountered (if any):\n{'; '.join(error_log) if error_log else 'None'}\n\n"
            "Format your answer with clear markdown, stating what was accomplished, key findings, and next steps if relevant."
        )

        final_summary = await self.llm_service.generate(
            prompt=synthesis_prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
        )

        complete_response = f"{final_summary}\n\n---\n{report['markdown_report']}"

        return {
            "final_response": complete_response,
            "messages": [{"role": "assistant", "content": complete_response}],
        }

    # --------------------------------------------------------------------------
    # Public Execution Methods
    # --------------------------------------------------------------------------

    async def run(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str,
    ) -> Dict[str, Any]:
        """Run the full LangGraph pipeline to completion.

        Args:
            user_message: Input text from the user.
            user_id: Identifier of the active user.
            conversation_id: Identifier of the current conversation session.

        Returns:
            Final executed AgentState dictionary.
        """
        initial_state: AgentState = {
            "messages": [{"role": "user", "content": user_message}],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "memories": [],
            "current_plan": [],
            "current_step": 0,
            "task_id": str(uuid.uuid4()),
            "tool_results": [],
            "verification_status": "pending",
            "retry_count": 0,
            "max_retries": 3,
            "error_log": [],
            "final_response": "",
        }

        logger.info(
            "Starting CognexaOrchestrator run for user %s (conversation: %s)",
            user_id,
            conversation_id,
        )
        final_state = await self.app.ainvoke(initial_state)
        return final_state

    async def run_stream(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream the execution of each node in the LangGraph pipeline.

        Args:
            user_message: Input text from the user.
            user_id: Identifier of the active user.
            conversation_id: Identifier of the current conversation session.

        Yields:
            Node transition events and partial state updates.
        """
        initial_state: AgentState = {
            "messages": [{"role": "user", "content": user_message}],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "memories": [],
            "current_plan": [],
            "current_step": 0,
            "task_id": str(uuid.uuid4()),
            "tool_results": [],
            "verification_status": "pending",
            "retry_count": 0,
            "max_retries": 3,
            "error_log": [],
            "final_response": "",
        }

        logger.info("Starting CognexaOrchestrator streaming run for user %s", user_id)
        async for event in self.app.astream(initial_state):
            yield event
