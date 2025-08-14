import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Assuming config.py is in the same directory or accessible via PYTHONPATH
try:
    from config import SERVICE_ACCOUNT_FILE, FIREBASE_DB_URL
except ImportError:
    logger.critical("config.py not found or SERVICE_ACCOUNT_FILE/FIREBASE_DB_URL missing.")
    # يمكنك اختيار الخروج أو ترك التطبيق يفشل لاحقًا إذا لم يتمكن من التهيئة
    SERVICE_ACCOUNT_FILE = None 
    FIREBASE_DB_URL = None

class Database:
    def __init__(self):
        if not SERVICE_ACCOUNT_FILE or not FIREBASE_DB_URL:
            logger.error("Firebase credentials or DB URL are not configured. Database will not function.")
            self.ref = None
            self.data = self._default_data_structure()
            return

        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': FIREBASE_DB_URL
                })
            self.ref = db.reference('/')
            self.data = self._load_data()
            logger.info("Firebase Database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}", exc_info=True)
            self.ref = None
            self.data = self._default_data_structure() # Fallback to a default structure

    def _default_data_structure(self) -> dict:
        return {
            "users": {},
            "banned_users": [],
            "premium_users": [],
            "groups": {},
            "statistics": {
                "total_messages": 0,
                "total_images": 0,
                "daily_activity": {}, # لتتبع النشاط اليومي بشكل عام
            }
        }

    def _load_data(self) -> dict:
        if not self.ref:
            logger.warning("Firebase reference not available, loading default data structure.")
            return self._default_data_structure()
        try:
            snapshot = self.ref.get()
            if snapshot:
                # ضمان وجود الهياكل الأساسية إذا كانت مفقودة في Firebase
                data = snapshot
                data.setdefault("users", {})
                data.setdefault("banned_users", [])
                data.setdefault("premium_users", [])
                data.setdefault("groups", {})
                data.setdefault("statistics", self._default_data_structure()["statistics"])
                data["statistics"].setdefault("total_messages", 0)
                data["statistics"].setdefault("total_images", 0)
                data["statistics"].setdefault("daily_activity", {})
                return data
        except Exception as e:
            logger.error(f"Failed to load data from Firebase: {e}", exc_info=True)
        return self._default_data_structure()

    def _save_data(self):
        # لا حاجة فعلية لهذه الدالة مع Firebase Realtime DB، لكنها موجودة للتوافق
        # يمكن استخدامها لتحديث self.data من Firebase إذا لزم الأمر
        # self.data = self._load_data()
        pass

    def _get_current_utc_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _get_current_date_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def is_user_exist(self, user_id: int) -> bool:
        return str(user_id) in self.data.get("users", {})

    def add_user(self, user_id: int, username: str, first_name: str):
        if not self.ref: return
        user_id_str = str(user_id)
        if user_id_str not in self.data.get("users", {}):
            user_data = {
                "username": username or "",
                "first_name": first_name or "المستخدم",
                "join_date": self._get_current_utc_iso(),
                "message_count": 0,
                "image_count": 0,
                "daily_image_counts": {}, # تم تغيير الاسم ليكون أوضح
                "last_active": self._get_current_utc_iso()
            }
            try:
                self.ref.child(f"users/{user_id_str}").set(user_data)
                if "users" not in self.data: self.data["users"] = {}
                self.data["users"][user_id_str] = user_data
                logger.info(f"Added new user: {user_id_str}")
            except Exception as e:
                logger.error(f"Failed to add user {user_id_str} to Firebase: {e}", exc_info=True)

    def update_user_activity(self, user_id: int, message_type: str = "text"):
        if not self.ref: return
        
        user_id_str = str(user_id)
        today_str = self._get_current_date_str()

        if user_id_str not in self.data.get("users", {}):
            #  قد ترغب في إضافة المستخدم هنا إذا لم يكن موجودًا، أو تسجيل خطأ
            logger.warning(f"Attempted to update activity for non-existent user: {user_id_str}")
            # self.add_user(user_id, "Unknown", "Unknown") # مثال: إضافة مستخدم غير معروف
            return

        user_data_local = self.data["users"][user_id_str]
        
        # Firebase updates
        fb_updates = {}
        fb_updates[f"users/{user_id_str}/last_active"] = self._get_current_utc_iso()
        
        # Local cache updates
        user_data_local["last_active"] = self._get_current_utc_iso()

        if message_type == "text":
            new_msg_count = user_data_local.get("message_count", 0) + 1
            fb_updates[f"users/{user_id_str}/message_count"] = new_msg_count
            user_data_local["message_count"] = new_msg_count
            
            new_total_msgs = self.data.get("statistics", {}).get("total_messages", 0) + 1
            fb_updates["statistics/total_messages"] = new_total_msgs
            self.data.setdefault("statistics", {})["total_messages"] = new_total_msgs

        elif message_type in ["photo", "image"]:
            new_img_count = user_data_local.get("image_count", 0) + 1
            fb_updates[f"users/{user_id_str}/image_count"] = new_img_count
            user_data_local["image_count"] = new_img_count

            new_total_imgs = self.data.get("statistics", {}).get("total_images", 0) + 1
            fb_updates["statistics/total_images"] = new_total_imgs
            self.data.setdefault("statistics", {})["total_images"] = new_total_imgs
            
            # Daily image count for the user
            user_daily_counts = user_data_local.get("daily_image_counts", {})
            current_daily_img_count = user_daily_counts.get(today_str, 0) + 1
            fb_updates[f"users/{user_id_str}/daily_image_counts/{today_str}"] = current_daily_img_count
            user_daily_counts[today_str] = current_daily_img_count
            user_data_local["daily_image_counts"] = user_daily_counts
        
        # Update daily activity stats (general)
        daily_activity_path = f"statistics/daily_activity/{today_str}"
        current_daily_activity = self.data.get("statistics", {}).get("daily_activity", {}).get(today_str, {"messages": 0, "images": 0, "active_users": {}})
        
        if message_type == "text":
            current_daily_activity["messages"] = current_daily_activity.get("messages", 0) + 1
        elif message_type in ["photo", "image"]:
            current_daily_activity["images"] = current_daily_activity.get("images", 0) + 1
        current_daily_activity.setdefault("active_users", {})[user_id_str] = True # Track unique active users for the day

        fb_updates[daily_activity_path] = current_daily_activity
        self.data.setdefault("statistics", {}).setdefault("daily_activity", {})[today_str] = current_daily_activity

        try:
            self.ref.update(fb_updates)
        except Exception as e:
            logger.error(f"Failed to update user/statistics activity in Firebase: {e}", exc_info=True)

    def get_user_stats(self, user_id: int) -> Optional[dict]:
        return self.data.get("users", {}).get(str(user_id))

    def get_all_users_data(self) -> Dict[str, dict]: # تغيير الاسم ليكون أوضح
        return self.data.get("users", {})

    def get_total_users(self) -> int:
        return len(self.data.get("users", {}))

    def get_daily_activity_stats(self, date_str: Optional[str] = None) -> dict:
        if date_str is None:
            date_str = self._get_current_date_str()
        stats = self.data.get("statistics", {}).get("daily_activity", {}).get(date_str, {"messages": 0, "images": 0, "active_users": {}})
        return {
            "messages": stats.get("messages", 0),
            "images": stats.get("images", 0),
            "unique_active_users": len(stats.get("active_users", {}))
        }

    def get_total_stats(self) -> dict:
        stats = self.data.get("statistics", {})
        return {
            "total_messages": stats.get("total_messages", 0),
            "total_images": stats.get("total_images", 0),
            "total_users": self.get_total_users()
        }

    def get_daily_image_count_for_user(self, user_id: int) -> int: # تم تغيير الاسم ليكون أوضح
        user_id_str = str(user_id)
        today_str = self._get_current_date_str()
        user_data = self.data.get("users", {}).get(user_id_str, {})
        return user_data.get("daily_image_counts", {}).get(today_str, 0)

    def ban_user(self, user_id: int):
        if not self.ref: return
        user_id_str = str(user_id)
        current_banned_users = list(self.data.get("banned_users", [])) #  إنشاء نسخة
        if user_id_str not in current_banned_users:
            current_banned_users.append(user_id_str)
            try:
                self.ref.child("banned_users").set(current_banned_users)
                self.data["banned_users"] = current_banned_users
                logger.info(f"Banned user: {user_id_str}")
            except Exception as e:
                logger.error(f"Failed to ban user {user_id_str} in Firebase: {e}", exc_info=True)

    def unban_user(self, user_id: int):
        if not self.ref: return
        user_id_str = str(user_id)
        current_banned_users = list(self.data.get("banned_users", []))
        if user_id_str in current_banned_users:
            current_banned_users.remove(user_id_str)
            try:
                self.ref.child("banned_users").set(current_banned_users)
                self.data["banned_users"] = current_banned_users
                logger.info(f"Unbanned user: {user_id_str}")
            except Exception as e:
                logger.error(f"Failed to unban user {user_id_str} in Firebase: {e}", exc_info=True)
    
    def get_banned_users_ids(self) -> List[str]: # تغيير الاسم ليكون أوضح
        return self.data.get("banned_users", [])

    def get_user_info(self, user_id: int) -> Optional[dict]: # نفس get_user_stats
        return self.get_user_stats(user_id)

    def is_user_banned(self, user_id: int) -> bool:
        return str(user_id) in self.data.get("banned_users", [])

    def is_user_premium(self, user_id: int) -> bool:
        return str(user_id) in self.data.get("premium_users", [])

    def add_premium_user(self, user_id: int) -> bool:
        if not self.ref: return False
        user_id_str = str(user_id)
        current_premium_users = list(self.data.get("premium_users", []))
        if user_id_str not in current_premium_users:
            current_premium_users.append(user_id_str)
            try:
                self.ref.child("premium_users").set(current_premium_users)
                self.data["premium_users"] = current_premium_users
                logger.info(f"Added premium user: {user_id_str}")
                return True
            except Exception as e:
                logger.error(f"Failed to add premium user {user_id_str} to Firebase: {e}", exc_info=True)
        return False

    def remove_premium_user(self, user_id: int) -> bool:
        if not self.ref: return False
        user_id_str = str(user_id)
        current_premium_users = list(self.data.get("premium_users", []))
        if user_id_str in current_premium_users:
            current_premium_users.remove(user_id_str)
            try:
                self.ref.child("premium_users").set(current_premium_users)
                self.data["premium_users"] = current_premium_users
                logger.info(f"Removed premium user: {user_id_str}")
                return True
            except Exception as e:
                logger.error(f"Failed to remove premium user {user_id_str} from Firebase: {e}", exc_info=True)
        return False
        
    def get_premium_users_ids(self) -> List[str]: # تغيير الاسم ليكون أوضح
        return self.data.get("premium_users", [])

    def get_all_user_ids_for_broadcast(self) -> List[str]: # تغيير الاسم ليكون أوضح
        return list(self.data.get("users", {}).keys())

    # --- Conversation History Methods ---
    def get_conversation_history(self, user_id, limit=10):
        try:
           history_ref = self.ref.child("users").child(str(user_id)).child("history")
           history = (
            history_ref
            .order_by_key()
            .limit_to_last(limit)
            .get()
        )
           if history:
            # ترتيب حسب المفتاح وضمان تنسيق كل رسالة
              sorted_history = [item for _, item in sorted(history.items())]
              validated_history = []
              for msg in sorted_history:
                  if isinstance(msg, dict) and "role" in msg and "parts" in msg:
                    validated_history.append(msg)
              return validated_history
            return []
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []


    def add_message_to_history(self, user_id: int, message: Dict[str, Any]):
        """Adds a message to the user's conversation history."""
        if not self.ref:
            return
        user_id_str = str(user_id)
        try:
            history_ref = self.ref.child(f"conversation_history/{user_id_str}")
            history_ref.push(message)
        except Exception as e:
            logger.error(f"Failed to add message to history for user {user_id_str}: {e}", exc_info=True)

    def clear_conversation_history(self, user_id: int):
        """Clears the conversation history for a specific user."""
        if not self.ref:
            return
        user_id_str = str(user_id)
        try:
            history_ref = self.ref.child(f"conversation_history/{user_id_str}")
            history_ref.delete()
            logger.info(f"Cleared conversation history for user: {user_id_str}")
        except Exception as e:
            logger.error(f"Failed to clear conversation history for user {user_id_str}: {e}", exc_info=True)

    # --- Group Methods ---
    def add_group(self, chat_id: int, title: str, members_count: Optional[int] = None):
        if not self.ref: return
        chat_id_str = str(chat_id)
        
        group_data_local = self.data.get("groups", {}).get(chat_id_str)
        
        current_time = self._get_current_utc_iso()
        
        if not group_data_local: # New group
            group_data = {
                "title": title,
                "join_date": current_time,
                "message_count": 0,
                "last_active": current_time,
                "members_count": members_count
            }
            try:
                self.ref.child(f"groups/{chat_id_str}").set(group_data)
                if "groups" not in self.data: self.data["groups"] = {}
                self.data["groups"][chat_id_str] = group_data
                logger.info(f"Added new group: {title} ({chat_id_str})")
            except Exception as e:
                logger.error(f"Failed to add group {chat_id_str} to Firebase: {e}", exc_info=True)
        else: # Existing group, update info
            updates = {
                f"groups/{chat_id_str}/title": title,
                f"groups/{chat_id_str}/last_active": current_time,
            }
            if members_count is not None:
                 updates[f"groups/{chat_id_str}/members_count"] = members_count
            
            try:
                self.ref.update(updates)
                group_data_local["title"] = title
                group_data_local["last_active"] = current_time
                if members_count is not None:
                    group_data_local["members_count"] = members_count
                logger.info(f"Updated group info: {title} ({chat_id_str})")
            except Exception as e:
                logger.error(f"Failed to update group {chat_id_str} in Firebase: {e}", exc_info=True)


    def get_all_groups(self) -> List[Dict[str, Any]]:
        groups_data = self.data.get("groups", {})
        return [
            {"chat_id": cid, **gdata} for cid, gdata in groups_data.items()
        ]

    def update_group_activity(self, chat_id: int):
        if not self.ref: return
        chat_id_str = str(chat_id)
        
        if chat_id_str in self.data.get("groups", {}):
            group_data_local = self.data["groups"][chat_id_str]
            new_msg_count = group_data_local.get("message_count", 0) + 1
            current_time = self._get_current_utc_iso()
            
            updates = {
                f"groups/{chat_id_str}/message_count": new_msg_count,
                f"groups/{chat_id_str}/last_active": current_time
            }
            try:
                self.ref.update(updates)
                group_data_local["message_count"] = new_msg_count
                group_data_local["last_active"] = current_time
            except Exception as e:
                logger.error(f"Failed to update group activity for {chat_id_str} in Firebase: {e}", exc_info=True)
        else:
            logger.warning(f"Attempted to update activity for non-existent group: {chat_id_str}")


    def update_group_info(self, chat_id: str, info: Dict[str, Any]): # chat_id is already str
        if not self.ref: return
        
        if "groups" not in self.data: self.data["groups"] = {} # Ensure groups key exists

        if chat_id in self.data["groups"]:
            # info might contain title, members_count, etc.
            updates_for_fb = {f"groups/{chat_id}/{key}": value for key, value in info.items()}
            try:
                self.ref.update(updates_for_fb)
                self.data["groups"][chat_id].update(info) # Update local cache
                logger.info(f"Updated group info for {chat_id} with: {info}")
            except Exception as e:
                logger.error(f"Failed to update group info for {chat_id} in Firebase: {e}", exc_info=True)
        else:
            # If group not in local cache but we're asked to update, it's a new group
            # Or you might decide to log a warning if an update is for a non-existent group.
            # For now, let's assume it could be a new group if info contains 'title'.
            if 'title' in info:
                self.add_group(int(chat_id), info['title'], info.get('members_count'))
            else:
                logger.warning(f"Attempted to update info for non-existent group {chat_id} without title.")


    def remove_group(self, chat_id: str): # chat_id is already str
        if not self.ref: return
        
        if "groups" in self.data and chat_id in self.data["groups"]:
            try:
                self.ref.child(f"groups/{chat_id}").delete()
                del self.data["groups"][chat_id] # Remove from local cache
                logger.info(f"Removed group: {chat_id}")
            except Exception as e:
                logger.error(f"Failed to remove group {chat_id} from Firebase: {e}", exc_info=True)

    def search_groups(self, query: str) -> List[Dict[str, Any]]:
        results = []
        query_lower = query.lower()
        for chat_id_str, group_data in self.data.get("groups", {}).items():
            title = group_data.get("title", "").lower()
            if query_lower in title or query_lower in chat_id_str:
                results.append({"chat_id": chat_id_str, **group_data})
        return results

    def cleanup_inactive_groups(self, inactivity_days_threshold: int = 30) -> tuple[int, list[Any]]:
        # هذا مثال، يمكنك تعديل منطق "عدم النشاط"
        if not self.ref: return 0, []
        
        removed_count = 0
        removed_groups_info = []
        
        #  ملاحظة: Firebase لا يدعم الاستعلامات المعقدة مثل "أقدم من X يومًا ولم يكن هناك نشاط" بسهولة.
        #  عادةً ما يتم هذا النوع من التنظيف من جانب العميل أو باستخدام Cloud Functions.
        #  هنا، سنعتمد على 'last_active' و 'message_count'.
        
        #  مثال بسيط: حذف المجموعات التي لم يكن لديها رسائل على الإطلاق وانضمت منذ أكثر من X يوم
        #  أو لم تكن نشطة منذ X يوم.
        
        groups_to_check = list(self.data.get("groups", {}).items()) # نسخة للالتفاف الآمن
        
        for chat_id_str, group_data in groups_to_check:
            is_inactive = False
            
            # المعيار 1: لا توجد رسائل + قديمة
            if group_data.get("message_count", 0) == 0:
                join_date_str = group_data.get("join_date")
                if join_date_str:
                    try:
                        join_date = datetime.fromisoformat(join_date_str.replace("Z", "+00:00")) # تأكد من توافق ISO
                        if (datetime.now(timezone.utc) - join_date).days > inactivity_days_threshold:
                            is_inactive = True
                    except ValueError:
                        logger.warning(f"Could not parse join_date for group {chat_id_str}: {join_date_str}")

            # المعيار 2: غير نشطة لفترة طويلة (بغض النظر عن عدد الرسائل)
            if not is_inactive: # تحقق فقط إذا لم تكن غير نشطة بالفعل
                last_active_str = group_data.get("last_active")
                if last_active_str:
                    try:
                        last_active_date = datetime.fromisoformat(last_active_str.replace("Z", "+00:00"))
                        if (datetime.now(timezone.utc) - last_active_date).days > inactivity_days_threshold:
                            is_inactive = True
                    except ValueError:
                         logger.warning(f"Could not parse last_active for group {chat_id_str}: {last_active_str}")
            
            if is_inactive:
                try:
                    self.ref.child(f"groups/{chat_id_str}").delete()
                    if chat_id_str in self.data.get("groups", {}): # تأكد مرة أخرى قبل الحذف محليًا
                        del self.data["groups"][chat_id_str]
                    removed_groups_info.append({"chat_id": chat_id_str, "title": group_data.get("title", "N/A")})
                    removed_count += 1
                    logger.info(f"Cleaned up inactive group: {group_data.get('title', 'N/A')} ({chat_id_str})")
                except Exception as e:
                    logger.error(f"Failed to remove inactive group {chat_id_str} from Firebase: {e}", exc_info=True)

        return removed_count, removed_groups_info


    # --- Premium User Image Limit (مثال للتحكم في حد الصور) ---
    def can_user_send_image(self, user_id: int, premium_image_limit: int = 999, free_user_image_limit: int = 7) -> bool:
        if self.is_user_premium(user_id):
            # المستخدمون المميزون قد يكون لديهم حد أعلى أو لا يوجد حد
            # هذا يعتمد على منطق عملك. هنا نفترض أن لديهم حدًا أعلى.
            return self.get_daily_image_count_for_user(user_id) < premium_image_limit
        else:
            return self.get_daily_image_count_for_user(user_id) < free_user_image_limit

    # لا حاجة لـ increment_daily_image_count بشكل منفصل إذا تم تضمينه في update_user_activity
    # ولكن إذا كنت تريدها منفصلة:
    # def increment_daily_image_count(self, user_id: int):
    #     # هذا المنطق مدمج الآن في update_user_activity
    #     # إذا كنت ترغب في فصله، تأكد من تحديث Firebase والكاش المحلي
    #     pass
