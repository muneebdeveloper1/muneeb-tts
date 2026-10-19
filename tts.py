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
import re
import zipfile
import io
from pydub import AudioSegment
import langdetect
from langdetect import detect, LangDetectException

# ---------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------
st.set_page_config(
    page_title="WordWave Studio",
    page_icon="🎙️",
    layout="wide"
)

# ---------------------------------------------------
# 🔑 OWNER UNLOCK GATEWAY
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
    st.title("WordWave Studio")
    st.caption("Professional Audiobook & Text-to-Speech Pipeline (Developer Mode Active)")

# ---------------------------------------------------
# DATA & API SETUP
# ---------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_voices():
    return asyncio.run(edge_tts.list_voices())

with st.spinner("Initializing Voice Engine..."):
    voices = load_voices()

LANGUAGE_MAP = {
    "en-US": "English (US)", "en-GB": "English (UK)", "en-AU": "English (AU)", 
    "ur-PK": "Urdu", "hi-IN": "Hindi", "ar-SA": "Arabic", "fr-FR": "French", 
    "de-DE": "German", "es-ES": "Spanish", "zh-CN": "Chinese", "ja-JP": "Japanese"
}

# Helper function to extract text
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
    return ""

# Helper for Async Generation
async def generate_audio_async(text, voice, rate="+0%", pitch="+0Hz", submaker=None):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
        elif chunk["type"] == "WordBoundary" and submaker is not None:
            submaker.feed(chunk)
    return audio_data

# ---------------------------------------------------
# MAIN APP TABS
# ---------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🎙️ Quick Voice", "🎭 Multi-Voice Dialogue", "📚 Audiobook Studio"])

# ==========================================
# TAB 1: QUICK VOICE (Single Voice)
# ==========================================
with tab1:
    st.markdown("### 📄 Text Input")
    
    uploaded_file = st.file_uploader("Upload Document", type=["pdf", "docx", "txt"], key="tab1_upload")
    if "edited_text_1" not in st.session_state: st.session_state.edited_text_1 = ""
    
    if uploaded_file:
        st.session_state.edited_text_1 = extract_text(uploaded_file)

    text_to_speak = st.text_area("Edit text here:", value=st.session_state.edited_text_1, height=250, key="tab1_text")
    st.session_state.edited_text_1 = text_to_speak

    # 4 Metrics
    words = len(text_to_speak.split())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Characters", len(text_to_speak))
    c2.metric("Words", words)
    c3.metric("Sentences", len([s for s in text_to_speak.replace('!', '.').replace('?', '.').split('.') if s.strip()]))
    c4.metric("Est. Audio Time", f"{round(words/150, 1)} min")

    st.divider()

    # Language & Voice Selection
    col_lang, col_voice = st.columns(2)
    with col_lang:
        lang_opts = sorted(list(set([v["Locale"] for v in voices])))
        selected_locale = st.selectbox("🌍 Language", lang_opts, format_func=lambda x: LANGUAGE_MAP.get(x, x))
    with col_voice:
        filtered = [v for v in voices if v["Locale"] == selected_locale]
        voice_names = [v["ShortName"].split("-")[-1].replace("Neural","") + f" ({v['Gender']})" for v in filtered]
        selected_v_name = st.selectbox("🎤 Voice", voice_names)
        selected_voice = filtered[voice_names.index(selected_v_name)]["ShortName"]

    with st.expander("⚙️ Advanced Voice Settings"):
        c_speed, c_pitch = st.columns(2)
        speed = c_speed.slider("Speed", -50, 50, 0)
        pitch = c_pitch.slider("Pitch", -50, 50, 0)

    if st.button("🚀 Generate Audio", use_container_width=True, type="primary"):
        if not text_to_speak.strip():
            st.warning("Please enter text.")
        else:
            start_time = time.time()
            bar = st.progress(0, text="Generating...")
            try:
                audio_bytes = asyncio.run(generate_audio_async(text_to_speak, selected_voice, f"{speed:+d}%", f"{pitch:+d}Hz"))
                bar.empty()
                st.success(f"Generated in {round(time.time() - start_time, 2)}s")
                st.audio(audio_bytes, format="audio/mp3")
                st.download_button("⬇️ Download MP3", audio_bytes, "WordWave_Quick.mp3", "audio/mp3", use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")

# ==========================================
# TAB 2: MULTI-VOICE DIALOGUE
# ==========================================
with tab2:
    st.markdown("### 🎭 Multi-Voice Dialogue Generator")
    st.info("Format your text with character names in brackets. Example:\n\n**[Alex]:** Hello there!\n**[Sarah]:** Hi, how are you?")
    
    dialogue_text = st.text_area("Script:", height=200, placeholder="[Alex]: Hello!\n[Sarah]: Hi!")
    
    st.markdown("#### Assign Voices")
    st.write("Match the names in your script to specific voices.")
    
    # Pre-defined mapping for simplicity
    col_a, col_b = st.columns(2)
    char_a = col_a.text_input("Character 1 Name", "Alex")
    voice_a = col_a.selectbox("Voice for Character 1", [v["ShortName"] for v in voices if v["Locale"] == "en-US"], key="v_a")
    
    char_b = col_b.text_input("Character 2 Name", "Sarah")
    voice_b = col_b.selectbox("Voice for Character 2", [v["ShortName"] for v in voices if v["Locale"] == "en-GB"], index=1, key="v_b")

    if st.button("🚀 Generate Dialogue", use_container_width=True, type="primary"):
        if not dialogue_text.strip():
            st.warning("Please enter a script.")
        else:
            start_time = time.time()
            bar = st.progress(0, text="Processing Script...")
            
            # Parse script
            lines = [line.strip() for line in dialogue_text.split('\n') if line.strip()]
            final_audio = AudioSegment.empty()
            voice_map = {char_a.lower(): voice_a, char_b.lower(): voice_b}
            default_voice = voice_a

            try:
                for i, line in enumerate(lines):
                    match = re.match(r"^\[(.*?)\]:\s*(.*)", line)
                    if match:
                        speaker = match.group(1).lower()
                        text = match.group(2)
                        voice = voice_map.get(speaker, default_voice)
                    else:
                        text = line
                        voice = default_voice

                    # Generate audio for line
                    bar.progress(int((i/len(lines))*100), text=f"Generating line {i+1}...")
                    audio_bytes = asyncio.run(generate_audio_async(text, voice))
                    
                    # Convert to pydub segment and append
                    segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                    final_audio += segment + AudioSegment.silent(duration=500) # 0.5s pause

                # Export final combined audio
                out_buffer = io.BytesIO()
                final_audio.export(out_buffer, format="mp3")
                bar.empty()
                st.success(f"Dialogue generated in {round(time.time() - start_time, 2)}s!")
                st.audio(out_buffer.getvalue(), format="audio/mp3")
                st.download_button("⬇️ Download Dialogue MP3", out_buffer.getvalue(), "Dialogue.mp3", "audio/mp3", use_container_width=True)
            except Exception as e:
                st.error(f"Error mixing dialogue: {e}")

# ==========================================
# TAB 3: AUDIOBOOK STUDIO
# ==========================================
with tab3:
    st.markdown("### 📚 Audiobook & Subtitle Studio")
    
    studio_text = st.text_area("Paste long text here (Max 50,000 characters):", height=200)
    
    with st.expander("🛠️ Studio Settings"):
        st.markdown("**Audio & Subtitles**")
        generate_srt = st.checkbox("Generate SRT Subtitles", value=True)
        
        st.markdown("**Background Music (Optional)**")
        music_file = st.file_uploader("Upload Background Music (MP3)", type=["mp3"])
        music_volume = st.slider("Music Volume Reduction (dB)", -30, -5, -15)
        
        st.markdown("**Text Cleanup**")
        st.checkbox("Remove PDF line breaks (fixes weird pausing)", value=True, key="clean_pdf")

    st.write("")
    if st.button("🏭 Start Audiobook Production", use_container_width=True, type="primary"):
        if not studio_text.strip():
            st.warning("Please enter text.")
        else:
            start_time = time.time()
            
            # 1. Text Cleanup
            if st.session_state.clean_pdf:
                studio_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', studio_text) # Fix single linebreaks
            
            # 2. Chunking (Split by paragraph)
            chunks = [p for p in studio_text.split('\n') if p.strip()]
            
            bar = st.progress(0, text="Initializing Audio Engine...")
            final_audio = AudioSegment.empty()
            submaker = edge_tts.SubMaker() if generate_srt else None

            try:
                # 3. Loop and Generate
                for i, chunk in enumerate(chunks):
                    bar.progress(int((i/len(chunks))*100), text=f"Synthesizing chunk {i+1} of {len(chunks)}...")
                    
                    # Use default fast voice for chunks
                    audio_bytes = asyncio.run(generate_audio_async(chunk, "en-US-ChristopherNeural", submaker=submaker))
                    
                    segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                    final_audio += segment + AudioSegment.silent(duration=300)

                # 4. Background Music Mixing
                if music_file:
                    bar.progress(90, text="Mixing Background Music...")
                    music = AudioSegment.from_file(music_file, format="mp3")
                    music = music - abs(music_volume) # Lower volume
                    
                    # Loop music if it's shorter than the audiobook
                    if len(music) < len(final_audio):
                        loops = (len(final_audio) // len(music)) + 1
                        music = music * loops
                    
                    music = music[:len(final_audio)]
                    final_audio = final_audio.overlay(music)

                # 5. Export
                bar.progress(95, text="Finalizing File...")
                out_buffer = io.BytesIO()
                final_audio.export(out_buffer, format="mp3", bitrate="192k")
                
                bar.empty()
                st.success(f"🎉 Audiobook Production Complete! (Took {round(time.time() - start_time, 1)}s)")
                
                # Show Audio & Download
                st.audio(out_buffer.getvalue(), format="audio/mp3")
                st.download_button("⬇️ Download Full Audiobook (MP3)", out_buffer.getvalue(), "Audiobook.mp3", "audio/mp3", use_container_width=True)
                
                # SRT Download
                if generate_srt:
                    srt_data = submaker.get_srt()
                    if srt_data:
                        st.download_button("⬇️ Download Subtitles (SRT)", srt_data, "Audiobook_Subtitles.srt", "text/plain", use_container_width=True)
                        
            except Exception as e:
                st.error(f"Production Error: {e}")
