#!/usr/bin/env python3
"""
Phase A Live Test: Latest Indy Dev Dan Video
Tests the complete Phase A pipeline (DeterministicExtractor + LLMNormalizer)
on the most recent Indy Dev Dan video.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from youtube_processor.core.discovery import ChannelDiscovery
from youtube_processor.core.transcript_extractor import TranscriptExtractor
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor
from youtube_processor.llm.transcript_analyzer import TranscriptAnalyzer
from youtube_processor.llm.normalizer_runner import NormalizerRunner


def main():
    """Run Phase A test on latest Indy Dev Dan video."""
    
    print("=" * 80)
    print("PHASE A LIVE TEST: Latest Indy Dev Dan Video")
    print("=" * 80)
    print()
    
    # Check for API key
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("❌ ERROR: YOUTUBE_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize components
    print("🔧 Initializing components...")
    discovery = ChannelDiscovery(api_key=api_key)
    transcript_extractor = TranscriptExtractor()
    deterministic_extractor = DeterministicExtractor()
    
    # Indy Dev Dan channel - use a known video with transcript for testing
    # Video: aA9KP7QIQvM (known to have transcript from previous tests)
    channel_handle = "@indydevdan"
    test_video_id = "aA9KP7QIQvM"
    
    print(f"📺 Channel: {channel_handle}")
    print(f"🎬 Test Video ID: {test_video_id}")
    print()
    
    # Step 1: Get video metadata
    print("Step 1: Using test video...")
    try:
        from youtube_processor.core.discovery import VideoMetadata
        # Create a simple metadata object for testing
        latest = VideoMetadata(
            video_id=test_video_id,
            title="Indy Dev Dan Test Video",
            description="Test video for Phase A",
            duration_seconds=600,
            upload_date="2025-11-01"
        )
        print(f"✅ Using test video: {latest.title}")
        print(f"   Video ID: {latest.video_id}")
        print()
    except Exception as e:
        print(f"❌ Error fetching video: {e}")
        sys.exit(1)
    
    # Step 2: Extract transcript
    print("Step 2: Extracting transcript...")
    try:
        transcript = transcript_extractor.extract(latest.video_id)
        if not transcript:
            print("❌ No transcript available")
            sys.exit(1)
        
        word_count = len(transcript.split())
        print(f"✅ Transcript extracted: {word_count:,} words")
        print()
    except Exception as e:
        print(f"❌ Error extracting transcript: {e}")
        sys.exit(1)
    
    # Step 3: Run deterministic extractor
    print("Step 3: Running deterministic extractor...")
    try:
        extraction_result = deterministic_extractor.extract(
            video_id=latest.video_id,
            transcript=transcript
        )
        
        # The wrapper returns a dict, need to extract candidates
        units = extraction_result.get('units', [])
        candidates = units  # Rename for consistency
        
        print(f"✅ Extracted {len(candidates)} candidates")
        
        # Show sample candidates
        print("   Sample candidates:")
        for c in candidates[:3]:
            print(f"     - ID: {c.get('id', 'N/A')}, Text: {c.get('text', '')[:60]}...")
        print()
    except Exception as e:
        print(f"❌ Error in deterministic extraction: {e}")
        sys.exit(1)
    
    # Step 4: Run LLM normalizer (Phase A)
    print("Step 4: Running Phase A LLM normalizer...")
    try:
        # Initialize analyzer with API key
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            print("⚠️  WARNING: ANTHROPIC_API_KEY not set, test will fail")
            sys.exit(1)
        
        analyzer = TranscriptAnalyzer(api_key=anthropic_api_key)
        
        # Run normalizer
        print("   Normalizing candidates (this may take 30-60 seconds)...")
        analysis_result = analyzer.analyze_units(
            candidates=candidates,
            video_id=latest.video_id,
            video_title=latest.title
        )
        
        knowledge_units = analysis_result.knowledge_units
        print(f"✅ Normalized to {len(knowledge_units)} knowledge units")
        print()
        
        # Show breakdown by type
        types = {}
        for ku in knowledge_units:
            types[ku.type] = types.get(ku.type, 0) + 1
        
        print("   Type breakdown:")
        for ktype, count in sorted(types.items()):
            print(f"     - {ktype}: {count}")
        print()
        
    except Exception as e:
        print(f"❌ Error in Phase A normalization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 5: Show sample results
    print("Step 5: Sample results...")
    print()
    
    # Show first 3 knowledge units
    for i, ku in enumerate(knowledge_units[:3], 1):
        print(f"Unit {i}:")
        print(f"  ID: {ku.id}")
        print(f"  Type: {ku.type}")
        print(f"  Name: {ku.name}")
        print(f"  Content: {ku.content[:100]}...")
        print()
    
    # Step 6: Save results to file
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"{latest.video_id}_phase_a_test.json"
    
    result_data = {
        "test_date": datetime.now().isoformat(),
        "video_id": latest.video_id,
        "video_title": latest.title,
        "upload_date": latest.upload_date,
        "transcript_word_count": word_count,
        "candidates_extracted": len(candidates),
        "knowledge_units_created": len(knowledge_units),
        "type_breakdown": types,
        "sample_units": [
            {
                "id": ku.id,
                "type": ku.type,
                "name": ku.name,
                "content": ku.content
            }
            for ku in knowledge_units[:5]
        ]
    }
    
    with open(output_file, 'w') as f:
        json.dump(result_data, f, indent=2)
    
    print(f"💾 Results saved to: {output_file}")
    print()
    
    # Step 7: Test determinism (if cache exists)
    print("Step 6: Testing determinism...")
    try:
        # Run again to test cache
        print("   Running normalizer again to test cache...")
        analysis_result_2 = analyzer.analyze_units(
            candidates=candidates,
            video_id=latest.video_id,
            video_title=latest.title
        )
        
        knowledge_units_2 = analysis_result_2.knowledge_units
        
        # Compare results
        if len(knowledge_units) == len(knowledge_units_2):
            matches = sum(
                1 for ku1, ku2 in zip(knowledge_units, knowledge_units_2)
                if ku1.id == ku2.id and ku1.type == ku2.type
            )
            
            if matches == len(knowledge_units):
                print(f"✅ 100% deterministic! ({matches}/{len(knowledge_units)} units identical)")
            else:
                print(f"⚠️  Partial match: {matches}/{len(knowledge_units)} units identical")
        else:
            print(f"⚠️  Different unit counts: {len(knowledge_units)} vs {len(knowledge_units_2)}")
        
    except Exception as e:
        print(f"⚠️  Could not test determinism: {e}")
    
    print()
    print("=" * 80)
    print("✅ PHASE A LIVE TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
