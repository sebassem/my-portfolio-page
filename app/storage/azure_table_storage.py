"""
Azure Table Storage Backend for Rate Limiting
==============================================
Provides persistent rate limiting across container restarts using Azure Table Storage.
This is essentially free for low-volume use cases like portfolio sites.
"""

import os
import re
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from limits.storage import Storage


class AzureTableStorage(Storage):
    """
    Custom rate limiter storage backend using Azure Table Storage.
    
    Provides persistent rate limiting across container restarts.
    Uses Azure Table Storage which is essentially free for this use case.
    """
    
    STORAGE_SCHEME = ["azuretable"]
    
    def __init__(
        self,
        uri: str = None,
        table_name: str = "ratelimits",
        credential: DefaultAzureCredential = None,
        **options
    ):
        """
        Initialize Azure Table Storage backend.
        
        Args:
            uri: Not used (kept for compatibility). Uses AZURE_STORAGE_ACCOUNT env var.
            table_name: Name of the table to store rate limit data
            credential: Azure credential to use. If None, creates new DefaultAzureCredential.
            **options: Additional options (unused)
        """
        storage_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        if not storage_account:
            raise ValueError("AZURE_STORAGE_ACCOUNT_NAME environment variable required")
        
        # Use provided credential or create new one
        if credential is None:
            credential = DefaultAzureCredential()
        
        # Use DefaultAzureCredential for authentication (same as other Azure services)
        self.table_client = TableServiceClient(
            endpoint=f"https://{storage_account}.table.core.windows.net",
            credential=credential
        ).get_table_client(table_name)
        
        # Ensure table exists
        try:
            self.table_client.create_table()
        except Exception:
            pass  # Table already exists
    
    def _sanitize_key(self, key: str) -> str:
        """
        Extract IP address from key for use as RowKey.
        
        The limits library generates keys like: LIMITER_192.168.1.1__ask_3_1_day
        We extract just the IP so changing rate limits doesn't create new entries.
        """
        # Extract IP address from the key (IPv4 pattern)
        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', key)
        if ip_match:
            return ip_match.group(1)
        # Fallback: sanitize the full key if no IP found
        return key.replace("/", "_").replace("\\", "_").replace("#", "_").replace("?", "_")
    
    def _get_entity(self, key: str) -> Optional[dict]:
        """Get entity from table, returning None if not found or expired."""
        try:
            entity = self.table_client.get_entity(
                partition_key="ratelimit",
                row_key=self._sanitize_key(key)
            )
            # Check if expired
            if entity.get("expiry") and entity["expiry"] < time.time():
                self._delete_entity(key)
                return None
            return entity
        except Exception:
            return None
    
    def _delete_entity(self, key: str) -> None:
        """Delete entity from table."""
        try:
            self.table_client.delete_entity(
                partition_key="ratelimit",
                row_key=self._sanitize_key(key)
            )
        except Exception:
            pass
    
    def incr(self, key: str, expiry: int, elastic_expiry: bool = False, amount: int = 1) -> int:
        """
        Increment the counter for a rate limit key.
        
        Args:
            key: The rate limit key (includes IP and limit info)
            expiry: TTL in seconds
            elastic_expiry: If True, reset expiry on each increment
            amount: Amount to increment by
            
        Returns:
            New counter value
        """
        entity = self._get_entity(key)
        now = time.time()
        
        if entity:
            new_count = entity.get("count", 0) + amount
            new_expiry = now + expiry if elastic_expiry else entity.get("expiry", now + expiry)
        else:
            new_count = amount
            new_expiry = now + expiry
        
        # Upsert the entity
        self.table_client.upsert_entity({
            "PartitionKey": "ratelimit",
            "RowKey": self._sanitize_key(key),
            "count": new_count,
            "expiry": new_expiry,
            "updated": datetime.now(timezone.utc).isoformat()
        })
        
        return new_count
    
    def get(self, key: str) -> int:
        """Get the current counter value for a key."""
        entity = self._get_entity(key)
        return entity.get("count", 0) if entity else 0
    
    def get_expiry(self, key: str) -> int:
        """Get the expiry time for a key."""
        entity = self._get_entity(key)
        return int(entity.get("expiry", 0)) if entity else 0
    
    def check(self) -> bool:
        """Check if storage is available."""
        try:
            # Try to query the table
            list(self.table_client.query_entities("PartitionKey eq 'ratelimit'", results_per_page=1))
            return True
        except Exception:
            return False
    
    def reset(self) -> Optional[int]:
        """Reset all rate limits (delete all entities)."""
        try:
            count = 0
            for entity in self.table_client.query_entities("PartitionKey eq 'ratelimit'"):
                self.table_client.delete_entity(entity)
                count += 1
            return count
        except Exception:
            return None
    
    def clear(self, key: str) -> None:
        """Clear a specific key."""
        self._delete_entity(key)
    
    @property
    def base_exceptions(self) -> Tuple[type, ...]:
        """
        Return tuple of exceptions that should trigger a fallback to in-memory storage.
        
        Required by the limits library Storage base class.
        
        Returns:
            Tuple of exception types
        """
        return (Exception,)
    
    def get_moving_window(self, key: str, limit: int, expiry: int) -> Tuple[int, int]:
        """
        Get the moving window information for a key.
        
        Required by the limits library for moving window rate limiting.
        
        Args:
            key: The rate limit key
            limit: The rate limit
            expiry: The window size in seconds
            
        Returns:
            Tuple of (timestamp of window start, count of requests in window)
        """
        entity = self._get_entity(key)
        if entity:
            # Return the window start time and current count
            window_start = int(entity.get("expiry", time.time()) - expiry)
            return (window_start, entity.get("count", 0))
        return (int(time.time()), 0)
