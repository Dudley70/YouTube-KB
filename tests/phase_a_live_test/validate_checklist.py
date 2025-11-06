#!/usr/bin/env python3
"""
Phase A Validation Checklist
Systematically tests each component with findings logged
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def print_header(text):
    """Print section header"""
    print()
    print("=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_check(passed, message, details=None):
    """Print checklist item"""
    status = "✅" if passed else "❌"
    print(f"{status} {message}")
    if details:
        for line in details:
            print(f"   {line}")
    return passed


def main():
    """Run validation checklist"""
    
    print_header("PHASE A VALIDATION CHECKLIST")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    findings = []
    all_passed = True
    
    # ========================================================================
    # CHECKPOINT 1: Environment Setup
    # ========================================================================
    print_header("CHECKPOINT 1: Environment Setup")
    
    # Check 1.1: Python version
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    passed = sys.version_info >= (3, 8)
    all_passed &= print_check(
        passed,
        f"Python version: {py_version}",
        ["Requirement: Python 3.8+"] if not passed else None
    )
    findings.append(f"Python {py_version}: {'OK' if passed else 'TOO OLD'}")
    
    # Check 1.2: Anthropic API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    passed = api_key is not None and len(api_key) > 0
    all_passed &= print_check(
        passed,
        "Anthropic API key set",
        ["Set with: export ANTHROPIC_API_KEY='your-key'"] if not passed else None
    )
    findings.append(f"API key: {'SET ({len(api_key)} chars)' if passed else 'NOT SET'}")
    
    if not api_key:
        print("\n⚠️  Cannot continue without API key")
        print("   Set with: export ANTHROPIC_API_KEY='your-key'")
        return
    
    # Check 1.3: Working directory
    expected_dir = Path(__file__).parent.parent.parent
    passed = expected_dir.exists() and (expected_dir / "youtube_processor").exists()
    all_passed &= print_check(
        passed,
        f"Working directory: {expected_dir}",
        [] if passed else ["youtube_processor/ not found"]
    )
    findings.append(f"Working dir: {'OK' if passed else 'INVALID'}")
    
    # ========================================================================
    # CHECKPOINT 2: Module Imports
    # ========================================================================
    print_header("CHECKPOINT 2: Module Imports")
    
    # Check 2.1: TranscriptExtractor
    try:
        from youtube_processor.core.transcript_extractor import TranscriptExtractor
        print_check(True, "TranscriptExtractor import")
        findings.append("TranscriptExtractor: OK")
    except Exception as e:
        all_passed &= print_check(False, "TranscriptExtractor import", [str(e)])
        findings.append(f"TranscriptExtractor: FAILED - {e}")
        return
    
    # Check 2.2: DeterministicExtractor
    try:
        from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor
        print_check(True, "DeterministicExtractor import")
        findings.append("DeterministicExtractor: OK")
    except Exception as e:
        all_passed &= print_check(False, "DeterministicExtractor import", [str(e)])
        findings.append(f"DeterministicExtractor: FAILED - {e}")
        return
    
    # Check 2.3: TranscriptAnalyzer
    try:
        from youtube_processor.llm.transcript_analyzer import TranscriptAnalyzer
        print_check(True, "TranscriptAnalyzer import")
        findings.append("TranscriptAnalyzer: OK")
    except Exception as e:
        all_passed &= print_check(False, "TranscriptAnalyzer import", [str(e)])
        findings.append(f"TranscriptAnalyzer: FAILED - {e}")
        return
    
    # ========================================================================
    # CHECKPOINT 3: Transcript Extraction
    # ========================================================================
    print_header("CHECKPOINT 3: Transcript Extraction")
    
    video_id = "aA9KP7QIQvM"
    transcript = None
    
    # Check 3.1: Create extractor
    try:
        extractor = TranscriptExtractor()
        print_check(True, "TranscriptExtractor initialized")
        findings.append("TranscriptExtractor init: OK")
    except Exception as e:
        all_passed &= print_check(False, "TranscriptExtractor initialization", [str(e)])
        findings.append(f"TranscriptExtractor init: FAILED - {e}")
        return
    
    # Check 3.2: Extract transcript
    try:
        print(f"   Extracting video: {video_id} ...")
        transcript = extractor.extract(video_id)
        
        if not transcript:
            all_passed &= print_check(False, "Transcript extraction", ["No transcript returned"])
            findings.append("Transcript extraction: NO TRANSCRIPT")
            return
        
        word_count = len(transcript.split())
        passed = word_count > 100
        all_passed &= print_check(
            passed,
            f"Transcript extracted: {word_count:,} words",
            [] if passed else ["Too short - may be invalid"]
        )
        findings.append(f"Transcript: {word_count} words")
        
    except Exception as e:
        all_passed &= print_check(False, "Transcript extraction", [str(e)])
        findings.append(f"Transcript extraction: FAILED - {e}")
        return
    
    # ========================================================================
    # CHECKPOINT 4: Deterministic Extraction
    # ========================================================================
    print_header("CHECKPOINT 4: Deterministic Extraction")
    
    candidates = None
    
    # Check 4.1: Create extractor
    try:
        det_extractor = DeterministicExtractor()
        print_check(True, "DeterministicExtractor initialized")
        findings.append("DeterministicExtractor init: OK")
    except Exception as e:
        all_passed &= print_check(False, "DeterministicExtractor initialization", [str(e)])
        findings.append(f"DeterministicExtractor init: FAILED - {e}")
        return
    
    # Check 4.2: Extract candidates
    try:
        print(f"   Extracting from {len(transcript)} char transcript ...")
        result = det_extractor.extract(
            video_id=video_id,
            transcript=transcript
        )
        
        # Check 4.3: Result structure
        if not isinstance(result, dict):
            all_passed &= print_check(False, "Result type", [f"Expected dict, got {type(result)}"])
            findings.append(f"Result type: WRONG - {type(result)}")
            return
        
        print_check(True, "Result type: dict")
        
        # Check 4.4: Has 'units' key
        if 'units' not in result:
            all_passed &= print_check(False, "Result structure", [f"Missing 'units' key, has: {list(result.keys())}"])
            findings.append(f"Result structure: MISSING units key")
            return
        
        print_check(True, "Result has 'units' key")
        
        # Check 4.5: Units count
        candidates = result['units']
        passed = len(candidates) >= 10
        all_passed &= print_check(
            passed,
            f"Candidates extracted: {len(candidates)}",
            ["Expected 40-100, got fewer"] if not passed else None
        )
        findings.append(f"Candidates: {len(candidates)} units")
        
        # Check 4.6: Candidate structure
        if candidates:
            sample = candidates[0]
            required_keys = ['id', 'text']
            missing = [k for k in required_keys if k not in sample]
            
            if missing:
                all_passed &= print_check(False, "Candidate structure", [f"Missing keys: {missing}"])
                findings.append(f"Candidate structure: MISSING {missing}")
            else:
                print_check(True, f"Candidate structure valid")
                print(f"   Sample ID: {sample['id']}")
                print(f"   Sample text: {sample['text'][:60]}...")
                findings.append(f"Candidate structure: OK")
        
    except Exception as e:
        all_passed &= print_check(False, "Deterministic extraction", [str(e)])
        findings.append(f"Deterministic extraction: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========================================================================
    # CHECKPOINT 5: LLM Normalizer Setup
    # ========================================================================
    print_header("CHECKPOINT 5: LLM Normalizer Setup")
    
    # Check 5.1: Create analyzer
    try:
        analyzer = TranscriptAnalyzer(api_key=api_key)
        print_check(True, "TranscriptAnalyzer initialized")
        findings.append("TranscriptAnalyzer init: OK")
    except Exception as e:
        all_passed &= print_check(False, "TranscriptAnalyzer initialization", [str(e)])
        findings.append(f"TranscriptAnalyzer init: FAILED - {e}")
        return
    
    # Check 5.2: Verify analyzer has analyze_units method
    if not hasattr(analyzer, 'analyze_units'):
        all_passed &= print_check(False, "Analyzer API", ["Missing analyze_units method"])
        findings.append("Analyzer API: MISSING analyze_units")
        return
    
    print_check(True, "Analyzer has analyze_units method")
    findings.append("Analyzer API: OK")
    
    # ========================================================================
    # CHECKPOINT 6: LLM Normalization (Small Test)
    # ========================================================================
    print_header("CHECKPOINT 6: LLM Normalization (3 Candidates)")
    
    # Test with just 3 candidates for speed
    test_candidates = candidates[:3]
    
    print(f"   Testing with {len(test_candidates)} candidates")
    print(f"   This may take 20-30 seconds...")
    
    try:
        analysis = analyzer.analyze_units(
            candidates=test_candidates,
            video_id=video_id,
            video_title="Test Video"
        )
        
        print_check(True, "analyze_units completed")
        
        # Check 6.1: Result structure
        if not hasattr(analysis, 'knowledge_units'):
            all_passed &= print_check(False, "Result structure", ["Missing knowledge_units attribute"])
            findings.append("Result structure: MISSING knowledge_units")
            return
        
        print_check(True, "Result has knowledge_units")
        
        # Check 6.2: Units count matches
        units = analysis.knowledge_units
        passed = len(units) == len(test_candidates)
        all_passed &= print_check(
            passed,
            f"Unit count: {len(units)} (expected {len(test_candidates)})",
            ["Count mismatch - invariant violation"] if not passed else None
        )
        findings.append(f"Unit count: {len(units)}/{len(test_candidates)}")
        
        # Check 6.3: Unit structure
        if units:
            sample = units[0]
            required_attrs = ['id', 'type', 'name', 'content']
            missing = [a for a in required_attrs if not hasattr(sample, a)]
            
            if missing:
                all_passed &= print_check(False, "Unit structure", [f"Missing attributes: {missing}"])
                findings.append(f"Unit structure: MISSING {missing}")
            else:
                print_check(True, "Unit structure valid")
                findings.append("Unit structure: OK")
        
        # Check 6.4: Detect fallback mode
        fallback_count = sum(1 for u in units if u.name == "(unclear)")
        
        if fallback_count == len(units):
            all_passed &= print_check(
                False,
                "Normalization quality",
                [
                    "ALL units in fallback mode - LLM call failed",
                    "Possible causes:",
                    "  - Invalid API key",
                    "  - Rate limit hit",
                    "  - Network timeout",
                    "  - LLM returned invalid JSON"
                ]
            )
            findings.append(f"Quality: FALLBACK MODE ({fallback_count}/{len(units)})")
        elif fallback_count > 0:
            print_check(
                True,
                f"Normalization quality: Partial ({fallback_count}/{len(units)} fallback)",
                [f"Some units failed, others succeeded"]
            )
            findings.append(f"Quality: PARTIAL ({fallback_count}/{len(units)} fallback)")
        else:
            print_check(True, "Normalization quality: All units properly categorized")
            findings.append(f"Quality: SUCCESS (0 fallback)")
        
        # Check 6.5: Show sample results
        print()
        print("   Sample results:")
        for i, unit in enumerate(units, 1):
            print(f"   {i}. [{unit.type}] {unit.name}")
        
    except Exception as e:
        all_passed &= print_check(False, "LLM normalization", [str(e)])
        findings.append(f"LLM normalization: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========================================================================
    # CHECKPOINT 7: Determinism Test (Cache)
    # ========================================================================
    print_header("CHECKPOINT 7: Determinism Test")
    
    print("   Running normalization again to test cache...")
    
    try:
        analysis_2 = analyzer.analyze_units(
            candidates=test_candidates,
            video_id=video_id,
            video_title="Test Video"
        )
        
        units_2 = analysis_2.knowledge_units
        
        # Check 7.1: Same count
        if len(units_2) != len(units):
            all_passed &= print_check(
                False,
                "Determinism: Count",
                [f"First run: {len(units)}, Second run: {len(units_2)}"]
            )
            findings.append(f"Determinism: COUNT MISMATCH")
        else:
            print_check(True, f"Determinism: Count matches ({len(units)})")
        
        # Check 7.2: Same IDs
        id_matches = sum(
            1 for u1, u2 in zip(units, units_2)
            if u1.id == u2.id
        )
        
        passed = id_matches == len(units)
        all_passed &= print_check(
            passed,
            f"Determinism: IDs match ({id_matches}/{len(units)})",
            [] if passed else ["IDs changed between runs"]
        )
        
        # Check 7.3: Same types
        type_matches = sum(
            1 for u1, u2 in zip(units, units_2)
            if u1.type == u2.type
        )
        
        passed = type_matches == len(units)
        if passed:
            print_check(True, f"Determinism: Types match ({type_matches}/{len(units)})")
            findings.append(f"Determinism: 100% ({type_matches}/{len(units)} match)")
        else:
            print_check(
                False,
                f"Determinism: Types differ ({type_matches}/{len(units)} match)",
                ["Cache may not be working or signature changed"]
            )
            findings.append(f"Determinism: PARTIAL ({type_matches}/{len(units)} match)")
        
    except Exception as e:
        all_passed &= print_check(False, "Determinism test", [str(e)])
        findings.append(f"Determinism test: FAILED - {e}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print_header("VALIDATION SUMMARY")
    
    print()
    print("FINDINGS:")
    for i, finding in enumerate(findings, 1):
        print(f"  {i}. {finding}")
    
    print()
    if all_passed:
        print("✅ ALL CHECKPOINTS PASSED")
        print()
        print("Next steps:")
        print("  1. Test with more candidates (10, 20, 40)")
        print("  2. Measure actual costs")
        print("  3. Deploy to production pipeline")
    else:
        print("❌ SOME CHECKPOINTS FAILED")
        print()
        print("Review failures above and:")
        print("  1. Enable logging: import logging; logging.basicConfig(level=logging.DEBUG)")
        print("  2. Check API key is valid")
        print("  3. Check rate limits")
        print("  4. Review error messages")
    
    print()
    print("=" * 80)
    
    # Save findings to file
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    findings_file = output_dir / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(findings_file, 'w') as f:
        f.write(f"Phase A Validation Results\n")
        f.write(f"Time: {datetime.now()}\n")
        f.write(f"Status: {'PASS' if all_passed else 'FAIL'}\n")
        f.write(f"\nFindings:\n")
        for i, finding in enumerate(findings, 1):
            f.write(f"{i}. {finding}\n")
    
    print(f"📝 Findings saved to: {findings_file}")
    print()


if __name__ == "__main__":
    main()
