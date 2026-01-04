#!/usr/bin/env python3
"""
AstroFiler Database Migration Management Script

This script provides utilities for managing database migrations using peewee-migrate.

Usage:
    python migrate.py status          - Show current migration status
    python migrate.py create <name>   - Create a new migration
    python migrate.py run             - Run all pending migrations
    python migrate.py help            - Show this help message

Examples:
    python migrate.py create add_new_field
    python migrate.py run
    python migrate.py status
"""

import sys
import os
import argparse
import logging

# Configure Python path for new package structure - must be before any astrofiler imports
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')

# Ensure src path is first in path to avoid conflicts with root astrofiler.py
if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)

# Now import astrofiler modules
try:
    from astrofiler.database import (
        setup_database,
        create_migration,
        run_migrations,
        get_migration_status,
        reset_migration_history,
        reset_database_file,
    )
    from astrofiler.exceptions import DatabaseError
except ImportError as e:
    print(f"Error importing astrofiler modules: {e}")
    print("Make sure you're running this from the project root directory.")
    sys.exit(1)

# Configure logging - using central astrofiler.log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('astrofiler.log', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description='AstroFiler Database Migration Management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show migration status')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new migration')
    create_parser.add_argument('name', help='Name of the migration')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run all pending migrations')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Initial database setup')

    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset migration state and/or database')
    reset_parser.add_argument(
        '--hard',
        action='store_true',
        help='Delete the SQLite database file (fresh start). Default is history-only.'
    )
    reset_parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create a DB backup before resetting.'
    )
    reset_parser.add_argument(
        '--backup-dir',
        default=None,
        help='Optional directory to write backups into.'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'status':
            status = get_migration_status()
            if status:
                print("Migration Status:")
                print(f"Current migration: {status['current']}")
                print(f"Completed migrations: {len(status['done'])}")
                if status['done']:
                    for migration in status['done']:
                        print(f"  [OK] {migration}")
                print(f"Pending migrations: {len(status['undone'])}")
                if status['undone']:
                    for migration in status['undone']:
                        print(f"  [ ] {migration}")
                if not status['undone']:
                    print("  No pending migrations")
            else:
                print("Error getting migration status")
                
        elif args.command == 'create':
            if create_migration(args.name):
                print(f"Migration '{args.name}' created successfully")
            else:
                print(f"Error creating migration '{args.name}'")
                
        elif args.command == 'run':
            if run_migrations():
                print("All migrations completed successfully")
            else:
                print("Error running migrations")
                
        elif args.command == 'setup':
            if setup_database():
                print("Database setup completed successfully")
            else:
                print("Error during database setup")

        elif args.command == 'reset':
            backup = not args.no_backup
            if args.hard:
                if reset_database_file(backup=backup, backup_dir=args.backup_dir):
                    print("Database file removed. Next run will recreate schema.")
                else:
                    print("Error resetting database file")
            else:
                if reset_migration_history(backup=backup, backup_dir=args.backup_dir):
                    print("Migration history reset (migratehistory dropped).")
                else:
                    print("Error resetting migration history")
                
    except DatabaseError as e:
        # Handle database errors gracefully without traceback
        print(f"\n{'='*70}")
        print("DATABASE ERROR")
        print(f"{'='*70}")
        print(f"\n{e}\n")
        print(f"{'='*70}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
