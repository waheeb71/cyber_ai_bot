"""
Formatting utilities for the Telegram bot
"""

import re
from telegram.constants import ParseMode

def format_code_blocks(text: str) -> str:
    """Format code blocks with proper syntax highlighting"""
    # Replace triple backticks with single backticks for inline code
    text = re.sub(r'```(\w+)\n(.*?)```', r'`\2`', text, flags=re.DOTALL)
    
    # Add proper spacing around code blocks
    text = re.sub(r'(?<!`)`([^`]+)`(?!`)', r' `\1` ', text)
    
    return text.strip()

def format_mixed_text(text: str) -> str:
    """Format mixed text (Arabic/English) for better readability"""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Format code blocks
    text = format_code_blocks(text)
    
    # Handle lists and bullets
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        # Format bullet points
        if line.strip().startswith(('•', '-', '*', '[')):
            line = '• ' + line.strip().lstrip('•-*[] ')
        
        # Clean up spacing around punctuation
        line = re.sub(r'\s*([،,.:؛])\s*', r'\1 ', line)
        line = re.sub(r'\s*\(\s*', ' (', line)
        line = re.sub(r'\s*\)\s*', ') ', line)
        
        formatted_lines.append(line.strip())
    
    # Join lines with proper spacing
    text = '\n'.join(formatted_lines)
    
    # Clean up multiple newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

def add_signature(text: str) -> str:
    """Add a signature to messages"""
    signature = "\n\n━━━━━━━━━━━━━━\n📢 قناة التلجرام: @SyberSc71\n👨‍💻 برمجة: @WAT4F"
    return text + signature

def format_message(text: str, add_sig: bool = True) -> tuple[str, dict]:
    """Format a message with all necessary formatting and return the text and parse mode"""
    # Apply all formatting
    text = format_mixed_text(text)
    
    if add_sig:
        text = add_signature(text)
    
    # Return formatted text and message options
    return text, {
        'parse_mode': ParseMode.MARKDOWN,
        'disable_web_page_preview': True
    }
