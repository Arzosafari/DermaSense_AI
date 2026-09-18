"""
Test arabic-reshaper for Persian text
"""
import arabic_reshaper

# Test Persian text
persian_text = "گزارش هوش مصنوعی غربالگری پوست SmartHealth"
print(f"Original: {persian_text}")
reshaped = arabic_reshaper.reshape(persian_text)
print(f"After reshaper: {reshaped}")

# Test mixed text
mixed_text = "مرحله بعدی توصیه شده"
print(f"\nOriginal: {mixed_text}")
reshaped2 = arabic_reshaper.reshape(mixed_text)
print(f"After reshaper: {reshaped2}")

# Test with bullet point
bullet_text = "• این یک تست است"
print(f"\nOriginal: {bullet_text}")
reshaped3 = arabic_reshaper.reshape(bullet_text)
print(f"After reshaper: {reshaped3}")
