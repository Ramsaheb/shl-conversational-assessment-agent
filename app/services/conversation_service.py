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

# Turn limit: evaluator caps at 8 total messages (user + assistant).
# We must produce recommendations before hitting the cap.
MAX_TURNS = 8


def _load_prompt(filename: str) -> str:
    """Load a prompt template."""
    path = Path(__file__).parent.parent / "prompts" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _count_turns(messages: list[ChatMessage]) -> int:
    """Count total conversation turns (both user + assistant)."""
    return len(messages)


def _is_near_turn_limit(messages: list[ChatMessage]) -> bool:
    """Check if we're approaching the turn limit and must recommend now.

    The evaluator sends the next user message after our reply, so:
    - Current messages count = N
    - Our reply adds 1 (assistant) → N+1
    - User reply adds 1 → N+2
    - If N+2 >= MAX_TURNS, user won't be able to continue, so we MUST recommend now.
    """
    return len(messages) >= MAX_TURNS - 2  # i.e., >= 6 messages


def detect_intent(messages: list[ChatMessage], state: dict) -> str:
    """Detect the user's intent using deterministic Python logic.

    Priority order:
    1. Forced recommendation (near turn limit)
    2. Refusal (safety first)
    3. Comparison (explicit comparison request)
    4. Refinement (modifying previous recommendations)
    5. Recommendation (enough context to recommend)
    6. Greeting (first message is a greeting)
    7. Clarification (need more information)

    Args:
        messages: Full conversation history.
        state: Extracted conversation state.

    Returns:
        Intent string constant.
    """
    latest_msg = messages[-1].content.lower().strip()

    # 0. Check turn limit — force recommendation if near cap
    if _is_near_turn_limit(messages):
        # Still check for refusal even at the limit
        should_refuse, _, _ = detect_refusal(latest_msg)
        if should_refuse:
            return INTENT_REFUSAL
        # Force recommendation with whatever context we have
        logger.info("Near turn limit (%d messages), forcing recommendation", len(messages))
        return INTENT_RECOMMENDATION

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
            found = find_assessments_to_compare(latest_msg)
            if len(found) >= 2:
                return INTENT_COMPARISON
            if found:
                return INTENT_COMPARISON

    # 3. Check for refinement (only if there were previous recommendations)
    has_previous_recs = any(msg.role == "assistant" for msg in messages[:-1])
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
    # Be more aggressive about recommending if conversation is getting long
    if len(messages) >= 4:
        # After 2 user turns, bias toward recommending with best-effort
        if state.get("role") or state.get("skills") or any([
            state.get("needs_cognitive"), state.get("needs_personality"),
            state.get("needs_technical"), state.get("needs_behavioral"),
        ]):
            return INTENT_RECOMMENDATION

    if is_state_sufficient_for_recommendation(state, messages):
        return INTENT_RECOMMENDATION

    # 6. Default: clarification
    return INTENT_CLARIFICATION


def _parse_refinement_directives(text: str) -> dict:
    """Parse refinement instructions like add/remove assessment types."""
    text_lower = text.lower()
    directives = {
        "add_types": set(),
        "remove_types": set(),
        "exclude_keywords": set(),
    }

    type_map = {
        "personality": "P",
        "cognitive": "A",
        "ability": "A",
        "technical": "K",
        "skills": "K",
        "coding": "K",
        "behavioral": "B",
        "behavior": "B",
        "sjt": "B",
    }

    add_pattern = r"\b(add|include|also add|plus|along with)\b"
    remove_pattern = r"\b(remove|exclude|without|avoid|drop|no)\b"

    for label, code in type_map.items():
        if re.search(rf"{add_pattern}\s+{re.escape(label)}", text_lower):
            directives["add_types"].add(code)
        if re.search(rf"{remove_pattern}\s+{re.escape(label)}", text_lower):
            directives["remove_types"].add(code)

    # Exclude entry-level/junior tests if asked
    if re.search(r"\b(remove|exclude|without|avoid|drop|no)\b\s+(?:any\s+)?(entry[- ]level|junior|beginner|graduate|intern|trainee)", text_lower):
        directives["exclude_keywords"].update({
            "entry-level", "entry level", "junior", "beginner", "graduate", "intern", "trainee",
        })

    return directives


def _apply_refinement_to_state(state: dict, directives: dict) -> dict:
    """Update conversation state based on refinement directives."""
    type_flag_map = {
        "A": "needs_cognitive",
        "P": "needs_personality",
        "K": "needs_technical",
        "B": "needs_behavioral",
    }

    for code in directives.get("add_types", set()):
        flag = type_flag_map.get(code)
        if flag:
            state[flag] = True
        if code not in state.get("assessment_types_mentioned", []):
            state["assessment_types_mentioned"].append({
                "A": "cognitive",
                "P": "personality",
                "K": "skills",
                "B": "behavioral",
            }.get(code, code))

    for code in directives.get("remove_types", set()):
        flag = type_flag_map.get(code)
        if flag:
            state[flag] = False

    return state


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
    logger.info("Extracted state - role=%s, seniority=%s, turns=%d",
                state.get("role"), state.get("seniority"), len(messages))

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

    # If search query is empty (edge case near turn limit), use raw user messages
    if not search_query.strip():
        user_msgs = [m.content for m in messages if m.role == "user"]
        search_query = " ".join(user_msgs[-2:])  # Last 2 user messages

    logger.info("Search query: %s", search_query)

    recommendations, summary = await get_recommendations(
        search_query=search_query,
        state=state,
        top_k=min(7, 10),
    )

    if not recommendations:
        # Near turn limit? Try broader search
        if _is_near_turn_limit(messages):
            user_msgs = " ".join(m.content for m in messages if m.role == "user")
            recommendations, summary = await get_recommendations(
                search_query=user_msgs,
                state=state,
                top_k=7,
            )

        if not recommendations:
            return await _handle_clarification(messages, state)

    return ChatResponse(
        reply=summary,
        recommendations=recommendations,
        end_of_conversation=True,
    )


async def _handle_refinement(
    messages: list[ChatMessage], state: dict
) -> ChatResponse:
    """Handle refinement of previous recommendations."""
    latest_msg = messages[-1].content
    directives = _parse_refinement_directives(latest_msg)
    state = _apply_refinement_to_state(state, directives)
    search_query = build_search_query(state)

    recommendations, summary = await get_recommendations(
        search_query=search_query,
        state=state,
        top_k=7,
        exclude_keywords=sorted(directives.get("exclude_keywords", set())),
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
