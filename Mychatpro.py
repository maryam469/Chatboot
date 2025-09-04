import streamlit as st
import json, os
from datetime import datetime, timedelta
from groq import Groq
import pytz
import re


st.markdown("""
    <style>
    .chat-bubble {
        transition: all 0.2s ease-in-out;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.1);
    }
   .chat-bubble:hover {
    transform: scale(1.03);
    box-shadow: 0px 4px 12px rgba(255, 105, 180, 0.4); /* Soft pink glow */
    cursor: pointer;
}
    </style>
""", unsafe_allow_html=True)



# --- CONFIG ---
DATA_DIR = "chat_data"
os.makedirs(DATA_DIR, exist_ok=True)
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
TZ = pytz.timezone("Asia/Karachi")

# --- HELPERS ---
def chat_file(user1, user2):
    users = "_".join(sorted([user1, user2]))
    return os.path.join(DATA_DIR, f"{users}.json")

def parse_ts_to_aware(ts_str: str):
    """Parse timestamps saved as strings into timezone-aware datetimes."""
    fmts = ["%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    for fmt in fmts:
        try:
            naive = datetime.strptime(ts_str, fmt)
            return TZ.localize(naive)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            return TZ.localize(dt)
        return dt.astimezone(TZ)
    except Exception:
        return datetime.now(TZ)

def msg_time_aware(m):
    """Get a timezone-aware datetime from a message dict."""
    if "ts" in m:
        return datetime.fromtimestamp(m["ts"], TZ)
    return parse_ts_to_aware(m.get("timestamp", ""))

def load_messages(u1, u2):
    path = chat_file(u1, u2)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                messages = json.load(f)
        except json.JSONDecodeError:
            st.warning("⚠️ Chat file is corrupted or unreadable. Starting fresh.")
            return []

        cutoff = datetime.now(TZ) - timedelta(days=2)
        filtered, changed = [], False
        for m in messages:
            msg_dt = msg_time_aware(m)
            if msg_dt >= cutoff:
                filtered.append(m)
            else:
                changed = True
        if changed:
            save_messages(u1, u2, filtered)
        return filtered
    return []

def save_messages(u1, u2, messages):
    path = chat_file(u1, u2)
    with open(path, "w") as f:
        json.dump(messages, f, indent=2)

def get_timestamp():
    pk_time = datetime.now(TZ)
    return pk_time.strftime("%Y-%m-%d %I:%M %p")

def get_ai_reply(prompt):
    try:
        client = Groq(api_key=GROQ_API_KEY)
        res = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"[AI Error]: {e}"

def make_links_clickable(text):
    url_pattern = re.compile(r"(https?://[^\s]+)")
    return url_pattern.sub(r'<a href="\1" target="_blank" style="color:#007AFF;text-decoration:none;">\1</a>', text)

def render_message_bubble(sender, message, timestamp, current_user, is_read=False):
    # ✅ Alignment
    align = "right" if sender == current_user else "left"

    # ✅ Cute & Cozy Colors
    if sender == current_user:
        bubble_color = "#E6E6FA"  # Lavender
        text_color = "#2D2D2D"    # Dark Gray
        border_radius = "20px 20px 5px 20px"
    else:
        bubble_color = "#FFFACD"  # Soft Light Yellow for warmth
        text_color = "#2D2D2D"
        border_radius = "20px 20px 20px 5px"

    # ✅ Read ticks
    ticks = "<span style='color:#34B7F1;'>✔✔</span>" if (sender == current_user and is_read) else "<span style='color:gray;'>✔</span>" if sender == current_user else ""

    # ✅ HTML Bubble
    html = f"""
    <div style="display:flex; justify-content:{align}; margin:6px 0;">
        <div class="chat-bubble" style="
            background:{bubble_color};
            padding:12px 16px;
            border-radius:{border_radius};
            max-width:70%;
            font-family:'Segoe UI', sans-serif;
            font-size:15px;
            line-height:1.4;
            color:{text_color};
            box-shadow: 0px 1px 3px rgba(0,0,0,0.1);
            transition: all 0.2s ease-in-out;
        ">
            <b style="color:{text_color};">{sender.capitalize()}</b><br>{message}
            <div style="font-size:11px; color:gray; text-align:right;">🕒 {timestamp} {ticks}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)



# --- LOGIN SYSTEM ---
def load_users_from_secrets():
    return st.secrets["users"]

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login to MyChatPro")
    USER_CREDENTIALS = load_users_from_secrets()
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in USER_CREDENTIALS and password == USER_CREDENTIALS[username]:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.partner = [u for u in USER_CREDENTIALS if u != username][0]
            st.success("✅ Login successful!")
            st.stop()
        else:
            st.error("❌ Invalid username or password")
    st.stop()

# --- CHAT UI ---
user = st.session_state.username
partner = st.session_state.partner

st.sidebar.title("👥 MyChatPro")
st.sidebar.success(f"Logged in as: {user}")
st.sidebar.info(f"Chatting with: {partner}")
st.title("💬 MyChatPro")

messages = load_messages(user, partner)

for msg in messages:
    if msg["sender"] == partner and not msg.get("read", False):
        msg["read"] = True
save_messages(user, partner, messages)

chat_container = st.container()
with chat_container:
    for m in messages:
        render_message_bubble(
            sender=m["sender"],
            message=m["text"],
            timestamp=m["timestamp"],
            current_user=user,
            is_read=m.get("read", False)
        )

if st.button("🔄 Refresh Chat"):
    st.rerun()

user_input = st.chat_input("Type your message...")
if user_input:
    now_aware = datetime.now(TZ)
    messages.append({
        "sender": user,
        "text": user_input,
        "timestamp": now_aware.strftime("%Y-%m-%d %I:%M %p"),
        "ts": int(now_aware.timestamp()),  # Future-proof field
        "read": False
    })
    save_messages(user, partner, messages)
    st.rerun()

if st.button("🗑️ Delete Chat"):
    chat_path = chat_file(user, partner)
    if os.path.exists(chat_path):
        os.remove(chat_path)
        st.success("Chat deleted!")
        st.rerun()
    else:
        st.warning("⚠️ No chat found to delete.")
