def format_text(text: str) -> str:
    """
    تنسيق النص بشكل منظم مع إضافة نقاط التعداد العربية ومعالجة الأكواد البرمجية
    """
    import re

    # تقسيم النص إلى فقرات
    paragraphs = text.split('\n\n')
    formatted_paragraphs = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            continue

        lines = paragraph.split('\n')
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # إزالة النجوم (عند وجودها) وجعل النص عريضًا
            if line.startswith('*') and line.endswith('*'):
                line = line[1:-1].strip()  # إزالة النجوم
                line = f"*{line}*"  # جعل النص عريض

            # التحقق إذا كان النص يحتوي على كود برمجي
            if line.startswith('```'):
                formatted_lines.append("\n" + line + "\n")
                continue

            # إزالة النجوم والعلامات
            line = line.replace('*', '')

            # هروب الأحرف الخاصة في Markdown
            special_chars = ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                line = line.replace(char, f'\\{char}')

            # تحويل النقاط إلى نقاط عربية
            if line.startswith(('-', '*', '•')):
                line = '• ' + line.lstrip('-*• ')

            # جعل العناوين عريضة
            if line.startswith('#'):
                line = line.replace('#', '')  # إزالة علامة الهاشتاج
                line = f"*{line.strip()}*"  # جعل الخط عريض

            formatted_lines.append(line)

        # إضافة ترقيم الأسطر للكود البرمجي
        if formatted_lines and formatted_lines[0].startswith('```'):
            code_lines = []
            for index, code_line in enumerate(formatted_lines[1:], start=1):
                code_lines.append(f"{index}: {code_line}")
            formatted_paragraph = '\n'.join([formatted_lines[0]] + code_lines)
        else:
            formatted_paragraph = '\n'.join(formatted_lines)

        formatted_paragraphs.append(formatted_paragraph)

    # دمج الفقرات مع مسافات إضافية
    final_text = '\n\n'.join(formatted_paragraphs)

    # إضافة التوقيع
    signature = "\n\n━━━━━━━━━━━━━━\n📢 قناة التلجرام: @SyberSc71\n👨‍💻 برمجة: @WAT4F"
    final_text += signature

    return final_text

# مثال على الاستخدام
if __name__ == '__main__':
    sample_text = """waheeb"""