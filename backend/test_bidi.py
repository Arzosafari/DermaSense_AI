"""
Test python-bidi for Persian text
"""
from bidi.algorithm import get_display

# Test Persian text
persian_text = "گزارش هوش مصنوعی غربالگری پوست SmartHealth"
print(f"Original: {persian_text}")
print(f"After bidi: {get_display(persian_text)}")

# Test mixed text
mixed_text = "مرحله بعدی توصیه شده"
print(f"\nOriginal: {mixed_text}")
print(f"After bidi: {get_display(mixed_text)}")

# Test with bullet point
bullet_text = "• این یک تست است"
print(f"\nOriginal: {bullet_text}")
print(f"After bidi: {get_display(bullet_text)}")
