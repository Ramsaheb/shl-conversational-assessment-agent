"""Conversation state extraction from message history."""

import re
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Seniority keywords
SENIORITY_KEYWORDS = {
    "junior": ["junior", "entry-level", "entry level", "graduate", "intern", "apprentice", "fresher", "trainee"],
    "mid-level": ["mid-level", "mid level", "intermediate", "experienced", "3-5 years", "2-4 years"],
    "senior": ["senior", "lead", "principal", "staff", "8+ years", "10+ years", "expert"],
    "manager": ["manager", "director", "head of", "vp", "vice president", "executive", "c-level", "supervisor"],
}

# Assessment type indicators
TYPE_INDICATORS = {
    "cognitive": ["cognitive", "reasoning", "aptitude", "ability", "numerical", "verbal", "logical",
                  "deductive", "inductive", "mental ability", "IQ", "problem solving", "analytical"],
    "personality": ["personality", "behavioral", "behaviour", "OPQ", "motivation", "cultural fit",
                    "work style", "interpersonal", "emotional intelligence", "temperament"],
    "skills": ["coding", "programming", "technical", "software", "developer", "IT", ".NET",
               "Java", "Python", "JavaScript", "SQL", "business skills", "typing", "Excel"],
    "behavioral": ["situational judgment", "SJT", "judgment test", "scenarios", "simulation",
                    "call center", "customer service"],
}


def extract_conversation_state(messages: list) -> dict:
    """Extract structured state from conversation history.

    Analyzes all messages to build a comprehensive understanding of
    what the user is looking for.

    Args:
        messages: List of ChatMessage objects.

    Returns:
        Dict with extracted state fields.
    """
    state = {
        "role": None,
        "seniority": None,
        "skills": [],
        "needs_cognitive": False,
        "needs_personality": False,
        "needs_technical": False,
        "needs_behavioral": False,
        "industry": None,
        "assessment_types_mentioned": [],
        "specific_assessments_mentioned": [],
        "raw_requirements": [],
    }

    # Combine all user messages for analysis
    user_text = " ".join(
        msg.content for msg in messages if msg.role == "user"
    ).lower()

    # Extract role/job title
    role_patterns = [
        r"(?:hiring|recruit|assess|evaluating|looking for|need.+?for)\s+(?:a\s+)?(.+?)(?:\s+(?:role|position|candidate|developer|engineer|manager|analyst|specialist))",
        r"(?:for\s+(?:a|an)\s+)(.+?)(?:\s+(?:role|position|job))",
        r"(?:role|position|job)\s*(?:is|:)\s*(.+?)(?:\.|,|$)",
    ]
    for pattern in role_patterns:
        match = re.search(pattern, user_text)
        if match:
            state["role"] = match.group(1).strip().title()
            break

    # Fallback: look for common role keywords
    if not state["role"]:
        role_keywords = [
            "developer", "engineer", "manager", "analyst", "designer",
            "architect", "scientist", "administrator", "consultant",
            "coordinator", "specialist", "assistant", "supervisor",
            "director", "executive", "agent", "representative", "cashier",
            "accountant", "auditor", "bookkeeper", "teller",
        ]
        for keyword in role_keywords:
            if keyword in user_text:
                # Get surrounding context
                idx = user_text.index(keyword)
                start = max(0, idx - 30)
                end = min(len(user_text), idx + len(keyword) + 20)
                context = user_text[start:end].strip()
                # Extract the role phrase
                words = context.split()
                for i, w in enumerate(words):
                    if keyword in w:
                        role_parts = words[max(0, i-2):i+1]
                        state["role"] = " ".join(role_parts).strip().title()
                        break
                if state["role"]:
                    break

    # Extract seniority
    for level, keywords in SENIORITY_KEYWORDS.items():
        if any(kw in user_text for kw in keywords):
            state["seniority"] = level
            break

    # Extract assessment type needs
    for atype, indicators in TYPE_INDICATORS.items():
        if any(ind in user_text for ind in indicators):
            state[f"needs_{atype if atype != 'cognitive' else 'cognitive'}"] = True
            if atype not in state["assessment_types_mentioned"]:
                state["assessment_types_mentioned"].append(atype)

    # Extract specific skills mentioned
    skill_keywords = [
        "java", "python", "javascript", "c++", "c#", ".net", "sql", "react",
        "angular", "node.js", "aws", "azure", "docker", "kubernetes",
        "leadership", "communication", "teamwork", "problem-solving",
        "stakeholder management", "project management", "agile", "scrum",
        "data analysis", "machine learning", "customer service",
        "sales", "negotiation", "presentation", "excel", "word",
    ]
    for skill in skill_keywords:
        if skill in user_text:
            state["skills"].append(skill)

    # Extract raw requirements (recent user messages)
    for msg in messages:
        if msg.role == "user":
            state["raw_requirements"].append(msg.content)

    # Check for specific assessment mentions
    assessment_names = [
        "opq", "opq32", "verify", "sjt", "motivational questionnaire",
        "coding simulation", "360", "jfa", "video interview",
        "mechanical comprehension", "checking test",
    ]
    for name in assessment_names:
        if name in user_text:
            state["specific_assessments_mentioned"].append(name)

    logger.info("Extracted state: role=%s, seniority=%s, skills=%d",
                state["role"], state["seniority"], len(state["skills"]))

    return state


def is_state_sufficient_for_recommendation(state: dict) -> bool:
    """Check if we have enough context to make recommendations.

    We need at least a role OR specific skills OR assessment type preference.

    Args:
        state: Extracted conversation state.

    Returns:
        True if we have enough info to recommend.
    """
    has_role = bool(state.get("role"))
    has_skills = len(state.get("skills", [])) >= 1
    has_type_preference = any([
        state.get("needs_cognitive"),
        state.get("needs_personality"),
        state.get("needs_technical"),
        state.get("needs_behavioral"),
    ])
    has_specific = len(state.get("specific_assessments_mentioned", [])) > 0

    # Need at least one strong signal
    return has_role or has_skills or has_type_preference or has_specific


def build_search_query(state: dict) -> str:
    """Build a search query string from conversation state.

    Args:
        state: Extracted conversation state.

    Returns:
        Search query string for retrieval.
    """
    parts = []

    if state.get("role"):
        parts.append(state["role"])

    if state.get("seniority"):
        parts.append(state["seniority"])

    if state.get("skills"):
        parts.extend(state["skills"][:5])  # Limit to top 5 skills

    # Add type preferences
    type_map = {
        "needs_cognitive": "cognitive reasoning aptitude",
        "needs_personality": "personality behavioral workplace",
        "needs_technical": "technical coding programming skills",
        "needs_behavioral": "situational judgment behavioral",
    }
    for key, terms in type_map.items():
        if state.get(key):
            parts.append(terms)

    if not parts and state.get("raw_requirements"):
        # Fallback to latest user message
        parts.append(state["raw_requirements"][-1])

    return " ".join(parts)
