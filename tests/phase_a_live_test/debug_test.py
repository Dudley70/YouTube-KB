#!/usr/bin/env python3
"""Quick debug test to see actual LLM error"""

import os
import sys
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from youtube_processor.llm.transcript_analyzer import TranscriptAnalyzer

# Test with minimal candidate
api_key = os.environ.get('ANTHROPIC_API_KEY')
print(f"API key present: {bool(api_key)}")
print(f"API key length: {len(api_key) if api_key else 0}")

analyzer = TranscriptAnalyzer(api_key=api_key)

# Single test candidate
candidates = [{
    'id': 'test-001',
    'text': 'This is a test technique for validation purposes.',
    'score': 1.0
}]

print("\nCalling analyze_units with 1 candidate...")
result = analyzer.analyze_units(
    candidates=candidates,
    video_id='test',
    video_title='Debug Test'
)

print(f"\nResult: {result.knowledge_units[0]}")
print(f"Name: {result.knowledge_units[0].name}")
print(f"Type: {result.knowledge_units[0].type}")
print(f"Confidence: {result.knowledge_units[0].confidence}")
