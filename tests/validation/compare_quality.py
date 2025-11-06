"""
Quality comparison: Deterministic vs LLM extraction.

Compares unit counts, extraction time, and basic quality metrics
for same videos using both methods (if old analyses exist).
"""
import json
import time
import glob
from pathlib import Path
from typing import Dict, List, Any, Optional
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor


def find_video_with_analysis(video_id: str) -> Optional[Dict[str, Any]]:
    """Find video analysis files."""
    # Look for analysis file
    analysis_files = glob.glob(f"output/*/{video_id}-analysis.json")
    if not analysis_files:
        analysis_files = glob.glob(f"output/test_{video_id}_analysis.json")
    
    if not analysis_files:
        return None
    
    analysis_path = Path(analysis_files[0])
    if not analysis_path.exists():
        return None
    
    return {
        'analysis_path': str(analysis_path),
        'analysis': json.loads(analysis_path.read_text())
    }


def extract_with_deterministic(video_id: str, transcript: str) -> Dict[str, Any]:
    """Extract using deterministic extractor."""
    extractor = DeterministicExtractor()
    
    start = time.time()
    result = extractor.extract(video_id, transcript)
    elapsed = time.time() - start
    
    return {
        'time': elapsed,
        'units': result['units'],
        'unit_count': len(result['units'])
    }


def compare_single_video(
    video_id: str,
    transcript: str,
    old_analysis: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compare extraction quality for a single video.
    """
    # Extract with new system
    new_result = extract_with_deterministic(video_id, transcript)
    
    comparison = {
        'video_id': video_id,
        'new_unit_count': new_result['unit_count'],
        'new_time': new_result['time'],
        'new_units_sample': [u['text'][:50] for u in new_result['units'][:3]]
    }
    
    # Compare with old if available
    if old_analysis:
        old_units = old_analysis.get('knowledge_units', [])
        comparison['old_unit_count'] = len(old_units)
        comparison['old_units_sample'] = [u.get('text', '')[:50] for u in old_units[:3]]
        
        # Calculate difference
        if old_units:
            unit_diff = new_result['unit_count'] - len(old_units)
            unit_diff_pct = (unit_diff / len(old_units) * 100) if len(old_units) > 0 else 0
            comparison['unit_count_diff'] = unit_diff
            comparison['unit_count_diff_pct'] = unit_diff_pct
    else:
        comparison['old_unit_count'] = None
        comparison['old_units_sample'] = None
    
    return comparison


def run_quality_comparison() -> Dict[str, Any]:
    """
    Run quality comparison on available test videos.
    """
    print("\n=== QUALITY COMPARISON ===\n")
    
    # Find test transcripts
    transcript_files = glob.glob("output/channels/*/transcripts/*.md")
    
    if not transcript_files:
        print("❌ No transcripts found for comparison")
        return {
            'comparison_available': False,
            'message': 'No transcripts found'
        }
    
    print(f"Found {len(transcript_files)} transcript(s)\n")
    
    results = []
    
    for transcript_path_str in transcript_files:
        transcript_path = Path(transcript_path_str)
        
        # Extract video ID
        filename = transcript_path.stem
        parts = filename.rsplit('_', 1)
        video_id = parts[1] if len(parts) == 2 else filename
        
        print(f"Comparing {video_id}...", end=' ', flush=True)
        
        # Read transcript
        content = transcript_path.read_text()
        if "## Transcript" in content:
            content = content.split("## Transcript")[1]
        transcript = content.strip()
        
        # Find old analysis if available
        old_analysis_info = find_video_with_analysis(video_id)
        old_analysis = old_analysis_info['analysis'] if old_analysis_info else None
        
        # Compare
        comparison = compare_single_video(video_id, transcript, old_analysis)
        results.append(comparison)
        
        has_old = "✓" if old_analysis else "○"
        print(f"{has_old} {comparison['new_unit_count']} units")
    
    # Aggregate statistics
    new_counts = [r['new_unit_count'] for r in results]
    new_times = [r['new_time'] for r in results]
    
    avg_new_count = sum(new_counts) / len(new_counts) if new_counts else 0
    avg_new_time = sum(new_times) / len(new_times) if new_times else 0
    
    # Statistics for videos with old analysis
    old_counts = [r['old_unit_count'] for r in results if r['old_unit_count'] is not None]
    avg_old_count = sum(old_counts) / len(old_counts) if old_counts else None
    
    print(f"\n=== SUMMARY ===")
    print(f"Videos analyzed: {len(results)}")
    print(f"Videos with old analysis: {len(old_counts)}")
    print(f"\nAverage unit count (new): {avg_new_count:.1f}")
    if avg_old_count:
        print(f"Average unit count (old): {avg_old_count:.1f}")
        change_pct = ((avg_new_count / avg_old_count - 1) * 100) if avg_old_count > 0 else 0
        print(f"Change: {change_pct:+.1f}%")
    
    print(f"\nAverage extraction time (new): {avg_new_time:.3f}s")
    
    return {
        'comparison_available': True,
        'videos_analyzed': len(results),
        'videos_with_old_analysis': len(old_counts),
        'avg_new_count': avg_new_count,
        'avg_old_count': avg_old_count,
        'avg_new_time': avg_new_time,
        'results': results
    }


def test_quality_validation():
    """Test quality comparison runs successfully."""
    results = run_quality_comparison()
    
    # Write detailed report
    report_path = Path("tests/validation/quality_comparison_report.json")
    report_path.write_text(json.dumps(results, indent=2))
    
    print(f"\nDetailed report: {report_path}")
    
    # Basic assertions
    assert results['comparison_available'], "Comparison should be available"
    assert results['videos_analyzed'] > 0, "Should analyze at least one video"
    assert results['avg_new_count'] > 0, "Should extract units"
    assert results['avg_new_time'] > 0, "Should have extraction time"
    assert results['avg_new_time'] < 5.0, "Extraction should be fast (<5s)"


if __name__ == '__main__':
    test_quality_validation()
