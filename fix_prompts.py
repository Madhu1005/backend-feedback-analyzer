import re

# Read backup
with open('app/core/prompt_templates.py.backup', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all field names
content = content.replace('"primary_emotion"', '"emotion"')
content = content.replace('"secondary_emotions"', '"_removed_secondary_emotions"')
content = content.replace('"requires_urgent_attention"', '"urgency"')
content = content.replace('"summary"', '"_removed_summary"')
content = content.replace('"stress_level"', '"stress"')

# Fix category values  
content = content.replace('"category": "concern"', '"category": "workload"')
content = content.replace('"category": "other"', '"category": "general"')

# Add missing confidence category field where needed
content = re.sub(
    r'("confidence_scores": \{\s*"sentiment": [^,]+,\s*"emotion": [^,]+),(\s*"stress":)',
    r'\1, "category": 0.80,\2',
    content
)

# Write fixed content
with open('app/core/prompt_templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed prompt_templates.py')
