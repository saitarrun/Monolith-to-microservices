"""
=============================================================================
Dual-Write Utility – Strangler Fig Phase 6
=============================================================================
During the transition period, the monolith writes user data to BOTH:
  1. The legacy monolith database (existing behavior)
  2. The new user-service's database (via HTTP or direct DB write)

This ensures data consistency while both systems are active.
Once the user-service handles 100% of traffic AND the monolith's user code
is removed (Phase 7), this module becomes unnecessary and should be deleted.
=============================================================================
"""

import logging
import requests
import psycopg2
import os
from functools import wraps

logger = logging.getLogger(__name__)

# Toggle for dual-write mode. Set via environment variable.
DUAL_WRITE_ENABLED = os.environ.get('DUAL_WRITE_ENABLED', 'true').lower() == 'true'
USER_SVC_URL = os.environ.get('USER_SVC_URL', 'http://user-svc')
USER_SVC_DB_URL = os.environ.get('USER_SVC_DB_URL', os.environ.get('DATABASE_URL', ''))


class DualWriteError(Exception):
    """Raised when the secondary write fails. Non-fatal – logged for reconciliation."""
    pass


def dual_write_user_http(user_data: dict) -> dict | None:
    """
    Write user data to the user-service via HTTP POST.
    
    This is the preferred approach when the user-service is accessible.
    Falls back to direct DB write if HTTP fails.
    
    Args:
        user_data: Dict with 'email' and 'name' keys.
    
    Returns:
        Response JSON from user-service, or None on failure.
    """
    if not DUAL_WRITE_ENABLED:
        return None

    try:
        response = requests.post(
            f"{USER_SVC_URL}/api/users",
            json=user_data,
            timeout=5,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in (200, 201):
            logger.info(f"Dual-write HTTP success for user: {user_data.get('email')}")
            return response.json()
        elif response.status_code == 409:
            logger.info(f"Dual-write HTTP: user already exists (idempotent): {user_data.get('email')}")
            return None
        else:
            logger.warning(
                f"Dual-write HTTP failed ({response.status_code}): {response.text}"
            )
            # Fall back to direct DB write
            return dual_write_user_db(user_data)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Dual-write HTTP error: {e}")
        # Fall back to direct DB write
        return dual_write_user_db(user_data)


def dual_write_user_db(user_data: dict) -> dict | None:
    """
    Write user data directly to the user-service database.
    
    Fallback approach when the user-service HTTP endpoint is unreachable.
    Uses the same database connection string as the user-service.
    
    Args:
        user_data: Dict with 'email' and 'name' keys.
    
    Returns:
        Dict with user 'id', or None on failure.
    """
    if not DUAL_WRITE_ENABLED or not USER_SVC_DB_URL:
        return None

    conn = None
    try:
        conn = psycopg2.connect(USER_SVC_DB_URL)
        conn.autocommit = False
        
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users_microservice (email, name, migrated_from, created_at, updated_at)
                   VALUES (%s, %s, 'dual-write', NOW(), NOW())
                   ON CONFLICT (email) DO NOTHING
                   RETURNING id""",
                (user_data['email'], user_data['name'])
            )
            result = cur.fetchone()
        
        conn.commit()
        
        if result:
            logger.info(f"Dual-write DB success for user: {user_data.get('email')} (id: {result[0]})")
            return {"id": result[0]}
        else:
            logger.info(f"Dual-write DB: user already exists (idempotent): {user_data.get('email')}")
            return None
            
    except Exception as e:
        logger.error(f"Dual-write DB error: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


def dual_write_update_user(user_id: int, user_data: dict) -> dict | None:
    """
    Update user data in the user-service via HTTP PUT.
    
    Args:
        user_id: The user ID to update.
        user_data: Dict with fields to update.
    
    Returns:
        Response JSON from user-service, or None on failure.
    """
    if not DUAL_WRITE_ENABLED:
        return None

    try:
        response = requests.put(
            f"{USER_SVC_URL}/api/users/{user_id}",
            json=user_data,
            timeout=5,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info(f"Dual-write update success for user {user_id}")
            return response.json()
        else:
            logger.warning(f"Dual-write update failed ({response.status_code}): {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Dual-write update error: {e}")
        return None


def dual_write_delete_user(user_id: int) -> bool:
    """
    Delete user from the user-service via HTTP DELETE.
    
    Args:
        user_id: The user ID to delete.
    
    Returns:
        True if successful, False otherwise.
    """
    if not DUAL_WRITE_ENABLED:
        return False

    try:
        response = requests.delete(
            f"{USER_SVC_URL}/api/users/{user_id}",
            timeout=5,
        )
        
        if response.status_code in (200, 404):
            logger.info(f"Dual-write delete for user {user_id}: {response.status_code}")
            return True
        else:
            logger.warning(f"Dual-write delete failed ({response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Dual-write delete error: {e}")
        return False
