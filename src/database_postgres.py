import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging
import os

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, postgres_url: str = None):
        """Initialize PostgreSQL database connection."""
        self.postgres_url = postgres_url or os.getenv("POSTGRES_URL")
        
        if not self.postgres_url:
            logger.error("PostgreSQL URL not provided. Database will not function.")
            self.pool = None
            return
        
        try:
            # Create connection pool
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,  # min and max connections
                self.postgres_url
            )
            
            if self.pool:
                logger.info("PostgreSQL connection pool created successfully.")
                self._init_tables()
                self._init_default_prompt()
            else:
                logger.error("Failed to create PostgreSQL connection pool.")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}", exc_info=True)
            self.pool = None

    def _get_connection(self):
        """Get a connection from the pool."""
        if not self.pool:
            raise Exception("Database pool not initialized")
        return self.pool.getconn()

    def _return_connection(self, conn):
        """Return a connection to the pool."""
        if self.pool and conn:
            self.pool.putconn(conn)

    def _init_tables(self):
        """Initialize all database tables."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    join_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    image_count INTEGER DEFAULT 0,
                    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Banned users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id BIGINT PRIMARY KEY,
                    banned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Premium users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS premium_users (
                    user_id BIGINT PRIMARY KEY,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Groups table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id BIGINT PRIMARY KEY,
                    title VARCHAR(500),
                    join_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    members_count INTEGER,
                    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Daily image counts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_image_counts (
                    user_id BIGINT,
                    date DATE,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
            """)
            
            # Statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    key VARCHAR(100) PRIMARY KEY,
                    value BIGINT DEFAULT 0,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Initialize statistics keys if not exist
            cursor.execute("""
                INSERT INTO statistics (key, value) VALUES ('total_messages', 0)
                ON CONFLICT (key) DO NOTHING
            """)
            cursor.execute("""
                INSERT INTO statistics (key, value) VALUES ('total_images', 0)
                ON CONFLICT (key) DO NOTHING
            """)
            
            # Prompts table (NEW)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Bot settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("PostgreSQL Database tables initialized successfully.")
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to initialize tables: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def _init_default_prompt(self):
        """Initialize default prompt if not exists."""
        default_prompt = """ملاحظة مرفقة مع الرسالة: كن ودودًا وحنونًا في تواصلك مع المستخدمين، 
وتحدث بأسلوب طبيعي يجعلهم يشعرون بالراحة والحب . 
جعل ردودك ممتعة، مرنة ومليئة بالحيوية، مع لمسة شخصية مميزة. 
لا تذكر اسمي إلا إذا طُلب منك ذلك. 
استخدم لغة طبيعية وواضحة، ولا تطيل الكلام بلا داعٍ.  
اسمك على تليجرام هو أبو راس، وتم ربطك عبر بوت تليجرام من قِبل وهيب الشرعبي من اليمن 🇾🇪. 
تذكر أن جنسيتك يمنية وأن ثقافتك جزء من شخصيتك. 
عند طلب تقديم معلومات، كن عاقلًا وواقعيًا، مع توضيح المفيد فقط. 
استخدم الإيموجيات بشكل متناسق لإضفاء المرح والتفاعل، مثل .

━━━━━━━━━━━━━━
رسالة المستخدم:
{user_message}

💬 أجب بأسلوب ودود، مرح، وواقعي. أضف لمسة شخصية تجعل المستخدم يريد التفاعل معك دائمًا!"""
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if default prompt exists
            cursor.execute("SELECT id FROM prompts WHERE name = 'default'")
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO prompts (name, content, is_active)
                    VALUES ('default', %s, TRUE)
                """, (default_prompt,))
                conn.commit()
                logger.info("Default prompt initialized.")
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to initialize default prompt: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def _get_current_utc_iso(self) -> str:
        """Get current UTC time in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def _get_current_date_str(self) -> str:
        """Get current date string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ==================== User Methods ====================
    
    def is_user_exist(self, user_id: int) -> bool:
        """Check if user exists in database."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking user existence: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def add_user(self, user_id: int, username: str, first_name: str):
        """Add a new user to database."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, join_date, last_active)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_active = EXCLUDED.last_active
            """, (user_id, username or "", first_name or "المستخدم", 
                  self._get_current_utc_iso(), self._get_current_utc_iso()))
            
            conn.commit()
            logger.info(f"Added/Updated user: {user_id}")
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to add user {user_id}: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def update_user_activity(self, user_id: int, message_type: str = "text"):
        """Update user activity and statistics."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Update user last_active
            cursor.execute("""
                UPDATE users SET last_active = %s WHERE user_id = %s
            """, (self._get_current_utc_iso(), user_id))
            
            if message_type == "text":
                # Update user message count
                cursor.execute("""
                    UPDATE users SET message_count = message_count + 1 WHERE user_id = %s
                """, (user_id,))
                
                # Update total messages statistics
                cursor.execute("""
                    UPDATE statistics SET value = value + 1, updated_at = %s WHERE key = 'total_messages'
                """, (self._get_current_utc_iso(),))
                
            elif message_type in ["photo", "image"]:
                # Update user image count
                cursor.execute("""
                    UPDATE users SET image_count = image_count + 1 WHERE user_id = %s
                """, (user_id,))
                
                # Update total images statistics
                cursor.execute("""
                    UPDATE statistics SET value = value + 1, updated_at = %s WHERE key = 'total_images'
                """, (self._get_current_utc_iso(),))
                
                # Update daily image count
                today = self._get_current_date_str()
                cursor.execute("""
                    INSERT INTO daily_image_counts (user_id, date, count)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (user_id, date) DO UPDATE SET count = daily_image_counts.count + 1
                """, (user_id, today))
            
            conn.commit()
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to update user activity: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_user_stats(self, user_id: int) -> Optional[dict]:
        """Get user statistics."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT user_id, username, first_name, join_date, message_count, 
                       image_count, last_active
                FROM users WHERE user_id = %s
            """, (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_all_users_data(self) -> Dict[str, dict]:
        """Get all users data."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT user_id, username, first_name, join_date, message_count, 
                       image_count, last_active
                FROM users
            """)
            results = cursor.fetchall()
            return {str(row['user_id']): dict(row) for row in results}
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_total_users(self) -> int:
        """Get total number of users."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting total users: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_daily_image_count_for_user(self, user_id: int) -> int:
        """Get daily image count for a user."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            today = self._get_current_date_str()
            cursor.execute("""
                SELECT count FROM daily_image_counts WHERE user_id = %s AND date = %s
            """, (user_id, today))
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting daily image count: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_user_info(self, user_id: int) -> Optional[dict]:
        """Get user info (alias for get_user_stats)."""
        return self.get_user_stats(user_id)

    def get_all_user_ids_for_broadcast(self) -> List[str]:
        """Get all user IDs for broadcasting."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            return [str(row[0]) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting user IDs: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    # ==================== Ban/Premium Methods ====================
    
    def ban_user(self, user_id: int):
        """Ban a user."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO banned_users (user_id) VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id,))
            conn.commit()
            logger.info(f"Banned user: {user_id}")
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to ban user {user_id}: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def unban_user(self, user_id: int):
        """Unban a user."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM banned_users WHERE user_id = %s", (user_id,))
            conn.commit()
            logger.info(f"Unbanned user: {user_id}")
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to unban user {user_id}: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM banned_users WHERE user_id = %s", (user_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking ban status: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_banned_users_ids(self) -> List[str]:
        """Get list of banned user IDs."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM banned_users")
            return [str(row[0]) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting banned users: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def is_user_premium(self, user_id: int) -> bool:
        """Check if user is premium."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM premium_users WHERE user_id = %s", (user_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking premium status: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def add_premium_user(self, user_id: int) -> bool:
        """Add a premium user."""
        if not self.pool:
            return False
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO premium_users (user_id) VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id,))
            conn.commit()
            logger.info(f"Added premium user: {user_id}")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to add premium user {user_id}: {e}", exc_info=True)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def remove_premium_user(self, user_id: int) -> bool:
        """Remove a premium user."""
        if not self.pool:
            return False
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM premium_users WHERE user_id = %s", (user_id,))
            conn.commit()
            logger.info(f"Removed premium user: {user_id}")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to remove premium user {user_id}: {e}", exc_info=True)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_premium_users_ids(self) -> List[str]:
        """Get list of premium user IDs."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM premium_users")
            return [str(row[0]) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting premium users: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    # ==================== Group Methods ====================
    
    def add_group(self, chat_id: int, title: str, members_count: Optional[int] = None):
        """Add or update a group."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            current_time = self._get_current_utc_iso()
            cursor.execute("""
                INSERT INTO groups (chat_id, title, join_date, last_active, members_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    last_active = EXCLUDED.last_active,
                    members_count = EXCLUDED.members_count
            """, (chat_id, title, current_time, current_time, members_count))
            
            conn.commit()
            logger.info(f"Added/Updated group: {title} ({chat_id})")
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to add group {chat_id}: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Get all groups."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT chat_id, title, join_date, message_count, members_count, last_active
                FROM groups ORDER BY last_active DESC
            """)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting groups: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def update_group_activity(self, chat_id: int):
        """Update group activity."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE groups SET 
                    message_count = message_count + 1,
                    last_active = %s
                WHERE chat_id = %s
            """, (self._get_current_utc_iso(), chat_id))
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to update group activity: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def update_group_info(self, chat_id: str, info: Dict[str, Any]):
        """Update group information."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build update query dynamically
            fields = []
            values = []
            for key, value in info.items():
                if key in ['title', 'members_count']:
                    fields.append(f"{key} = %s")
                    values.append(value)
            
            if fields:
                values.append(int(chat_id))
                query = f"UPDATE groups SET {', '.join(fields)} WHERE chat_id = %s"
                cursor.execute(query, tuple(values))
                conn.commit()
                logger.info(f"Updated group info for {chat_id}")
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to update group info: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def remove_group(self, chat_id: str):
        """Remove a group."""
        if not self.pool:
            return
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM groups WHERE chat_id = %s", (int(chat_id),))
            conn.commit()
            logger.info(f"Removed group: {chat_id}")
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to remove group: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def search_groups(self, query: str) -> List[Dict[str, Any]]:
        """Search groups by title or chat_id."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT chat_id, title, join_date, message_count, members_count, last_active
                FROM groups
                WHERE LOWER(title) LIKE %s OR CAST(chat_id AS TEXT) LIKE %s
            """, (f'%{query.lower()}%', f'%{query}%'))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error searching groups: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def cleanup_inactive_groups(self, inactivity_days_threshold: int = 30) -> tuple:
        """Clean up inactive groups."""
        if not self.pool:
            return 0, []
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get inactive groups
            cursor.execute("""
                SELECT chat_id, title FROM groups
                WHERE (message_count = 0 AND join_date < NOW() - INTERVAL '%s days')
                   OR (last_active < NOW() - INTERVAL '%s days')
            """, (inactivity_days_threshold, inactivity_days_threshold))
            
            inactive_groups = cursor.fetchall()
            removed_count = len(inactive_groups)
            removed_groups_info = [{"chat_id": str(g['chat_id']), "title": g['title']} for g in inactive_groups]
            
            # Delete inactive groups
            if inactive_groups:
                chat_ids = [g['chat_id'] for g in inactive_groups]
                cursor.execute("""
                    DELETE FROM groups WHERE chat_id = ANY(%s)
                """, (chat_ids,))
                conn.commit()
                logger.info(f"Cleaned up {removed_count} inactive groups")
            
            return removed_count, removed_groups_info
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to cleanup groups: {e}", exc_info=True)
            return 0, []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    # ==================== Statistics Methods ====================
    
    def get_total_stats(self) -> dict:
        """Get total statistics."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            stats = {}
            cursor.execute("SELECT value FROM statistics WHERE key = 'total_messages'")
            result = cursor.fetchone()
            stats['total_messages'] = result[0] if result else 0
            
            cursor.execute("SELECT value FROM statistics WHERE key = 'total_images'")
            result = cursor.fetchone()
            stats['total_images'] = result[0] if result else 0
            
            stats['total_users'] = self.get_total_users()
            
            return stats
        except Exception as e:
            logger.error(f"Error getting total stats: {e}")
            return {'total_messages': 0, 'total_images': 0, 'total_users': 0}
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_daily_activity_stats(self, date_str: Optional[str] = None) -> dict:
        """Get daily activity statistics."""
        if date_str is None:
            date_str = self._get_current_date_str()
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Count daily images
            cursor.execute("""
                SELECT COALESCE(SUM(count), 0) FROM daily_image_counts WHERE date = %s
            """, (date_str,))
            images = cursor.fetchone()[0]
            
            # Note: We don't have daily message tracking yet, so we return 0
            # You can add a similar table for daily messages if needed
            
            return {
                'messages': 0,  # Would need daily_message_counts table
                'images': images,
                'unique_active_users': 0  # Would need tracking
            }
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return {'messages': 0, 'images': 0, 'unique_active_users': 0}
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    # ==================== Prompt Methods (NEW) ====================
    
    def get_active_prompt(self) -> str:
        """Get the active prompt."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT content FROM prompts WHERE is_active = TRUE ORDER BY updated_at DESC LIMIT 1
            """)
            result = cursor.fetchone()
            return result[0] if result else self._get_default_prompt_text()
        except Exception as e:
            logger.error(f"Error getting active prompt: {e}")
            return self._get_default_prompt_text()
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def _get_default_prompt_text(self) -> str:
        """Get default prompt text."""
        return """ملاحظة مرفقة مع الرسالة: كن ودودًا وحنونًا في تواصلك مع المستخدمين، 
وتحدث بأسلوب طبيعي يجعلهم يشعرون بالراحة والحب . 
جعل ردودك ممتعة، مرنة ومليئة بالحيوية، مع لمسة شخصية مميزة. 
لا تذكر اسمي إلا إذا طُلب منك ذلك. 
استخدم لغة طبيعية وواضحة، ولا تطيل الكلام بلا داعٍ.  
اسمك على تليجرام هو أبو راس، وتم ربطك عبر بوت تليجرام من قِبل وهيب الشرعبي من اليمن 🇾🇪. 
تذكر أن جنسيتك يمنية وأن ثقافتك جزء من شخصيتك. 
عند طلب تقديم معلومات، كن عاقلًا وواقعيًا، مع توضيح المفيد فقط. 
استخدم الإيموجيات بشكل متناسق لإضفاء المرح والتفاعل، مثل .

━━━━━━━━━━━━━━
رسالة المستخدم:
{user_message}

💬 أجب بأسلوب ودود، مرح، وواقعي. أضف لمسة شخصية تجعل المستخدم يريد التفاعل معك دائمًا!"""

    def update_prompt(self, name: str, content: str) -> bool:
        """Update or create a prompt."""
        if not self.pool:
            return False
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Deactivate all prompts first
            cursor.execute("UPDATE prompts SET is_active = FALSE")
            
            # Insert or update the prompt
            cursor.execute("""
                INSERT INTO prompts (name, content, is_active, updated_at)
                VALUES (%s, %s, TRUE, %s)
                ON CONFLICT (name) DO UPDATE SET
                    content = EXCLUDED.content,
                    is_active = TRUE,
                    updated_at = EXCLUDED.updated_at
            """, (name, content, self._get_current_utc_iso()))
            
            conn.commit()
            logger.info(f"Updated prompt: {name}")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to update prompt: {e}", exc_info=True)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def reset_to_default_prompt(self) -> bool:
        """Reset to default prompt."""
        if not self.pool:
            return False
        
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Deactivate all prompts
            cursor.execute("UPDATE prompts SET is_active = FALSE")
            
            # Activate default prompt
            cursor.execute("UPDATE prompts SET is_active = TRUE WHERE name = 'default'")
            
            conn.commit()
            logger.info("Reset to default prompt")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to reset prompt: {e}", exc_info=True)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    # ==================== Utility Methods ====================
    
    def can_user_send_image(self, user_id: int, premium_image_limit: int = 999, 
                           free_user_image_limit: int = 7) -> bool:
        """Check if user can send image based on daily limit."""
        if self.is_user_premium(user_id):
            return self.get_daily_image_count_for_user(user_id) < premium_image_limit
        else:
            return self.get_daily_image_count_for_user(user_id) < free_user_image_limit

    def close(self):
        """Close all database connections."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connections closed.")
