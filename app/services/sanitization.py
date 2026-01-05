"""
Input Sanitization and Prompt Injection Detection
=================================================
Security utilities for detecting and handling potential prompt injection attacks.
"""

import re
from typing import List, Tuple


# =============================================================================
# Prompt Injection Detection Patterns
# =============================================================================

# Regex patterns that may indicate prompt injection attempts
SUSPICIOUS_PATTERNS: List[str] = [
    r"ignore\s+(previous|above|all)\s+instructions?",
    r"disregard\s+(previous|above|all)",
    r"forget\s+(everything|previous|above)",
    r"you\s+are\s+now",
    r"new\s+instructions?",
    r"system\s*:\s*",
    r"<\s*script",
    r"javascript\s*:",
    r"\{\{.*\}\}",  # Template injection
    r"\$\{.*\}",    # Variable injection
]

# Pre-compile patterns for better performance
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


def sanitize_input(text: str) -> Tuple[str, bool]:
    """
    Sanitize user input and detect potential prompt injection attacks.
    
    Performs the following checks and transformations:
    1. Checks for suspicious patterns that may indicate prompt injection
    2. Removes non-printable control characters (except newlines/tabs)
    3. Normalizes excessive whitespace
    
    Args:
        text: Raw user input string
        
    Returns:
        Tuple of (sanitized_text, is_suspicious)
        - sanitized_text: Cleaned input string
        - is_suspicious: True if prompt injection patterns were detected
    """
    # Check for suspicious patterns
    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            return text, True
    
    # Remove non-printable control characters (preserve newlines and tabs)
    sanitized = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    
    # Collapse excessive whitespace (10+ consecutive spaces)
    sanitized = re.sub(r'\s{10,}', ' ', sanitized)
    
    return sanitized, False
