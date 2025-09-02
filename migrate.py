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
import argparse
from astrofiler_db import setup_database, create_migration, run_migrations, get_migration_status
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
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
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'status':
        status = get_migration_status()
        if status:
            print("Migration Status:")
            print(f"Current migration: {status['current']}")
            print(f"Completed migrations: {len(status['done'])}")
            if status['done']:
                for migration in status['done']:
                    print(f"  ✓ {migration}")
            print(f"Pending migrations: {len(status['undone'])}")
            if status['undone']:
                for migration in status['undone']:
                    print(f"  ○ {migration}")
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

if __name__ == '__main__':
    main()
