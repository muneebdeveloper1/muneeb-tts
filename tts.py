import streamlit as st
import asyncio
import edge_tts
import aiohttp
import pdfplumber
import pandas as pd
from docx import Document
from pathlib import Path
import time
import os

# Auto-detection imports
import langdetect
from langdetect import detect, LangDetectException

# ---------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------
st.set_page_config(
    page_title="WordWave",
    page_icon="🎙️",
    layout="wide"
)

# ---------------------------------------------------
# 🔑 OWNER UNLOCK GATEWAY (Temporary Shutdown)
# ---------------------------------------------------
if "app_unlocked" not in st.session_state:
    st.session_state["app_unlocked"] = False

if not st.session_state["app_unlocked"]:
    st.error("🛑 Service Temporarily Suspended")
    st.info(
        "### **This application has been temporarily shut down by the owner.**\n\n"
        "Free promotional access for this resource has expired and the hosting limits "
        "have been consumed.\n\n"
        "To request access restoration, please contact **Muneeb** directly."
    )
    
    secret_key = st.text_input("🔓 Developer Override Access:", type="password")
    if st.button("Verify Admin Access"):
        if secret_key == "Ilovemuh@mm@d": 
            st.session_state["app_unlocked"] = True
            st.success("✅ Access Granted! Loading your pipeline...")
            st.rerun()
        else:
            st.error("❌ Incorrect Admin Passkey.")
    st.stop()

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
col1, col2 = st.columns([1, 8])

with col1:
    logo_path = Path("logo.png")
    if logo_path.exists():
        st.image(str(logo_path), width=120)
    else:
        st.write("🎙️")

with col2:
    st.title("WordWave")
    st.caption("Text-to-speech and audiobook generator (Developer Mode Active)")

# ---------------------------------------------------
# LOAD VOICES
# ---------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_voices():
    async def get_voices():
        return await edge_tts.list_voices()
    return asyncio.run(get_voices())

try:
    with st.spinner("Loading voices..."):
        voices = load_voices()
except Exception as e:
    st.error(f"Could not load voices: {type(e).__name__}")
    st.stop()

if not voices:
    st.error("No voices are currently available.")
    st.stop()

# ---------------------------------------------------
# LANGUAGE MAP
# ---------------------------------------------------
LANGUAGE_MAP = {
    "en-US": "English (United States)", "en-GB": "English (United Kingdom)",
    "en-AU": "English (Australia)", "en-CA": "English (Canada)", "en-IN": "English (India)",
    "ur-PK": "Urdu (Pakistan)", "hi-IN": "Hindi (India)", "ar-SA": "Arabic (Saudi Arabia)",
    "tr-TR": "Turkish (Turkey)", "fr-FR": "French (France)", "de-DE": "German (Germany)",
    "es-ES": "Spanish (Spain)", "it-IT": "Italian (Italy)", "pt-BR": "Portuguese (Brazil)",
    "ru-RU": "Russian (Russia)", "ja-JP": "Japanese (Japan)", "ko-KR": "Korean (South Korea)",
    "zh-CN": "Chinese (China)", "bn-BD": "Bengali (Bangladesh)", "fa-IR": "Persian (Iran)",
    "id-ID": "Indonesian (Indonesia)", "ms-MY": "Malay (Malaysia)", "nl-NL": "Dutch (Netherlands)",
    "pl-PL": "Polish (Poland)", "sv-SE": "Swedish (Sweden)", "ta-IN": "Tamil (India)",
    "te-IN": "Telugu (India)", "th-TH": "Thai (Thailand)", "uk-UA": "Ukrainian (Ukraine)",
    "vi-VN": "Vietnamese (Vietnam)"
}

# ---------------------------------------------------
# 📄 TEXT INPUT & FILE EXTRACTION
# ---------------------------------------------------
st.markdown("### 📄 Text Input")

def extract_text(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if extension == "txt":
        return uploaded_file.getvalue().decode("utf-8-sig")
    if extension == "pdf":
        pages = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: pages.append(page_text)
        return "\n\n".join(pages)
    if extension == "docx":
        document = Document(uploaded_file)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if extension in ("xls", "xlsx"):
        dataframe = pd.read_excel(uploaded_file)
        return dataframe.to_string(index=False)
    return ""

uploaded_file = st.file_uploader("Upload PDF, DOCX, TXT, XLS, or XLSX", type=["pdf", "docx", "txt", "xls", "xlsx"])

if "edited_text" not in st.session_state:
    st.session_state.edited_text = ""
if "last_file_signature" not in st.session_state:
    st.session_state.last_file_signature = None

if uploaded_file is not None:
    signature = (uploaded_file.name, uploaded_file.size)
    if signature != st.session_state.last_file_signature:
        try:
            extracted_text = extract_text(uploaded_file)
            st.session_state.edited_text = extracted_text
            st.session_state.last_file_signature = signature
        except Exception as file_error:
            st.error(f"Error reading file: {file_error}")

text_to_speak = st.text_area(
    "Edit or type your text here:",
    value=st.session_state.edited_text,
    height=250,
    key="text_area_input"
)
st.session_state.edited_text = text_to_speak

# 📊 4 COUNTER METRICS
words_count = len(text_to_speak.split())
chars_count = len(text_to_speak)
sentences_count = len([s for s in text_to_speak.replace('!', '.').replace('?', '.').split('.') if s.strip()])
read_time_mins = round(words_count / 150, 1) if words_count > 0 else 0

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
stat_col1.metric("Characters", chars_count)
stat_col2.metric("Words", words_count)
stat_col3.metric("Sentences", sentences_count)
stat_col4.metric("Est. Read Time", f"{read_time_mins} min")
st.divider()

# ---------------------------------------------------
# 🌍 LANGUAGE SELECTION & AUTO-DETECT
# ---------------------------------------------------
locale_display = {voice["Locale"]: LANGUAGE_MAP.get(voice["Locale"], voice["Locale"]) for voice in voices}
sorted_languages = sorted(locale_display.items(), key=lambda item: item[1])
available_locales = [loc for loc, name in sorted_languages]

if "selected_lang" not in st.session_state:
    st.session_state.selected_lang = sorted_languages[0][1]
if "detect_msg" not in st.session_state:
    st.session_state.detect_msg = None

# Define the callback function (runs BEFORE the page renders)
def detect_language_callback():
    text = st.session_state.text_area_input
    if not text.strip():
        st.session_state.detect_msg = "warning|Please enter some text first."
        return
    
    try:
        detected_code = detect(text[:1000])
        matches = [loc for loc in available_locales if loc.startswith(detected_code)]
        if matches:
            defaults = {'en': 'en-US', 'ur': 'ur-PK', 'hi': 'hi-IN', 'zh': 'zh-CN', 'fr': 'fr-FR', 'es': 'es-ES', 'ar': 'ar-SA', 'pt': 'pt-BR'}
            best_locale = defaults.get(detected_code) if defaults.get(detected_code) in matches else matches[0]
            
            display_name = next(label for code, label in sorted_languages if code == best_locale)
            st.session_state.selected_lang = display_name
            st.session_state.detect_msg = f"success|Detected: **{display_name}**"
        else:
            st.session_state.detect_msg = f"warning|Language code '{detected_code}' detected, but no matching voice found."
    except LangDetectException:
        st.session_state.detect_msg = "error|Could not detect language. Please select manually."

# UI Layout for Language & Button
col_lang, col_btn = st.columns([3, 1])

with col_lang:
    language_choice = st.selectbox(
        "🌍 Select Language",
        [label for code, label in sorted_languages],
        key="selected_lang"
    )

with col_btn:
    st.write("") # Spacing
    st.write("")
    # on_click executes the callback before the app re-renders
    st.button("🔍 Auto-Detect Language", use_container_width=True, on_click=detect_language_callback)

# Display the result message below the dropdown
if st.session_state.detect_msg:
    msg_type, msg_text = st.session_state.detect_msg.split("|", 1)
    if msg_type == "success":
        st.success(msg_text)
    elif msg_type == "warning":
        st.warning(msg_text)
    else:
        st.error(msg_text)

# Resolve selected locale
selected_locale = next(code for code, label in sorted_languages if label == language_choice)
filtered_voices = [voice for voice in voices if voice["Locale"] == selected_locale]

# ---------------------------------------------------
# VOICE GENDER FILTER & SELECTION
# ---------------------------------------------------
if "gender_filter" not in st.session_state:
    st.session_state.gender_filter = "All"

g1, g2, g3 = st.columns(3)
with g1:
    if st.button("All Voices", use_container_width=True): st.session_state.gender_filter = "All"
with g2:
    if st.button("Male Voices", use_container_width=True): st.session_state.gender_filter = "Male"
with g3:
    if st.button("Female Voices", use_container_width=True): st.session_state.gender_filter = "Female"

if st.session_state.gender_filter != "All":
    filtered_voices = [v for v in filtered_voices if v["Gender"] == st.session_state.gender_filter]

voice_map = {}
for voice in filtered_voices:
    short_name = voice["ShortName"]
    clean_name = short_name.split("-")[-1].replace("Neural", "").strip()
    voice_map[f"{clean_name} ({voice['Gender']})"] = short_name

voice_labels = sorted(voice_map.keys())
if not voice_labels:
    st.warning("No voices found for this selection.")
    st.stop()

voice_choice = st.selectbox("🎤 Select Voice", voice_labels)
selected_voice = voice_map[voice_choice]

# ---------------------------------------------------
# SPEED AND PITCH
# ---------------------------------------------------
st.markdown("### 🎚️ Voice Settings")
c1, c2 = st.columns(2)
with c1:
    speed = st.slider("⚡ Speed", min_value=-50, max_value=50, value=0)
with c2:
    pitch = st.slider("🎵 Pitch", min_value=-50, max_value=50, value=0)

def format_rate(value): return f"{value:+d}%"
def format_pitch(value): return f"{value:+d}Hz"

# ---------------------------------------------------
# SAMPLE VOICE PREVIEW
# ---------------------------------------------------
async def create_sample():
    communicate = edge_tts.Communicate(text="Hello, this is a sample voice preview.", voice=selected_voice)
    await communicate.save("sample.mp3")

if st.button("▶ Play Sample Voice"):
    try:
        with st.spinner("Generating sample..."):
            asyncio.run(create_sample())
        with open("sample.mp3", "rb") as sample_file:
            st.audio(sample_file.read(), format="audio/mpeg")
    except Exception as e:
        st.error(f"Sample failed: {type(e).__name__}")

# ---------------------------------------------------
# 🚀 AUDIO GENERATION ENGINE PIPELINE
# ---------------------------------------------------
st.divider()
st.markdown("### 🚀 Generate Full Audio")

async def generate_full_audio(text, voice, rate_str, pitch_str):
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate_str, pitch=pitch_str)
    await communicate.save("output.mp3")

if st.button("🎙️ Generate Full Audio File", use_container_width=True, type="primary"):
    if not text_to_speak.strip():
        st.warning("Please provide text before running the voice generator pipeline.")
    else:
        try:
            progress_text = "Synthesizing voice... Please wait."
            my_bar = st.progress(0, text=progress_text)
            start_time = time.time()
            
            rate_param = format_rate(speed) if speed != 0 else "+0%"
            pitch_param = format_pitch(pitch) if pitch != 0 else "+0Hz"
            
            my_bar.progress(30, text="Processing text data...")
            time.sleep(0.5) 
            
            my_bar.progress(60, text="Connecting to Speech Service...")
            asyncio.run(generate_full_audio(text_to_speak, selected_voice, rate_param, pitch_param))
            
            my_bar.progress(100, text="Finalizing audio file...")
            time.sleep(0.5)
            
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            my_bar.empty()
            
            st.success(f"🎉 Audio generated successfully in **{duration} seconds**!")
            
            with open("output.mp3", "rb") as audio_file:
                audio_data = audio_file.read()
                
            st.audio(audio_data, format="audio/mpeg")
            
            st.download_button(
                label="⬇️ Download Audio File (.mp3)",
                data=audio_data,
                file_name="WordWave_Audio.mp3",
                mime="audio/mpeg",
                use_container_width=True
            )
            
        except Exception as gen_err:
            st.error(f"Pipeline Generation Failed: {type(gen_err).__name__}")
            print("Full execution pipeline error details:", repr(gen_err))
