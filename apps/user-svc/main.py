import os
from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

# =============================================================================
# User Microservice
# =============================================================================
# Extracted from the monolith as part of the Strangler Fig migration (Phase 3).
# Handles all user management CRUD operations.
#
# This service runs independently with its own connection to the shared
# database (during transition) or a dedicated user database (post-migration).
# =============================================================================

app = Flask(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/monolith"
)


def get_db_connection():
    """Create a new database connection."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def init_db():
    """Initialize the users table if it doesn't exist."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users_microservice (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    migrated_from VARCHAR(50) DEFAULT 'microservice'
                );
                CREATE INDEX IF NOT EXISTS idx_users_email ON users_microservice(email);
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Failed to initialize DB: {e}")
    finally:
        conn.close()


# -------------------------------------------------------
# Health Check
# -------------------------------------------------------
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Kubernetes readiness/liveness probes."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "healthy", "service": "user-svc"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


# -------------------------------------------------------
# List Users
# -------------------------------------------------------
@app.route('/api/users', methods=['GET'])
@app.route('/api/users/', methods=['GET'])
def list_users():
    """List all users with pagination.
    
    Previously handled by the monolith – now served by this microservice.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)  # Cap at 100
    offset = (page - 1) * per_page

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, created_at, updated_at FROM users_microservice "
                "ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (per_page, offset)
            )
            users = cur.fetchall()

            cur.execute("SELECT COUNT(*) as total FROM users_microservice")
            total = cur.fetchone()['total']

        # Serialize datetime objects
        for user in users:
            user['created_at'] = user['created_at'].isoformat() if user['created_at'] else None
            user['updated_at'] = user['updated_at'].isoformat() if user['updated_at'] else None

        return jsonify({
            "users": users,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------
# Get Single User
# -------------------------------------------------------
@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a single user by ID."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, created_at, updated_at FROM users_microservice WHERE id = %s",
                (user_id,)
            )
            user = cur.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        user['created_at'] = user['created_at'].isoformat() if user['created_at'] else None
        user['updated_at'] = user['updated_at'].isoformat() if user['updated_at'] else None

        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------
# Create User
# -------------------------------------------------------
@app.route('/api/users', methods=['POST'])
@app.route('/api/users/', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = data.get('email')
    name = data.get('name')

    if not email or not name:
        return jsonify({"error": "Both 'email' and 'name' are required"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO users_microservice (email, name, created_at, updated_at)
                   VALUES (%s, %s, NOW(), NOW())
                   RETURNING id, email, name, created_at, updated_at""",
                (email, name)
            )
            user = cur.fetchone()
        conn.commit()

        user['created_at'] = user['created_at'].isoformat() if user['created_at'] else None
        user['updated_at'] = user['updated_at'].isoformat() if user['updated_at'] else None

        return jsonify(user), 201
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": f"User with email '{email}' already exists"}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------
# Update User
# -------------------------------------------------------
@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update an existing user."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    conn = get_db_connection()
    try:
        fields = []
        values = []
        if 'email' in data:
            fields.append("email = %s")
            values.append(data['email'])
        if 'name' in data:
            fields.append("name = %s")
            values.append(data['name'])

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        fields.append("updated_at = NOW()")
        values.append(user_id)

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE users_microservice SET {', '.join(fields)} WHERE id = %s "
                "RETURNING id, email, name, created_at, updated_at",
                values
            )
            user = cur.fetchone()
        conn.commit()

        if not user:
            return jsonify({"error": "User not found"}), 404

        user['created_at'] = user['created_at'].isoformat() if user['created_at'] else None
        user['updated_at'] = user['updated_at'].isoformat() if user['updated_at'] else None

        return jsonify(user), 200
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Email already in use"}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------
# Delete User
# -------------------------------------------------------
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM users_microservice WHERE id = %s RETURNING id",
                (user_id,)
            )
            deleted = cur.fetchone()
        conn.commit()

        if not deleted:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"message": f"User {user_id} deleted"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------
# Application Entry Point
# -------------------------------------------------------
# Initialize DB on startup
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8002))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'false').lower() == 'true')
