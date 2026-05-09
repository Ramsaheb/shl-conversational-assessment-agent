
"""Conversation state extraction from message history."""

import re
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Seniority keywords
SENIORITY_KEYWORDS = {
    "junior": ["junior", "entry-level", "entry level", "graduate", "intern", "apprentice", "fresher", "trainee",
               "0-1 years", "1 year", "0 years", "new grad"],
    "mid-level": ["mid-level", "mid level", "intermediate", "experienced",
                  "2-4 years", "3-5 years", "2 years", "3 years", "4 years", "5 years",
                  "4 year", "5 year", "few years"],
    "senior": ["senior", "lead", "principal", "staff",
               "6-8 years", "8+ years", "10+ years", "6 years", "7 years", "8 years",
               "9 years", "10 years", "expert"],
    "manager": ["manager", "director", "head of", "vp", "vice president", "executive", "c-level", "supervisor"],
}

# Regex patterns for year-based seniority detection
YEAR_PATTERN = re.compile(r'\b(\d+)\s*(?:\+\s*)?(?:years?|yrs?)\b', re.IGNORECASE)


def _detect_seniority_from_years(text: str) -> str | None:
    """Detect seniority level from year mentions in text.

    Examples: "around 4 years", "4+ yrs", "about 3 years experience"
    """
    match = YEAR_PATTERN.search(text)
    if match:
        years = int(match.group(1))
        if years <= 1:
            return "junior"
        elif years <= 5:
            return "mid-level"
        elif years <= 9:
            return "senior"
        else:
            return "manager"
    return None


# Assessment type indicators — only use EXPLICIT assessment type requests,
# NOT role-related words like "developer" or "Java"
TYPE_INDICATORS = {
    "cognitive": ["cognitive", "reasoning", "aptitude", "ability test", "numerical reasoning",
                  "verbal reasoning", "logical reasoning", "deductive", "inductive",
                  "mental ability", "iq test", "problem solving test", "analytical test"],
    "personality": ["personality", "personality test", "OPQ", "motivation questionnaire",
                    "cultural fit test", "work style assessment", "temperament",
                    "behavioral assessment", "personality assessment"],
    "skills": ["coding test", "coding assessment", "coding simulation", "programming test",
               "technical test", "technical assessment", "skills test", "skills assessment",
               "business skills test", "typing test", "excel test"],
    "behavioral": ["situational judgment", "SJT", "judgment test", "scenarios test",
                    "simulation assessment", "behavioral simulation"],
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

    # Combine all user messages for analysis, but for context like role/seniority,
    # we want to prioritize the most recent messages.
    user_messages_newest_first = [msg.content.lower() for msg in reversed(messages) if msg.role == "user"]
    full_user_text = " ".join(msg.content.lower() for msg in messages if msg.role == "user")

    # Extract role/job title (search from newest message to oldest)
    role_patterns = [
        r"(?:hiring|recruit|assess|evaluating|looking for|need.+?for)\s+(?:a\s+)?(.+?)(?:\s+(?:role|position|candidate|developer|engineer|manager|analyst|specialist))",
        r"(?:for\s+(?:a|an)\s+)(.+?)(?:\s+(?:role|position|job))",
        r"(?:role|position|job)\s*(?:is|:)\s*(.+?)(?:\.|,|$)",
        r"(?:hiring|recruiting)\s+(?:a\s+|an\s+)?(.+?)(?:\s+who|\s+with|\s+that|\.|,|$)",
    ]
    
    role_keywords = [
        "developer", "engineer", "manager", "analyst", "designer",
        "architect", "scientist", "administrator", "consultant",
        "coordinator", "specialist", "assistant", "supervisor",
        "director", "executive", "agent", "representative", "cashier",
        "accountant", "auditor", "bookkeeper", "teller", "clerk",
        "technician", "nurse", "teacher", "salesperson", "operator",
    ]

    for msg_text in user_messages_newest_first:
        if state["role"]:
            break
            
        for pattern in role_patterns:
            match = re.search(pattern, msg_text)
            if match:
                role_text = match.group(1).strip()
                role_text = re.sub(r'\b(i need|we need|looking for|hiring)\b', '', role_text).strip()
                if len(role_text) > 2:
                    state["role"] = role_text.title()
                    break
                    
        if not state["role"]:
            for keyword in role_keywords:
                if keyword in msg_text:
                    idx = msg_text.index(keyword)
                    start = max(0, idx - 30)
                    end = min(len(msg_text), idx + len(keyword) + 20)
                    context = msg_text[start:end].strip()
                    words = context.split()
                    for i, w in enumerate(words):
                        if keyword in w:
                            role_parts = words[max(0, i-2):i+1]
                            state["role"] = " ".join(role_parts).strip().title()
                            break
                    if state["role"]:
                        break

    # Check for job description text (search in full text is fine, usually only provided once)
    jd_patterns = [
        r"(?:job description|jd)\s*[:;]\s*(.+?)(?:$)",
        r"(?:here is|here's)\s+(?:a|the)\s+(?:text|job description|jd)\s*[:;]?\s*(.+?)(?:$)",
    ]
    for pattern in jd_patterns:
        match = re.search(pattern, full_user_text, re.DOTALL)
        if match:
            jd_text = match.group(1).strip()
            if not state["role"]:
                for keyword in ["developer", "engineer", "manager", "analyst", "designer",
                                "architect", "specialist", "coordinator", "administrator"]:
                    if keyword in jd_text:
                        idx = jd_text.index(keyword)
                        start = max(0, idx - 20)
                        context_words = jd_text[start:idx + len(keyword) + 10].split()
                        for i, w in enumerate(context_words):
                            if keyword in w:
                                state["role"] = " ".join(context_words[max(0, i-2):i+1]).strip().title()
                                break
                        if state["role"]:
                            break

    # Extract seniority — search from newest to oldest
    for msg_text in user_messages_newest_first:
        if state["seniority"]:
            break
        for level, keywords in SENIORITY_KEYWORDS.items():
            if any(kw in msg_text for kw in keywords):
                state["seniority"] = level
                break
        
        if not state["seniority"]:
            year_seniority = _detect_seniority_from_years(msg_text)
            if year_seniority:
                state["seniority"] = year_seniority

    user_text = full_user_text

    # Extract assessment type needs (only from EXPLICIT requests, not role words)
    for atype, indicators in TYPE_INDICATORS.items():
        if any(ind.lower() in user_text for ind in indicators):
            if atype == "cognitive":
                state["needs_cognitive"] = True
            elif atype == "personality":
                state["needs_personality"] = True
            elif atype == "skills":
                state["needs_technical"] = True
            elif atype == "behavioral":
                state["needs_behavioral"] = True
            if atype not in state["assessment_types_mentioned"]:
                state["assessment_types_mentioned"].append(atype)

    # Extract specific skills mentioned. Prefer the latest user message to avoid
    # carrying over skills from a previous topic.
    skill_keywords = [
        "java", "python", "javascript", "c++", "c#", ".net", "sql", "react",
        "angular", "node.js", "aws", "azure", "docker", "kubernetes",
        "leadership", "communication", "teamwork", "problem-solving",
        "stakeholder management", "project management", "agile", "scrum",
        "data analysis", "machine learning", "customer service",
        "sales", "negotiation", "presentation", "excel", "word",
        "html", "css", "php", "ruby", "swift", "kotlin", "spring",
        "django", "flask", "typescript", "golang", "rust",
    ]
    latest_skills = []
    if user_messages_newest_first:
        latest_text = user_messages_newest_first[0]
        for skill in skill_keywords:
            if skill in latest_text:
                latest_skills.append(skill)

    if latest_skills:
        # Preserve order and remove duplicates
        state["skills"] = list(dict.fromkeys(latest_skills))
    else:
        for skill in skill_keywords:
            # Look only at the 2 most recent user messages to avoid carrying over old skills
            for msg_text in user_messages_newest_first[:2]:
                if skill in msg_text and skill not in state["skills"]:
                    state["skills"].append(skill)
                    break

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

    logger.info("Extracted state: role=%s, seniority=%s, skills=%d, types=%s",
                state["role"], state["seniority"], len(state["skills"]),
                state["assessment_types_mentioned"])

    return state


def is_state_sufficient_for_recommendation(state: dict, messages: list = None) -> bool:
    """Check if we have enough context to make recommendations.

    We need at least a role or skills to make a meaningful recommendation.
    We're intentionally more permissive than before to avoid asking
    too many clarifying questions.

    Args:
        state: Extracted conversation state.
        messages: Conversation history to check length.

    Returns:
        True if we have enough info to recommend.
    """
    has_role = bool(state.get("role"))
    has_seniority = bool(state.get("seniority"))
    has_skills = len(state.get("skills", [])) > 0
    has_type_preference = any([
        state.get("needs_cognitive"),
        state.get("needs_personality"),
        state.get("needs_technical"),
        state.get("needs_behavioral"),
    ])
    has_specific = len(state.get("specific_assessments_mentioned", [])) > 0

    # Specific assessment mentioned — recommend immediately
    if has_specific:
        return True

    # If conversation is long (4+ messages), be more permissive
    if messages and len(messages) >= 4:
        return has_role or has_skills or has_type_preference

    # Standard: need role + some context
    if has_role and (has_seniority or has_type_preference or has_skills):
        return True

    # Role + any skills mentioned
    if has_role and has_skills:
        return True

    return False


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
        parts.extend(state["skills"][:5])

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
