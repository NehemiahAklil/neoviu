"""
Example usage for the registry command
"""

main = """

Examples:
  # Sync with remote AniList
  nviu registry sync --upload --download

  # Show detailed registry statistics  
  nviu registry stats --detailed

  # Search local registry
  nviu registry search "attack on titan"

  # Export registry to JSON
  nviu registry export --format json --output backup.json

  # Import from backup
  nviu registry import backup.json

  # Clean up orphaned entries
  nviu registry clean --dry-run

  # Create full backup
  nviu registry backup --compress

  # Restore from backup
  nviu registry restore backup.tar.gz
"""
