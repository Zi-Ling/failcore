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
    db_path = args.db or trace_path.replace(".jsonl", ".db")
    
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
        
        # Ingest file
        ingestor = TraceIngestor(store)
        stats = ingestor.ingest_file(trace_path)
        
        print("✓ Ingest completed")
        print(f"  Events ingested: {stats['events']}")
        print(f"  Steps aggregated: {stats['steps']}")
        if stats['incomplete'] > 0:
            print(f"  Incomplete steps: {stats['incomplete']}")
        if stats['errors'] > 0:
            print(f"  Errors: {stats['errors']}")
        print()
        
        # Show database stats
        db_stats = store.get_stats()
        print("Database Statistics:")
        print(f"  Total events: {db_stats['events']}")
        print(f"  Total steps: {db_stats['steps']}")
        print(f"  Runs: {db_stats['runs']}")
        print()
        
        if db_stats['status_distribution']:
            print("Status Distribution:")
            for status, count in sorted(db_stats['status_distribution'].items(), key=lambda x: -x[1]):
                print(f"  {status:15s} {count:5d}")
            print()
        
        if db_stats['top_tools']:
            print("Top Tools:")
            for tool, count in list(db_stats['top_tools'].items())[:5]:
                print(f"  {tool:20s} {count:5d}")
    
    return 0


def trace_query(args):
    """Execute SQL query on trace database"""
    db_path = args.db
    sql = args.sql
    
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Run 'failcore trace ingest' first")
        return 1
    
    with SQLiteStore(db_path) as store:
        try:
            results = store.query(sql)
            
            if not results:
                print("(no results)")
                return 0
            
            # Print results as table
            if results:
                keys = list(results[0].keys())
                
                # Print header
                print(" | ".join(f"{k:20s}" for k in keys))
                print("-" * (len(keys) * 23))
                
                # Print rows
                for row in results:
                    print(" | ".join(f"{str(row[k])[:20]:20s}" for k in keys))
                
                print()
                print(f"({len(results)} row{'s' if len(results) != 1 else ''})")
        
        except Exception as e:
            print(f"Query error: {e}")
            return 1
    
    return 0


def trace_stats(args):
    """Show trace statistics (from jsonl or db)"""
    source = args.source
    
    # Check if it's a database
    if source.endswith(".db") and Path(source).exists():
        return _stats_from_db(source)
    elif source.endswith(".jsonl") and Path(source).exists():
        return _stats_from_jsonl(source)
    else:
        print(f"Error: Unknown source type or file not found: {source}")
        print("Supported: .jsonl or .db files")
        return 1


def _stats_from_db(db_path: str):
    """Show stats from database"""
    with SQLiteStore(db_path) as store:
        stats = store.get_stats()
        
        print(f"Database Statistics: {Path(db_path).name}")
        print(f"{'='*60}")
        print(f"Total Events: {stats['events']}")
        print(f"Total Steps: {stats['steps']}")
        print(f"Runs: {stats['runs']}")
        print()
        
        if stats['status_distribution']:
            print("Status Distribution:")
            for status, count in sorted(stats['status_distribution'].items(), key=lambda x: -x[1]):
                pct = count / stats['steps'] * 100 if stats['steps'] > 0 else 0
                print(f"  {status:15s} {count:5d} ({pct:5.1f}%)")
            print()
        
        if stats['top_tools']:
            print("Top Tools:")
            for tool, count in stats['top_tools'].items():
                print(f"  {tool:30s} {count:5d}")
    
    return 0


def _stats_from_jsonl(trace_path: str):
    """Show stats from jsonl (without database)"""
    from collections import Counter
    
    events = []
    steps_by_status = Counter()
    tools = Counter()
    event_types = Counter()
    
    with open(trace_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                event = json.loads(line)
                events.append(event)
                
                evt = event.get("event", {})
                evt_type = evt.get("type", "UNKNOWN")
                event_types[evt_type] += 1
                
                step = evt.get("step", {})
                if step.get("tool"):
                    tools[step["tool"]] += 1
                
                if evt_type == "STEP_END":
                    data = evt.get("data", {})
                    result = data.get("result", {})
                    status = result.get("status", "UNKNOWN")
                    steps_by_status[status] += 1
            
            except json.JSONDecodeError:
                continue
    
    print(f"Trace Statistics: {Path(trace_path).name}")
    print(f"{'='*60}")
    print(f"Total Events: {len(events)}")
    print(f"Total Steps: {sum(steps_by_status.values())}")
    print()
    
    print("Event Types:")
    for evt_type, count in event_types.most_common():
        print(f"  {evt_type:25s} {count:5d}")
    print()
    
    if steps_by_status:
        print("Status Distribution:")
        total_steps = sum(steps_by_status.values())
        for status, count in steps_by_status.most_common():
            pct = count / total_steps * 100 if total_steps > 0 else 0
            print(f"  {status:15s} {count:5d} ({pct:5.1f}%)")
        print()
    
    if tools:
        print("Top Tools:")
        for tool, count in tools.most_common(10):
            print(f"  {tool:30s} {count:5d}")
        print()
    
    print("Note: For faster analysis, run 'failcore trace ingest' to create a database")
    
    return 0
