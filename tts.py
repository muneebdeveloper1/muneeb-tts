import streamlit as st
import asyncio
import edge_tts
import pdfplumber
from docx import Document
import pandas as pd

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="Keep Laughing Voice Generator",
    page_icon="logo.png",
    layout="wide"
)

col1, col2 = st.columns([1, 8])

with col1:
    st.image("logo.png", width=150)

with col2:
    st.title("Keep Laughing with Muneeb")

# ---------------------------------------------------
# LOAD EDGE TTS VOICES
# ---------------------------------------------------
@st.cache_data
def load_voices():
    async def get_voices():
        return await edge_tts.list_voices()

    return asyncio.run(get_voices())

voices = load_voices()

# ---------------------------------------------------
# FILE TEXT EXTRACTION
# ---------------------------------------------------
def extract_text(file):
    extension = file.name.split(".")[-1].lower()

    if extension == "txt":
        return file.read().decode("utf-8")

    elif extension == "pdf":
        text = ""

        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"

        return text

    elif extension == "docx":
        doc = Document(file)
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)

    elif extension in ["xls", "xlsx"]:
        dataframe = pd.read_excel(file)
        return dataframe.to_string(index=False)

    return ""

# ---------------------------------------------------
# LANGUAGE MAP
# ---------------------------------------------------
LANGUAGE_MAP = {
    "en-US": "English (United States)",
    "en-GB": "English (United Kingdom)",
    "en-AU": "English (Australia)",
    "en-CA": "English (Canada)",
    "en-IN": "English (India)",
    "ur-PK": "Urdu (Pakistan)",
    "hi-IN": "Hindi (India)",
    "ar-SA": "Arabic (Saudi Arabia)",
    "tr-TR": "Turkish (Turkey)",
    "fr-FR": "French (France)",
    "de-DE": "German (Germany)",
    "es-ES": "Spanish (Spain)",
    "it-IT": "Italian (Italy)",
    "pt-BR": "Portuguese (Brazil)",
    "ru-RU": "Russian (Russia)",
    "ja-JP": "Japanese (Japan)",
    "ko-KR": "Korean (South Korea)",
    "zh-CN": "Chinese (China)",
    "bn-BD": "Bengali (Bangladesh)",
    "fa-IR": "Persian (Iran)",
    "id-ID": "Indonesian (Indonesia)",
    "ms-MY": "Malay (Malaysia)",
    "nl-NL": "Dutch (Netherlands)",
    "pl-PL": "Polish (Poland)",
    "sv-SE": "Swedish (Sweden)",
    "ta-IN": "Tamil (India)",
    "te-IN": "Telugu (India)",
    "th-TH": "Thai (Thailand)",
    "uk-UA": "Ukrainian (Ukraine)",
    "vi-VN": "Vietnamese (Vietnam)"
}

# ---------------------------------------------------
# LANGUAGE SELECTION
# ---------------------------------------------------
locale_display = {}

for voice in voices:
    locale = voice["Locale"]

    if locale in LANGUAGE_MAP:
        locale_display[locale] = LANGUAGE_MAP[locale]
    else:
        parts = locale.split("-")

        if len(parts) == 2:
            locale_display[locale] = (
                f"{parts[0].upper()} ({parts[1].upper()})"
            )
        else:
            locale_display[locale] = locale

sorted_languages = sorted(
    locale_display.items(),
    key=lambda item: item[1]
)

language_labels = [
    label for code, label in sorted_languages
]

language_choice = st.selectbox(
    "🌍 Select Language",
    language_labels
)

selected_locale = None

for code, label in sorted_languages:
    if label == language_choice:
        selected_locale = code
        break

filtered_voices = [
    voice
    for voice in voices
    if voice["Locale"] == selected_locale
]

# ---------------------------------------------------
# GENDER FILTER
# ---------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    show_all = st.button("All Voices")

with col2:
    show_male = st.button("Male Voices")

with col3:
    show_female = st.button("Female Voices")

if show_male:
    filtered_voices = [
        voice
        for voice in filtered_voices
        if voice["Gender"] == "Male"
    ]

if show_female:
    filtered_voices = [
        voice
        for voice in filtered_voices
        if voice["Gender"] == "Female"
    ]

# ---------------------------------------------------
# VOICE SELECTION
# ---------------------------------------------------
voice_map = {}
voice_labels = []

for voice in filtered_voices:
    short_name = voice["ShortName"]

    clean_name = (
        short_name
        .split("-")[-1]
        .replace("Neural", "")
    )

    label = f"{clean_name} ({voice['Gender']})"

    voice_map[label] = short_name
    voice_labels.append(label)

voice_choice = st.selectbox(
    "🎤 Select Voice",
    voice_labels
)

selected_voice = voice_map[voice_choice]

# ---------------------------------------------------
# SAMPLE VOICE PREVIEW
# ---------------------------------------------------
async def create_sample():
    sample_text = (
        "Hello, this is a sample voice preview."
    )

    communicate = edge_tts.Communicate(
        sample_text,
        selected_voice
    )

    await communicate.save("sample.mp3")

if st.button("▶ Play Sample Voice"):
    asyncio.run(create_sample())
    st.audio("sample.mp3")

# ---------------------------------------------------
# INPUT TEXT / FILE with ADVANCED PREVIEW & EDIT
# ---------------------------------------------------
uploaded_file = st.file_uploader(
    "📁 Upload File (PDF, DOCX, TXT, Excel)",
    type=["pdf", "docx", "txt", "xls", "xlsx"]
)

# Initialize session state for edited text
if "original_text" not in st.session_state:
    st.session_state.original_text = ""
if "edited_text" not in st.session_state:
    st.session_state.edited_text = ""
if "file_uploaded" not in st.session_state:
    st.session_state.file_uploaded = False

# Handle file upload
if uploaded_file:
    # Check if a new file is uploaded (different from previous)
    current_file_name = uploaded_file.name
    if "last_file_name" not in st.session_state or st.session_state.last_file_name != current_file_name:
        # New file: extract text and store
        extracted = extract_text(uploaded_file)
        st.session_state.original_text = extracted
        st.session_state.edited_text = extracted
        st.session_state.file_uploaded = True
        st.session_state.last_file_name = current_file_name

    # Display file info
    st.info(f"📄 File loaded: {current_file_name}")

    # Advanced preview and edit area
    st.markdown("### ✏️ Edit Extracted Text")
    st.markdown("Modify the text below — remove or keep only the parts you need for audio generation.")

    # Editable text area
    edited = st.text_area(
        "Text Editor (edit freely)",
        value=st.session_state.edited_text,
        height=400,
        key="text_editor",
        label_visibility="collapsed"
    )

    # Update session state when user edits
    st.session_state.edited_text = edited

    # Action buttons
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Reset to Original"):
            st.session_state.edited_text = st.session_state.original_text
            st.rerun()
    with col_btn2:
        if st.button("🗑 Clear All"):
            st.session_state.edited_text = ""
            st.rerun()

    # Text to be used for audio generation
    final_text = st.session_state.edited_text

else:
    # No file uploaded: use simple text area for pasting
    st.session_state.file_uploaded = False
    final_text = st.text_area(
        "📄 Paste your text",
        height=250
    )

# ---------------------------------------------------
# TEXT STATISTICS (based on the text that will be spoken)
# ---------------------------------------------------
characters = len(final_text)
words = len(final_text.split())
sentences = len([
    sentence
    for sentence in (
        final_text.replace("!", ".")
            .replace("?", ".")
            .split(".")
    )
    if sentence.strip()
])
paragraphs = len([
    paragraph
    for paragraph in final_text.split("\n\n")
    if paragraph.strip()
])
lines = len([
    line
    for line in final_text.split("\n")
    if line.strip()
])

st.markdown("### 📊 Text Statistics")

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("Characters", characters)

with c2:
    st.metric("Words", words)

with c3:
    st.metric("Sentences", sentences)

with c4:
    st.metric("Paragraphs", paragraphs)

with c5:
    st.metric("Lines", lines)

# ---------------------------------------------------
# SPEED AND PITCH
# ---------------------------------------------------
speed = st.slider(
    "⚡ Speed",
    min_value=-50,
    max_value=50,
    value=0
)

pitch = st.slider(
    "🎚 Pitch",
    min_value=-50,
    max_value=50,
    value=0
)

def format_rate(value):
    return f"+{value}%" if value >= 0 else f"{value}%"

def format_pitch(value):
    return f"+{value}Hz" if value >= 0 else f"{value}Hz"

# ---------------------------------------------------
# AUDIO GENERATION
# ---------------------------------------------------
OUTPUT_FILE = "output.mp3"

async def generate_audio():
    communicate = edge_tts.Communicate(
        text=final_text,
        voice=selected_voice,
        rate=format_rate(speed),
        pitch=format_pitch(pitch)
    )

    await communicate.save(OUTPUT_FILE)

# ---------------------------------------------------
# GENERATE BUTTON
# ---------------------------------------------------
if st.button("🚀 Generate Audiobook"):

    if not final_text.strip():
        st.warning(
            "Please add text or upload a file (and make sure the editor is not empty)."
        )

    else:
        with st.spinner("Generating audio..."):
            asyncio.run(generate_audio())

        st.success("Audio generated successfully!")

        st.audio(OUTPUT_FILE)

        with open(OUTPUT_FILE, "rb") as audio_file:
            st.download_button(
                label="⬇ Download MP3",
                data=audio_file,
                file_name="audiobook.mp3",
                mime="audio/mpeg"
            )