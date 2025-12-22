"""
Formatting utilities for the Telegram bot
"""

import re
import html

def format_message(text: str) -> str:
  
    code_blocks = []
    def _sub_code_block(match):
        code = html.escape(match.group(2))
        lang = match.group(1)
        if lang:
            tag = f'<pre><code class="language-{lang}">{code}</code></pre>'
        else:
            tag = f'<pre><code>{code}</code></pre>'
        code_blocks.append(tag)
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"

    # Handle ```code``` blocks
    text = re.sub(r'```(\w*)\n(.*?)\n```', _sub_code_block, text, flags=re.DOTALL)

    def _sub_inline_code(match):
        code = html.escape(match.group(1))
        tag = f'<code>{code}</code>'
        code_blocks.append(tag)
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"

    # Handle `code`
    text = re.sub(r'`([^`]+)`', _sub_inline_code, text)

    # Now do other formatting on the rest of the text
    
    # Escape HTML to prevent special characters from breaking the layout or being hidden
    text = html.escape(text)

    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text, flags=re.DOTALL)
    # Italic
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text, flags=re.DOTALL)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text, flags=re.DOTALL)

    # Handle lists
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line.startswith(('* ', '- ')):
            lines[i] = '• ' + stripped_line[2:]
        else:
            lines[i] = line # Keep original line if not a list item
    text = '\n'.join(lines)

    # Restore code blocks
    for i, code_block in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{i}__", code_block)

    return text.strip()


def add_signature(text: str) -> str:
    """Add a signature to messages"""
    signature = "\n\n━━━━━━━━━━━━━━\n📢 قناة التلجرام: @SyberSc71\n👨‍💻 برمجة: @WAT4F"
    return text + signature
