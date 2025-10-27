#!/usr/bin/env python3
"""
PHANTOM Security AI - Performance Benchmark Runner

This script runs comprehensive performance benchmarks to measure
the impact of resilience and reliability improvements.

Usage:
    python benchmark_runner.py --all
    python benchmark_runner.py --database --cache
    python benchmark_runner.py --compare baseline_db improved_db
"""

import asyncio
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.core.benchmarks.performance_benchmarks import (
    PerformanceBenchmark, BenchmarkConfig,
    database_query_benchmark, cache_operation_benchmark,
    health_check_benchmark, websocket_benchmark
)


async def run_database_benchmark(benchmark: PerformanceBenchmark) -> None:
    """Run database performance benchmark"""
    config = BenchmarkConfig(
        name="database_queries",
        description="Database query performance with connection pooling",
        iterations=1000,
        concurrency=20,
        warmup_iterations=50
    )
    
    print(f"Running database benchmark: {config.iterations} iterations, {config.concurrency} concurrent...")
    result = await benchmark.run_benchmark(database_query_benchmark, config)
    
    print(f"✅ Database Benchmark Results:")
    print(f"   Mean Response Time: {result.mean_response_time:.2f}ms")
    print(f"   P95 Response Time: {result.p95_response_time:.2f}ms")
    print(f"   Throughput: {result.requests_per_second:.2f} req/s")
    print(f"   Success Rate: {(result.successful_iterations/result.total_iterations*100):.1f}%")
    print()


async def run_cache_benchmark(benchmark: PerformanceBenchmark) -> None:
    """Run cache performance benchmark"""
    config = BenchmarkConfig(
        name="cache_operations",
        description="Cache set/get operations with compression",
        iterations=5000,
        concurrency=50,
        warmup_iterations=100
    )
    
    print(f"Running cache benchmark: {config.iterations} iterations, {config.concurrency} concurrent...")
    result = await benchmark.run_benchmark(cache_operation_benchmark, config)
    
    print(f"✅ Cache Benchmark Results:")
    print(f"   Mean Response Time: {result.mean_response_time:.2f}ms")
    print(f"   P95 Response Time: {result.p95_response_time:.2f}ms")
    print(f"   Throughput: {result.requests_per_second:.2f} req/s")
    print(f"   Success Rate: {(result.successful_iterations/result.total_iterations*100):.1f}%")
    print()


async def run_health_check_benchmark(benchmark: PerformanceBenchmark) -> None:
    """Run health check performance benchmark"""
    config = BenchmarkConfig(
        name="health_checks",
        description="Comprehensive health check execution",
        iterations=100,
        concurrency=5,
        warmup_iterations=10
    )
    
    print(f"Running health check benchmark: {config.iterations} iterations, {config.concurrency} concurrent...")
    result = await benchmark.run_benchmark(health_check_benchmark, config)
    
    print(f"✅ Health Check Benchmark Results:")
    print(f"   Mean Response Time: {result.mean_response_time:.2f}ms")
    print(f"   P95 Response Time: {result.p95_response_time:.2f}ms")
    print(f"   Throughput: {result.requests_per_second:.2f} req/s")
    print(f"   Success Rate: {(result.successful_iterations/result.total_iterations*100):.1f}%")
    print()


async def run_websocket_benchmark(benchmark: PerformanceBenchmark) -> None:
    """Run WebSocket performance benchmark"""
    config = BenchmarkConfig(
        name="websocket_messages",
        description="WebSocket message handling with queueing",
        iterations=2000,
        concurrency=30,
        warmup_iterations=50
    )
    
    print(f"Running WebSocket benchmark: {config.iterations} iterations, {config.concurrency} concurrent...")
    result = await benchmark.run_benchmark(websocket_benchmark, config)
    
    print(f"✅ WebSocket Benchmark Results:")
    print(f"   Mean Response Time: {result.mean_response_time:.2f}ms")
    print(f"   P95 Response Time: {result.p95_response_time:.2f}ms")
    print(f"   Throughput: {result.requests_per_second:.2f} req/s")
    print(f"   Success Rate: {(result.successful_iterations/result.total_iterations*100):.1f}%")
    print()


async def run_all_benchmarks(benchmark: PerformanceBenchmark) -> None:
    """Run all performance benchmarks"""
    print("🚀 Starting comprehensive performance benchmarks...")
    print("=" * 60)
    
    start_time = datetime.utcnow()
    
    try:
        await run_database_benchmark(benchmark)
        await run_cache_benchmark(benchmark)
        await run_health_check_benchmark(benchmark)
        await run_websocket_benchmark(benchmark)
    except Exception as e:
        print(f"❌ Benchmark execution failed: {e}")
        return
    
    end_time = datetime.utcnow()
    total_duration = (end_time - start_time).total_seconds()
    
    print("=" * 60)
    print(f"✅ All benchmarks completed in {total_duration:.2f} seconds")
    
    # Generate summary report
    summary = benchmark.get_summary_report()
    print("\n📊 Summary Report:")
    print(f"   Total Benchmarks: {summary['summary']['total_benchmarks']}")
    print(f"   Total Requests: {summary['summary']['total_requests']:,}")
    print(f"   Overall Success Rate: {summary['summary']['overall_success_rate_percent']:.1f}%")
    print(f"   Overall Mean Response: {summary['summary']['overall_mean_response_time_ms']:.2f}ms")
    
    # Export results
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"benchmark_results_{timestamp}.json"
    benchmark.export_results(filename)
    print(f"   Results exported to: {filename}")


def compare_benchmarks(benchmark: PerformanceBenchmark, baseline: str, comparison: str) -> None:
    """Compare two benchmark results"""
    try:
        comparison_result = benchmark.compare_results(baseline, comparison)
        
        print(f"📈 Benchmark Comparison: {baseline} vs {comparison}")
        print("=" * 60)
        
        baseline_data = comparison_result["baseline"]
        comparison_data = comparison_result["comparison"]
        improvements = comparison_result["improvements"]
        summary = comparison_result["summary"]
        
        print(f"Baseline ({baseline}):")
        print(f"   Mean Response Time: {baseline_data['mean_response_time_ms']:.2f}ms")
        print(f"   P95 Response Time: {baseline_data['p95_response_time_ms']:.2f}ms")
        print(f"   Throughput: {baseline_data['requests_per_second']:.2f} req/s")
        print(f"   Success Rate: {baseline_data['success_rate_percent']:.1f}%")
        
        print(f"\nComparison ({comparison}):")
        print(f"   Mean Response Time: {comparison_data['mean_response_time_ms']:.2f}ms")
        print(f"   P95 Response Time: {comparison_data['p95_response_time_ms']:.2f}ms")
        print(f"   Throughput: {comparison_data['requests_per_second']:.2f} req/s")
        print(f"   Success Rate: {comparison_data['success_rate_percent']:.1f}%")
        
        print("\n🔍 Performance Changes:")
        
        # Response time (lower is better)
        rt_change = improvements["response_time_change_percent"]
        rt_symbol = "✅" if rt_change < 0 else "❌" if rt_change > 0 else "➖"
        print(f"   Response Time: {rt_symbol} {rt_change:+.1f}%")
        
        # Throughput (higher is better)
        tp_change = improvements["throughput_change_percent"]
        tp_symbol = "✅" if tp_change > 0 else "❌" if tp_change < 0 else "➖"
        print(f"   Throughput: {tp_symbol} {tp_change:+.1f}%")
        
        # P95 response time (lower is better)
        p95_change = improvements["p95_response_time_change_percent"]
        p95_symbol = "✅" if p95_change < 0 else "❌" if p95_change > 0 else "➖"
        print(f"   P95 Response Time: {p95_symbol} {p95_change:+.1f}%")
        
        # Success rate (higher is better)
        sr_change = improvements["success_rate_change_percent"]
        sr_symbol = "✅" if sr_change > 0 else "❌" if sr_change < 0 else "➖"
        print(f"   Success Rate: {sr_symbol} {sr_change:+.1f}%")
        
        # Overall summary
        improvements_count = sum([
            summary["response_time_improved"],
            summary["throughput_improved"], 
            summary["p95_improved"],
            summary["reliability_improved"]
        ])
        
        print(f"\n📋 Overall Assessment:")
        print(f"   Improvements: {improvements_count}/4 metrics improved")
        
        if improvements_count >= 3:
            print("   🎉 Significant performance improvement!")
        elif improvements_count >= 2:
            print("   👍 Notable performance improvement")
        elif improvements_count >= 1:
            print("   📊 Some performance improvement")
        else:
            print("   ⚠️  No significant improvement detected")
            
    except ValueError as e:
        print(f"❌ Comparison failed: {e}")


async def main():
    """Main benchmark runner"""
    parser = argparse.ArgumentParser(
        description="PHANTOM Security AI Performance Benchmarks"
    )
    
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument("--database", action="store_true", help="Run database benchmark")
    parser.add_argument("--cache", action="store_true", help="Run cache benchmark")
    parser.add_argument("--health", action="store_true", help="Run health check benchmark")
    parser.add_argument("--websocket", action="store_true", help="Run WebSocket benchmark")
    
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "COMPARISON"),
                       help="Compare two benchmark results")
    
    parser.add_argument("--list", action="store_true", help="List available benchmark results")
    parser.add_argument("--export", help="Export results to specified file")
    parser.add_argument("--import", help="Import results from specified file")
    
    args = parser.parse_args()
    
    if not any([args.all, args.database, args.cache, args.health, args.websocket, 
               args.compare, args.list, args.export]):
        parser.print_help()
        return
    
    # Initialize benchmark
    benchmark = PerformanceBenchmark()
    
    try:
        # Import existing results if specified
        if getattr(args, 'import', None):
            print(f"Importing benchmark results from {getattr(args, 'import')}")
            # Implementation would load from file
        
        # Run benchmarks
        if args.all:
            await run_all_benchmarks(benchmark)
        else:
            if args.database:
                await run_database_benchmark(benchmark)
            if args.cache:
                await run_cache_benchmark(benchmark)
            if args.health:
                await run_health_check_benchmark(benchmark)
            if args.websocket:
                await run_websocket_benchmark(benchmark)
        
        # Handle comparisons
        if args.compare:
            compare_benchmarks(benchmark, args.compare[0], args.compare[1])
        
        # List results
        if args.list:
            summary = benchmark.get_summary_report()
            print("📋 Available Benchmark Results:")
            for bench in summary.get("benchmarks", []):
                print(f"   - {bench['name']} ({bench['timestamp']})")
        
        # Export results
        if args.export:
            benchmark.export_results(args.export)
            print(f"✅ Results exported to {args.export}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Benchmark interrupted by user")
    except Exception as e:
        print(f"❌ Benchmark execution failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())