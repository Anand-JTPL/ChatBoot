import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
import uuid
import re
import PyPDF2
import docx
from PIL import Image
import base64
from io import BytesIO

load_dotenv()

# ---------- PAGE ----------
st.set_page_config(page_title="ChatGPT Clone", page_icon="🤖", layout="wide")

# ---------- MODEL ----------
model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    streaming=True
)

# ---------- FILE READ ----------
def read_file(uploaded_file):
    if uploaded_file.type == "application/pdf":
        pdf = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
        return text

    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(uploaded_file)
        return "\n".join([p.text for p in doc.paragraphs])

    elif uploaded_file.type == "text/plain":
        return uploaded_file.read().decode("utf-8")

    return ""

# ---------- IMAGE TO BASE64 ----------
def image_to_base64(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

# ---------- SESSION ----------
if "chats" not in st.session_state:
    st.session_state.chats = {}

if "current_chat" not in st.session_state:
    chat_id = str(uuid.uuid4())
    st.session_state.current_chat = chat_id
    st.session_state.chats[chat_id] = {
        "messages": [],
        "memory": {}
    }

# 🔥 IMPORTANT (file reset key)
if "file_key" not in st.session_state:
    st.session_state.file_key = 0

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

# ---------- SIDEBAR ----------
with st.sidebar:
    st.title("💬 ChatGPT")

    if st.button("➕ New Chat"):
        chat_id = str(uuid.uuid4())
        st.session_state.current_chat = chat_id
        st.session_state.chats[chat_id] = {
            "messages": [],
            "memory": {}
        }
        st.rerun()

    st.divider()

    for cid in st.session_state.chats.keys():
        if st.button(f"Chat {cid[:6]}", key=cid):
            st.session_state.current_chat = cid
            st.rerun()

# ---------- CURRENT CHAT ----------
chat_data = st.session_state.chats[st.session_state.current_chat]
messages = chat_data["messages"]
memory = chat_data["memory"]

# ---------- MEMORY ----------
def update_memory(text, memory):
    text_lower = text.lower()

    name_match = re.search(r"(?:my name is|i am|call me)\s+([a-zA-Z]+)", text_lower)
    if name_match:
        memory["name"] = name_match.group(1).capitalize()

    loc_match = re.search(r"(?:i live in|i am from|i stay in)\s+([a-zA-Z\s]+)", text_lower)
    if loc_match:
        memory["location"] = loc_match.group(1).strip().title()

    return memory

# ---------- DISPLAY CHAT ----------
for msg in messages:
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        if isinstance(msg.content, list):
            for part in msg.content:
                if part["type"] == "text":
                    st.markdown(part["text"])
                elif part["type"] == "image_url":
                    st.image(part["image_url"]["url"], width=200)
        else:
            st.markdown(msg.content)

# ---------- INPUT BAR ----------
col1, col2 = st.columns([1, 8])

with col1:
    uploaded_file = st.file_uploader(
        "📎",
        type=["png", "jpg", "jpeg", "pdf", "txt", "docx"],
        label_visibility="collapsed",
        key=f"file_{st.session_state.file_key}"  # 🔥 dynamic key
    )
    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file

with col2:
    user_input = st.chat_input("Send a message...")

# ---------- PREVIEW ----------
if st.session_state.uploaded_file:
    file = st.session_state.uploaded_file

    if file.type.startswith("image"):
        img = Image.open(file)
        st.image(img, width=150, caption="Attached Image")
    else:
        with st.expander("File Preview"):
            st.text(read_file(file)[:500])

# ---------- HANDLE MESSAGE ----------
if user_input:

    memory = update_memory(user_input, memory)

    # ---------- BUILD USER MESSAGE ----------
    if st.session_state.uploaded_file and st.session_state.uploaded_file.type.startswith("image"):
        img = Image.open(st.session_state.uploaded_file)
        b64 = image_to_base64(img)

        content = [
            {"type": "text", "text": user_input},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        ]
        user_msg = HumanMessage(content=content)

    else:
        if st.session_state.uploaded_file:
            file_text = read_file(st.session_state.uploaded_file)
            full_text = f"{user_input}\n\nFile Content:\n{file_text[:2000]}"
        else:
            full_text = user_input

        user_msg = HumanMessage(content=full_text)

    messages.append(user_msg)

    # ---------- SHOW USER ----------
    with st.chat_message("user"):
        if isinstance(user_msg.content, list):
            for part in user_msg.content:
                if part["type"] == "text":
                    st.markdown(part["text"])
                elif part["type"] == "image_url":
                    st.image(part["image_url"]["url"], width=150)
        else:
            st.markdown(user_msg.content)

    # ---------- SYSTEM ----------
    memory_text = ""
    if memory:
        memory_text = "User Info:\n"
        for k, v in memory.items():
            memory_text += f"- {k}: {v}\n"

    system_msg = SystemMessage(
        content=memory_text + "\nYou are a helpful assistant."
    )

    conversation = [system_msg] + messages

    # ---------- RESPONSE ----------
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        stream = model.stream(conversation)

        for chunk in stream:
            if chunk.content:
                full_response += chunk.content
                placeholder.markdown(full_response + "▌")

        placeholder.markdown(full_response)

    messages.append(AIMessage(content=full_response))

    # 🔥 CLEAR INPUT + FILE (FIXED)
    st.session_state.uploaded_file = None
    st.session_state.file_key += 1   # 👈 THIS LINE FIXES UI

    st.rerun()