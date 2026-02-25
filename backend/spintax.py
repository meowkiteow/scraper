"""
Spintax parser — resolves {option1|option2|option3} syntax.
Supports nested spintax.
"""

import re
import random


def render(text: str) -> str:
    """
    Resolve all spintax in text, returning one random variant.
    
    Examples:
        render("{Hi|Hey|Hello} {{first_name}}")
        → "Hey {{first_name}}"
        
        render("{I {really|truly} love|I enjoy} your {product|service}")
        → "I truly love your service"
    """
    if not text:
        return text

    max_iterations = 10  # Safety limit for nested spintax
    for _ in range(max_iterations):
        # Find innermost spintax blocks (no nested braces inside)
        match = re.search(r'\{([^{}]+)\}', text)
        if not match:
            break

        full_match = match.group(0)
        inner = match.group(1)

        # Only process if it contains a pipe (otherwise it's a template variable like {{name}})
        if '|' in inner:
            options = inner.split('|')
            replacement = random.choice(options).strip()
            text = text[:match.start()] + replacement + text[match.end():]
        else:
            # Not spintax — skip by replacing temporarily
            text = text[:match.start()] + f"__BRACE__{inner}__BRACE__" + text[match.end():]

    # Restore any non-spintax braces
    text = text.replace("__BRACE__", "{").replace("__BRACE__", "}")
    # Fix double-replacement
    text = re.sub(r'__BRACE__', '{', text, count=0)

    return text


def count_variants(text: str) -> int:
    """
    Count the total number of possible spintax combinations.
    """
    if not text:
        return 1

    total = 1
    for match in re.finditer(r'\{([^{}]+)\}', text):
        inner = match.group(1)
        if '|' in inner:
            total *= len(inner.split('|'))

    return total


def preview_all(text: str, max_previews: int = 5) -> list:
    """Generate multiple random variants for preview."""
    return [render(text) for _ in range(max_previews)]
