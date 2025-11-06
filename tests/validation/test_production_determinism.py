"""
Production determinism validation.

Tests available videos, extracting each 5 times to verify
100% deterministic output.
"""
import json
import hashlib
import glob
from pathlib import Path
from typing import List, Dict, Any
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor


def compute_units_hash(units: List[Dict[str, Any]]) -> str:
    """Compute deterministic hash of units list"""
    # Sort by ID to ensure consistent ordering
    sorted_units = sorted(units, key=lambda u: u['id'])
    units_json = json.dumps(sorted_units, sort_keys=True)
    return hashlib.sha256(units_json.encode('utf-8')).hexdigest()


def find_test_videos() -> List[Dict[str, str]]:
    """Find all available test videos."""
    test_videos = []
    
    # Find all transcript files
    transcript_files = glob.glob("output/channels/*/transcripts/*.md")
    
    for transcript_path_str in transcript_files:
        transcript_path = Path(transcript_path_str)
        
        # Extract video ID from filename (last part before .md)
        filename = transcript_path.stem
        # Format is typically "Title_VIDEO_ID"
        parts = filename.rsplit('_', 1)
        if len(parts) == 2:
            video_id = parts[1]
        else:
            video_id = filename
        
        test_videos.append({
            "id": video_id,
            "path": str(transcript_path)
        })
    
    return test_videos


def test_single_video_determinism(video_id: str, transcript: str) -> Dict[str, Any]:
    """
    Test determinism for a single video.
    
    Returns:
        {
            'video_id': str,
            'deterministic': bool,
            'unit_count': int,
            'unique_results': int,
            'hashes': List[str]
        }
    """
    extractor = DeterministicExtractor()
    
    # Extract 5 times
    results = []
    hashes = []
    
    for run in range(5):
        result = extractor.extract(video_id, transcript)
        results.append(result)
        
        # Compute hash of units
        units_hash = compute_units_hash(result['units'])
        hashes.append(units_hash)
    
    # Check if all hashes are identical
    unique_hashes = len(set(hashes))
    is_deterministic = unique_hashes == 1
    
    return {
        'video_id': video_id,
        'deterministic': is_deterministic,
        'unit_count': len(results[0]['units']),
        'unique_results': unique_hashes,
        'hashes': hashes
    }


def run_full_validation() -> Dict[str, Any]:
    """
    Run full determinism validation on all test videos.
    
    Returns:
        {
            'total_videos': int,
            'deterministic_count': int,
            'determinism_rate': float,
            'results': List[Dict]
        }
    """
    print("\n=== PRODUCTION DETERMINISM VALIDATION ===\n")
    
    # Find test videos
    test_videos = find_test_videos()
    
    if not test_videos:
        print("❌ No test videos found")
        return {
            'total_videos': 0,
            'deterministic_count': 0,
            'determinism_rate': 0,
            'results': []
        }
    
    print(f"Found {len(test_videos)} video(s) for testing")
    print(f"Testing {len(test_videos)} videos × 5 runs each...\n")
    
    all_results = []
    
    for i, video_info in enumerate(test_videos, 1):
        video_id = video_info['id']
        transcript_path = Path(video_info['path'])
        
        if not transcript_path.exists():
            print(f"⚠️  Video {i}/{len(test_videos)}: {video_id} - Transcript not found, skipping")
            continue
        
        print(f"Testing {i}/{len(test_videos)}: {video_id}...", end=' ', flush=True)
        
        content = transcript_path.read_text()
        # Extract just the transcript part (skip markdown headers)
        if "## Transcript" in content:
            content = content.split("## Transcript")[1]
        
        transcript = content.strip()
        result = test_single_video_determinism(video_id, transcript)
        all_results.append(result)
        
        status = "✓" if result['deterministic'] else "✗"
        print(f"{status} {result['unit_count']} units, {result['unique_results']} unique")
    
    # Summary
    total = len(all_results)
    deterministic = sum(1 for r in all_results if r['deterministic'])
    rate = (deterministic / total * 100) if total > 0 else 0
    
    print(f"\n=== RESULTS ===")
    print(f"Total videos: {total}")
    print(f"Deterministic: {deterministic}/{total} ({rate:.1f}%)")
    print(f"Status: {'✅ PASS' if rate == 100 else '❌ FAIL'}")
    
    return {
        'total_videos': total,
        'deterministic_count': deterministic,
        'determinism_rate': rate,
        'results': all_results
    }

def test_determinism_validation():
    """Test that all available videos show 100% determinism"""
    results = run_full_validation()
    
    # Write results to file
    results_path = Path("tests/validation/determinism_results.json")
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {results_path}")
    
    # Assert 100% determinism
    assert results['determinism_rate'] == 100, \
        f"Only {results['determinism_rate']:.1f}% determinism achieved"


if __name__ == '__main__':
    results = run_full_validation()
    
    # Write results to file
    results_path = Path("tests/validation/determinism_results.json")
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {results_path}")
    
    # Exit with appropriate code
    exit(0 if results['determinism_rate'] == 100 else 1)
