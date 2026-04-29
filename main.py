import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
import PyPDF2
import docx
from PIL import Image
import base64
from io import BytesIO
import re   # for pattern matching

load_dotenv()

# ---------- FILE & IMAGE HELPERS (unchanged) ----------
def read_file(uploaded_file):
    # ... same as before ...
    pass

def image_to_base64(image):
    # ... same ...
    pass

# ---------- CUSTOM CSS (unchanged) ----------
st.markdown("""...""", unsafe_allow_html=True)

# ---------- SIDEBAR (unchanged) ----------
with st.sidebar:
    st.header("💰 Cost Control")
    max_tokens = st.slider("Max response length (tokens)", 100, 2000, 500)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7)
    st.caption("💡 Tip: Keep max tokens 500 or less to save cost")

# ---------- MAIN APP ----------
def main():
    st.set_page_config(page_title="ChatBoot", page_icon="🤖")
    st.title("🤖 ChatBoot")

    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=True
    )

    # Session state
    if "messages" not in st.session_state:
        st.session_state.messages = [SystemMessage(content="You are a helpful assistant. Keep answers concise.")]
    if "uploaded_file" not in st.session_state:
        st.session_state.uploaded_file = None
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0
    if "user_memory" not in st.session_state:
        st.session_state.user_memory = {}   # e.g., {"name": "Anand", "age": 25}

    # Display chat history (unchanged)
    for msg in st.session_state.messages:
        if isinstance(msg, SystemMessage):
            continue
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

    # ---------- FIXED BOTTOM INPUT BAR (unchanged) ----------
    with st.container():
        st.markdown('<div class="fixed-input">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([0.6, 7, 1])
        with col1:
            uploaded_file = st.file_uploader(
                "📎",
                type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
                label_visibility="collapsed",
                key=f"attach_{st.session_state.input_key}"
            )
            if uploaded_file is not None:
                st.session_state.uploaded_file = uploaded_file
        with col2:
            user_input = st.text_input(
                "Message",
                placeholder="Send a message...",
                label_visibility="collapsed",
                key=f"input_{st.session_state.input_key}"
            )
        with col3:
            send = st.button("➤", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Preview attachment (unchanged)
    if st.session_state.uploaded_file:
        if st.session_state.uploaded_file.type.startswith("image"):
            img = Image.open(st.session_state.uploaded_file)
            st.image(img, width=150, caption="Attached image")
        else:
            with st.expander("Attached file preview"):
                st.text(read_file(st.session_state.uploaded_file)[:500])

    # ---------- HANDLE SEND (with memory extraction) ----------
    if send and user_input:
        # ----- EXTRACT NAME / AGE FROM USER INPUT -----
        def update_memory_from_input(text, memory):
            # Name: "my name is Anand", "i am Anand", "call me Anand"
            name_match = re.search(r"(?:my name is|i am|call me)\s+([A-Za-z]+)", text, re.IGNORECASE)
            if name_match:
                memory["name"] = name_match.group(1)
            # Age: "i am 25 years old", "age 25", "25 years old"
            age_match = re.search(r"(?:i am|age)\s+(\d+)\s*(?:years old)?", text, re.IGNORECASE)
            if age_match:
                memory["age"] = int(age_match.group(1))
            # Also handle "my age is 30"
            age2_match = re.search(r"my age is\s+(\d+)", text, re.IGNORECASE)
            if age2_match:
                memory["age"] = int(age2_match.group(1))
            return memory

        st.session_state.user_memory = update_memory_from_input(user_input, st.session_state.user_memory)

        # ----- BUILD SYSTEM MESSAGE WITH MEMORY -----
        memory_text = ""
        if st.session_state.user_memory:
            memory_text = "User facts you MUST remember:\n"
            for k, v in st.session_state.user_memory.items():
                memory_text += f"- {k}: {v}\n"
            memory_text += "\nAnswer based on these facts when asked about the user.\n"
        system_content = memory_text + "You are a helpful assistant. Keep answers concise."
        system_msg = SystemMessage(content=system_content)

        # Build user message (vision if image) – unchanged
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
                full_text = f"File content:\n{file_text}\n\nUser: {user_input}"
            else:
                full_text = user_input
            user_msg = HumanMessage(content=full_text)

        # Save and display user message
        st.session_state.messages.append(user_msg)
        with st.chat_message("user"):
            if isinstance(user_msg.content, list):
                for part in user_msg.content:
                    if part["type"] == "text":
                        st.markdown(part["text"])
                    elif part["type"] == "image_url":
                        st.image(part["image_url"]["url"], width=150)
            else:
                st.markdown(user_msg.content)

        # Stream assistant response USING MEMORY SYSTEM MESSAGE
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            # Replace old system message with new one that contains memory
            stream = model.stream([system_msg, user_msg])
            for chunk in stream:
                if chunk.content:
                    full_response += chunk.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        st.session_state.messages.append(AIMessage(content=full_response))

        # Clear input & attachment
        st.session_state.uploaded_file = None
        st.session_state.input_key += 1
        st.rerun()

if __name__ == "__main__":
    main()