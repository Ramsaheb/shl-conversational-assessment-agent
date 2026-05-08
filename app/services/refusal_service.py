"""Refusal detection service for off-topic and injection attempts."""

import re
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Topics to refuse
REFUSAL_TOPICS = {
    "legal": [
        "legal advice", "lawsuit", "sue", "attorney", "lawyer",
        "court", "litigation", "legal rights", "employment law",
        "wrongful termination", "discrimination lawsuit",
    ],
    "salary": [
        "salary", "compensation", "pay range", "how much",
        "wage", "bonus", "stock options", "equity", "benefits package",
        "salary negotiation", "pay scale",
    ],
    "off_topic": [
        "recipe", "weather", "sports", "movie", "game",
        "homework", "write me a poem", "tell me a joke",
        "write code", "debug", "fix my code", "translate",
        "book recommendation", "travel advice", "medical advice",
        "health advice", "investment advice", "stock market",
        "cryptocurrency", "bitcoin", "dating advice",
        "python script", "write a script", "write me a script"
    ],
}

# Prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+(?:a|an)",
    r"new\s+instructions?\s*:",
    r"system\s*prompt",
    r"reveal\s+(your\s+)?instructions",
    r"show\s+(your\s+)?system\s+prompt",
    r"what\s+are\s+your\s+instructions",
    r"act\s+as\s+(?:a|an)",
    r"pretend\s+(?:to\s+be|you\s+are)",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode",
    r"\bdo\s+anything\s+now\b",
]

REFUSAL_MESSAGES = {
    "legal": "I'm sorry, but I can't provide legal advice. I'm specifically designed to help you find the right SHL assessments for your hiring needs. How can I help you with assessment selection?",
    "salary": "I'm not able to provide salary or compensation guidance. My expertise is in helping you select the right SHL assessments. Would you like help finding assessments for a specific role?",
    "off_topic": "That's outside my area of expertise. I'm an SHL assessment recommendation assistant — I can help you find the right assessments for evaluating candidates. What role are you hiring for?",
    "injection": "I can only help with SHL assessment recommendations. Could you tell me about the role you're looking to fill so I can suggest appropriate assessments?",
}


def detect_refusal(text: str) -> tuple[bool, str | None, str | None]:
    """Detect if a message should be refused.

    Args:
        text: User message text.

    Returns:
        Tuple of (should_refuse, refusal_type, refusal_message).
    """
    text_lower = text.lower().strip()

    # Check prompt injection first (highest priority)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            logger.warning("Prompt injection attempt detected: %s", text[:50])
            return True, "injection", REFUSAL_MESSAGES["injection"]

    # Check refusal topics
    for topic, keywords in REFUSAL_TOPICS.items():
        # Require keyword match but also check it's not SHL-related
        for keyword in keywords:
            if keyword in text_lower:
                # Don't refuse if the message also mentions assessments/hiring
                shl_context = any(
                    term in text_lower
                    for term in ["assessment", "test", "evaluate", "hiring",
                                 "recruit", "shl", "candidate"]
                )
                if not shl_context:
                    logger.info("Refusing %s topic: %s", topic, text[:50])
                    return True, topic, REFUSAL_MESSAGES[topic]

    return False, None, None
