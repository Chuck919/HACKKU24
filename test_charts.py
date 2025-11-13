"""
Test script to verify chart generation works
"""
from main import generate_market_charts

print("Testing chart generation...")
print("=" * 50)

charts = generate_market_charts()

print("\n" + "=" * 50)
print(f"Generated {len(charts)} charts:")
for name in charts.keys():
    print(f"  ✓ {name}")
    
print("\nChart data preview (first 50 chars):")
for name, data in charts.items():
    print(f"  {name}: {data[:50]}...")

print("\n✓ Chart generation test successful!")
