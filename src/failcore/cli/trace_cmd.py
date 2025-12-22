# failcore/cli/trace_cmd.py
"""
Trace management commands: ingest, query, stats
"""

import json
from pathlib import Path
from failcore.infra.storage import SQLiteStore, TraceIngestor


def trace_ingest(args):
    """Ingest trace file into database"""
    trace_path = args.trace
    db_path = ".failcore/failcore.db"  # Global shared database
    
    # Ensure .failcore directory exists
    Path(".failcore").mkdir(exist_ok=True)
    
    if not Path(trace_path).exists():
        print(f"Error: Trace file not found: {trace_path}")
        return 1
    
    print(f"Ingesting: {trace_path}")
    print(f"Database: {db_path}")
    print()
    
    # Create store and ingestor
    with SQLiteStore(db_path) as store:
        # Initialize schema
        store.init_schema()
        
        # Ingest file (skip if run_id already exists)
        ingestor = TraceIngestor(store)
        stats = ingestor.ingest_file(trace_path, skip_if_exists=True)
        
        if stats.get("skipped"):
            print("[SKIPPED] Run already exists in database")
            return 0
        
        print("[OK] Ingest completed")
        print(f"  Events ingested: {stats['events']}")
        print(f"  Steps aggregated: {stats['steps']}")
        if stats.get('incomplete', 0) > 0:
            print(f"  Incomplete steps: {stats['incomplete']}")
        if stats.get('errors', 0) > 0:
            print(f"  Errors: {stats['errors']}")
        print()
        
        # Show database stats
        db_stats = store.get_stats()
        print("Database Statistics:")
        print(f"  Total events: {db_stats['events']}")
        print(f"  Total steps: {db_stats['steps']}")
        print(f"  Runs: {db_stats['runs']}")
        print()
        
        if db_stats.get('status_distribution'):
            print("Status Distribution:")
            for status, count in sorted(db_stats['status_distribution'].items(), key=lambda x: -x[1]):
                print(f"  {status:15s} {count:5d}")
            print()
        
        if db_stats.get('tool_distribution'):
            print("Top Tools:")
            for tool, count in list(db_stats['tool_distribution'].items())[:5]:
                print(f"  {tool:20s} {count:5d}")
    
    return 0


def trace_query(args):
    """Execute SQL query on trace database"""
    db_path = ".failcore/failcore.db"  # Global shared database
    sql = args.query
    
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Hint: Run 'failcore trace ingest <trace.jsonl>' first")
        return 1
    
    with SQLiteStore(db_path) as store:
        try:
            results = store.query(sql)
            
            if not results:
                print("(0 rows)")
                return 0
            
            # Get column names
            columns = list(results[0].keys())
            
            # Print header
            header = " | ".join(f"{col:20s}" for col in columns)
            print(header)
            print("-" * len(header))
            
            # Print rows
            for row in results:
                values = [str(row[col]) if row[col] is not None else "NULL" for col in columns]
                print(" | ".join(f"{val:20s}" for val in values))
            
            print()
            print(f"({len(results)} rows)")
            
        except Exception as e:
            print(f"Error executing query: {e}")
            return 1
    
    return 0


def trace_stats(args):
    """Show trace database statistics"""
    db_path = ".failcore/failcore.db"  # Global shared database
    run_id = getattr(args, 'run', None)
    
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Hint: Run 'failcore trace ingest <trace.jsonl>' first")
        return 1
    
    with SQLiteStore(db_path) as store:
        stats = store.get_stats(run_id=run_id)
        
        print(f"Database Statistics: {Path(db_path).name}")
        if run_id:
            print(f"Run Filter: {run_id}")
        print("="*60)
        print(f"Total Events: {stats['events']}")
        print(f"Total Steps: {stats['steps']}")
        print(f"Runs: {stats['runs']}")
        print()
        
        if stats.get('status_distribution'):
            print("Status Distribution:")
            total = sum(stats['status_distribution'].values())
            for status, count in stats['status_distribution'].items():
                pct = count / total * 100 if total > 0 else 0
                print(f"  {status:20s} {count:3d} ({pct:5.1f}%)")
            print()
        
        if stats.get('tool_distribution'):
            print("Top Tools:")
            for tool, count in sorted(stats['tool_distribution'].items(), key=lambda x: -x[1])[:10]:
                print(f"  {tool:40s} {count:3d}")
    
    return 0
