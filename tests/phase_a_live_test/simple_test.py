#!/usr/bin/env python3
"""
Simple Phase A Test - Actually works with correct imports
Tests the two-step pipeline: DeterministicExtractor → LLMNormalizer
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from youtube_processor.core.transcript_extractor import TranscriptExtractor
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor
from youtube_processor.llm.transcript_analyzer import TranscriptAnalyzer


def main():
    """Simple test of Phase A pipeline."""
    
    print("=" * 80)
    print("SIMPLE PHASE A TEST")
    print("=" * 80)
    print()
    
    # Use a known video with transcript
    video_id = "aA9KP7QIQvM"
    video_title = "Test Video"
    
    print(f"Testing with video: {video_id}")
    print()
    
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ERROR: Set ANTHROPIC_API_KEY environment variable")
        print("   Example: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    
    # Step 1: Get transcript
    print("Step 1: Extracting transcript...")
    try:
        extractor = TranscriptExtractor()
        transcript = extractor.extract(video_id)
        word_count = len(transcript.split())
        print(f"✅ Got {word_count:,} words")
        print()
    except Exception as e:
        print(f"❌ Failed: {e}")
        sys.exit(1)
    
    # Step 2: Run deterministic extraction
    print("Step 2: Running deterministic extraction...")
    try:
        det_extractor = DeterministicExtractor()
        result = det_extractor.extract(
            video_id=video_id,
            transcript=transcript
        )
        
        # Result is a dict with 'units' key
        candidates = result.get('units', [])
        
        print(f"✅ Extracted {len(candidates)} candidates")
        if candidates:
            sample = candidates[0]
            print(f"   Sample: {sample.get('text', '')[:60]}...")
        print()
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 3: Run Phase A normalization
    print("Step 3: Running Phase A LLM normalization...")
    print("   (This will take 30-60 seconds...)")
    try:
        analyzer = TranscriptAnalyzer(api_key=api_key)
        
        # Test with just first 5 candidates for speed
        test_candidates = candidates[:5]
        print(f"   Testing with {len(test_candidates)} candidates")
        
        analysis = analyzer.analyze_units(
            candidates=test_candidates,
            video_id=video_id,
            video_title=video_title
        )
        
        units = analysis.knowledge_units
        print(f"✅ Got {len(units)} knowledge units")
        print()
        
        # Show results
        print("Results:")
        for i, unit in enumerate(units, 1):
            print(f"{i}. [{unit.type}] {unit.name}")
            if unit.name == "(unclear)":
                print(f"   ⚠️  FALLBACK MODE - LLM call failed")
        print()
        
        # Check if fallback was used
        fallback_count = sum(1 for u in units if u.name == "(unclear)")
        if fallback_count == len(units):
            print("❌ ALL UNITS IN FALLBACK MODE")
            print("   This means the LLM normalization failed.")
            print("   Possible causes:")
            print("   - Invalid API key")
            print("   - Rate limit hit")
            print("   - Network timeout")
            print("   - LLM returned invalid JSON")
            print()
            print("   To debug, enable logging:")
            print("   import logging")
            print("   logging.basicConfig(level=logging.DEBUG)")
        elif fallback_count > 0:
            print(f"⚠️  {fallback_count}/{len(units)} units used fallback")
        else:
            print("✅ SUCCESS - All units properly categorized!")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
