"""Main conversation orchestration service.

Implements the deterministic decision layer:
  User Messages → State Extraction → Intent Analysis → Decision → Response
"""

import re
from pathlib import Path

from app.models.request_models import ChatMessage
from app.models.response_models import ChatResponse, Recommendation
from app.utils.conversation_parser import (
    extract_conversation_state,
    is_state_sufficient_for_recommendation,
    build_search_query,
)
from app.services.refusal_service import detect_refusal
from app.services.recommendation_service import get_recommendations
from app.services.comparison_service import compare_assessments, find_assessments_to_compare
from app.services.groq_service import generate_response
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Intent types
INTENT_CLARIFICATION = "clarification"
INTENT_RECOMMENDATION = "recommendation"
INTENT_COMPARISON = "comparison"
INTENT_REFINEMENT = "refinement"
INTENT_REFUSAL = "refusal"
INTENT_GREETING = "greeting"


def _load_prompt(filename: str) -> str:
    """Load a prompt template."""
    path = Path(__file__).parent.parent / "prompts" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def detect_intent(messages: list[ChatMessage], state: dict) -> str:
    """Detect the user's intent using deterministic Python logic.

    Priority order:
    1. Refusal (safety first)
    2. Comparison (explicit comparison request)
    3. Refinement (modifying previous recommendations)
    4. Recommendation (enough context to recommend)
    5. Greeting (first message is a greeting)
    6. Clarification (need more information)

    Args:
        messages: Full conversation history.
        state: Extracted conversation state.

    Returns:
        Intent string constant.
    """
    latest_msg = messages[-1].content.lower().strip()

    # 1. Check for refusal
    should_refuse, _, _ = detect_refusal(latest_msg)
    if should_refuse:
        return INTENT_REFUSAL

    # 2. Check for comparison
    comparison_keywords = [
        "compare", "comparison", "difference between", "differ from",
        "vs", "versus", "which is better", "how does .+ compare",
        "what.s the difference", "pros and cons",
    ]
    for kw in comparison_keywords:
        if re.search(kw, latest_msg):
            # Verify at least some assessments are mentioned
            found = find_assessments_to_compare(latest_msg)
            if len(found) >= 2:
                return INTENT_COMPARISON
            # Even with one, if comparison keyword is present
            if found:
                return INTENT_COMPARISON

    # 3. Check for refinement (only if there were previous recommendations)
    has_previous_recs = any(
        msg.role == "assistant" and any(
            indicator in msg.content.lower()
            for indicator in ["recommend", "suggest", "here are", "assessment"]
        )
        for msg in messages[:-1]
    )
    refinement_keywords = [
        "also add", "include", "remove", "replace", "instead",
        "actually", "what about", "add more", "fewer", "more",
        "personality too", "cognitive too", "technical too",
        "change", "update", "modify", "swap",
    ]
    if has_previous_recs and any(kw in latest_msg for kw in refinement_keywords):
        return INTENT_REFINEMENT

    # 4. Check for greeting
    greeting_patterns = [
        r"^(hi|hello|hey|greetings|good morning|good afternoon|good evening)[\s!.,]*$",
        r"^(hi|hello|hey)\s+(there|shl)[\s!.,]*$",
    ]
    if any(re.match(p, latest_msg) for p in greeting_patterns):
        return INTENT_GREETING

    # 5. Check if enough context for recommendation
    if is_state_sufficient_for_recommendation(state):
        return INTENT_RECOMMENDATION

    # 6. Default: clarification
    return INTENT_CLARIFICATION


async def process_conversation(messages: list[ChatMessage]) -> ChatResponse:
    """Process a conversation and generate a response.

    This is the main orchestration function that:
    1. Extracts conversation state
    2. Detects intent
    3. Routes to appropriate handler
    4. Returns formatted response

    Args:
        messages: Full conversation history.

    Returns:
        ChatResponse with reply, recommendations, and end_of_conversation flag.
    """
    # Step 1: Extract conversation state
    state = extract_conversation_state(messages)
    logger.info("Extracted state - Intent detection starting...")

    # Step 2: Detect intent
    intent = detect_intent(messages, state)
    logger.info("Detected intent: %s", intent)

    # Step 3: Route to handler
    if intent == INTENT_REFUSAL:
        return await _handle_refusal(messages)

    elif intent == INTENT_GREETING:
        return await _handle_greeting()

    elif intent == INTENT_COMPARISON:
        return await _handle_comparison(messages)

    elif intent == INTENT_REFINEMENT:
        return await _handle_refinement(messages, state)

    elif intent == INTENT_RECOMMENDATION:
        return await _handle_recommendation(messages, state)

    else:  # INTENT_CLARIFICATION
        return await _handle_clarification(messages, state)


async def _handle_refusal(messages: list[ChatMessage]) -> ChatResponse:
    """Handle off-topic or injection attempts."""
    latest_msg = messages[-1].content
    _, refusal_type, refusal_message = detect_refusal(latest_msg)

    return ChatResponse(
        reply=refusal_message or (
            "I can only help with SHL assessment recommendations. "
            "What role are you hiring for?"
        ),
        recommendations=[],
        end_of_conversation=False,
    )


async def _handle_greeting() -> ChatResponse:
    """Handle greeting messages."""
    return ChatResponse(
        reply=(
            "Hello! I'm the SHL Assessment Recommendation Assistant. "
            "I can help you find the right assessments for your hiring needs.\n\n"
            "To get started, could you tell me:\n"
            "- What role are you hiring for?\n"
            "- What level of seniority? (entry-level, mid-level, senior, manager)\n"
            "- Are there specific skills you need to evaluate?"
        ),
        recommendations=[],
        end_of_conversation=False,
    )


async def _handle_clarification(
    messages: list[ChatMessage], state: dict
) -> ChatResponse:
    """Ask clarifying questions based on what's missing."""
    system_prompt = _load_prompt("system_prompt.txt")
    clarification_prompt = _load_prompt("clarification_prompt.txt")

    # Determine what's missing
    missing = []
    if not state.get("role"):
        missing.append("the specific role or job title you're hiring for")
    if not state.get("seniority"):
        missing.append("the seniority level (entry-level, mid-level, senior, manager)")
    if not state.get("skills"):
        missing.append("key skills or competencies to evaluate")
    if not any([state.get("needs_cognitive"), state.get("needs_personality"),
                state.get("needs_technical"), state.get("needs_behavioral")]):
        missing.append("what type of assessment you need (cognitive, personality, technical, or behavioral)")

    latest_msg = messages[-1].content

    user_prompt = clarification_prompt.format(
        user_message=latest_msg,
        missing_info=", ".join(missing) if missing else "more specific details",
        current_state=_format_state(state),
    ) if clarification_prompt else (
        f"The user said: '{latest_msg}'\n\n"
        f"Current understanding: {_format_state(state)}\n\n"
        f"Still needed: {', '.join(missing)}\n\n"
        f"Ask 1-2 focused clarifying questions to help narrow down "
        f"SHL assessment recommendations. Be conversational and helpful."
    )

    reply = await generate_response(system_prompt, user_prompt, max_tokens=300)

    return ChatResponse(
        reply=reply,
        recommendations=[],
        end_of_conversation=False,
    )


async def _handle_recommendation(
    messages: list[ChatMessage], state: dict
) -> ChatResponse:
    """Generate assessment recommendations."""
    search_query = build_search_query(state)
    logger.info("Search query: %s", search_query)

    recommendations, summary = await get_recommendations(
        search_query=search_query,
        state=state,
        top_k=min(7, 10),  # Default to 7, max 10
    )

    if not recommendations:
        # Fallback to clarification
        return await _handle_clarification(messages, state)

    return ChatResponse(
        reply=summary,
        recommendations=recommendations,
        end_of_conversation=False,
    )


async def _handle_refinement(
    messages: list[ChatMessage], state: dict
) -> ChatResponse:
    """Handle refinement of previous recommendations."""
    # Re-extract state with full context (includes refinement request)
    search_query = build_search_query(state)

    # Add refinement context to query
    latest_msg = messages[-1].content.lower()
    search_query = f"{search_query} {latest_msg}"

    recommendations, summary = await get_recommendations(
        search_query=search_query,
        state=state,
        top_k=7,
    )

    if not recommendations:
        return ChatResponse(
            reply="I couldn't find additional assessments matching your refined criteria. Could you be more specific about what you'd like to change?",
            recommendations=[],
            end_of_conversation=False,
        )

    return ChatResponse(
        reply=f"I've updated the recommendations based on your feedback.\n\n{summary}",
        recommendations=recommendations,
        end_of_conversation=False,
    )


async def _handle_comparison(messages: list[ChatMessage]) -> ChatResponse:
    """Handle assessment comparison requests."""
    latest_msg = messages[-1].content
    comparison_text = await compare_assessments(latest_msg)

    return ChatResponse(
        reply=comparison_text,
        recommendations=[],
        end_of_conversation=False,
    )


def _format_state(state: dict) -> str:
    """Format state dict for LLM context."""
    parts = []
    if state.get("role"):
        parts.append(f"Role: {state['role']}")
    if state.get("seniority"):
        parts.append(f"Seniority: {state['seniority']}")
    if state.get("skills"):
        parts.append(f"Skills: {', '.join(state['skills'])}")
    if state.get("needs_cognitive"):
        parts.append("Needs: Cognitive assessments")
    if state.get("needs_personality"):
        parts.append("Needs: Personality assessments")
    if state.get("needs_technical"):
        parts.append("Needs: Technical skills assessments")
    if state.get("needs_behavioral"):
        parts.append("Needs: Behavioral assessments")
    return "; ".join(parts) if parts else "No specific details gathered yet"
