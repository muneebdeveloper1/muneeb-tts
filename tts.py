import streamlit as st
import asyncio
import edge_tts
import aiohttp
import pdfplumber
import pandas as pd
from docx import Document
from pathlib import Path
import time
import io
import re
from pydub import AudioSegment
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

# Comprehensive Language Map for Full Names
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
# TAB 1: QUICK VOICE (Exact UI Restored)
# ==========================================
with tab1:
    st.markdown("### 📄 Text Input")
    
    uploaded_file = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"], key="tab1_upload")
    if "edited_text_1" not in st.session_state: st.session_state.edited_text_1 = ""
    
    if uploaded_file:
        st.session_state.edited_text_1 = extract_text(uploaded_file)

    text_to_speak = st.text_area("Edit or type your text here:", value=st.session_state.edited_text_1, height=250, key="tab1_text")
    st.session_state.edited_text_1 = text_to_speak

    # 4 Metrics
    words = len(text_to_speak.split())
    sentences = len([s for s in text_to_speak.replace('!', '.').replace('?', '.').split('.') if s.strip()])
    read_time = round(words / 150, 1) if words > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Characters", len(text_to_speak))
    c2.metric("Words", words)
    c3.metric("Sentences", sentences)
    c4.metric("Est. Read Time", f"{read_time} min")

    st.divider()

    # Language & Auto Detect
    all_locales = sorted(list(set([v["Locale"] for v in voices])))
    
    if "selected_lang_t1" not in st.session_state:
        st.session_state.selected_lang_t1 = all_locales[0]
    if "detect_msg_t1" not in st.session_state:
        st.session_state.detect_msg_t1 = None

    def detect_lang_t1():
        text = st.session_state.tab1_text
        if not text.strip():
            st.session_state.detect_msg_t1 = "warning|Please enter text first."
            return
        try:
            code = detect(text[:1000])
            matches = [loc for loc in all_locales if loc.startswith(code)]
            if matches:
                defaults = {'en': 'en-US', 'ur': 'ur-PK', 'hi': 'hi-IN', 'zh': 'zh-CN', 'fr': 'fr-FR', 'es': 'es-ES', 'ar': 'ar-SA'}
                best = defaults.get(code) if defaults.get(code) in matches else matches[0]
                st.session_state.selected_lang_t1 = best
                st.session_state.detect_msg_t1 = f"success|Detected: **{LANGUAGE_MAP.get(best, best)}**"
            else:
                st.session_state.detect_msg_t1 = f"warning|Detected '{code}', but no matching voice."
        except:
            st.session_state.detect_msg_t1 = "error|Could not detect language."

    col_lang, col_btn = st.columns([3, 1])
    with col_lang:
        selected_locale_t1 = st.selectbox(
            "🌍 Select Language", 
            all_locales, 
            format_func=lambda x: LANGUAGE_MAP.get(x, x),
            key="selected_lang_t1"
        )
    with col_btn:
        st.write("")
        st.write("")
        st.button("🔍 Auto-Detect", use_container_width=True, on_click=detect_lang_t1)

    if st.session_state.detect_msg_t1:
        msg_t, msg_txt = st.session_state.detect_msg_t1.split("|", 1)
        if msg_t == "success": st.success(msg_txt)
        elif msg_t == "warning": st.warning(msg_txt)
        else: st.error(msg_txt)

    # Voice Selection
    filtered = [v for v in voices if v["Locale"] == selected_locale_t1]
    
    if "gender_filter_t1" not in st.session_state: st.session_state.gender_filter_t1 = "All"
    
    g1, g2, g3 = st.columns(3)
    if g1.button("All Voices", use_container_width=True, key="btn_g1"): st.session_state.gender_filter_t1 = "All"
    if g2.button("Male Voices", use_container_width=True, key="btn_g2"): st.session_state.gender_filter_t1 = "Male"
    if g3.button("Female Voices", use_container_width=True, key="btn_g3"): st.session_state.gender_filter_t1 = "Female"

    if st.session_state.gender_filter_t1 != "All":
        filtered = [v for v in filtered if v["Gender"] == st.session_state.gender_filter_t1]

    voice_names = [v["ShortName"].split("-")[-1].replace("Neural","") + f" ({v['Gender']})" for v in filtered]
    voice_choice_t1 = st.selectbox("🎤 Select Voice", voice_names)
    selected_voice_t1 = filtered[voice_names.index(voice_choice_t1)]["ShortName"]

    with st.expander("⚙️ Voice Settings"):
        c_speed, c_pitch = st.columns(2)
        speed_t1 = c_speed.slider("⚡ Speed", -50, 50, 0)
        pitch_t1 = c_pitch.slider("🎵 Pitch", -50, 50, 0)

    st.write("")
    if st.button("🎙️ Generate Full Audio File", use_container_width=True, type="primary"):
        if not text_to_speak.strip():
            st.warning("Please provide text before generating.")
        else:
            start_time = time.time()
            bar = st.progress(0, text="Synthesizing...")
            try:
                bar.progress(40, text="Connecting to Speech Service...")
                audio_bytes = asyncio.run(generate_audio_async(text_to_speak, selected_voice_t1, f"{speed_t1:+d}%", f"{pitch_t1:+d}Hz"))
                bar.progress(100, text="Finalizing...")
                time.sleep(0.5)
                bar.empty()
                
                duration = round(time.time() - start_time, 2)
                st.success(f"🎉 Audio generated successfully in **{duration} seconds**!")
                st.audio(audio_bytes, format="audio/mp3")
                st.download_button("⬇️ Download Audio File (.mp3)", audio_bytes, "WordWave_Quick.mp3", "audio/mp3", use_container_width=True)
            except Exception as e:
                st.error(f"Generation Failed: {e}")

# ==========================================
# TAB 2: MULTI-VOICE DIALOGUE (Dynamic Characters)
# ==========================================
with tab2:
    st.markdown("### 🎭 Multi-Voice Dialogue Generator")
    st.info("Format your script with names in brackets, like this: `[Alex]: Hello there!` `[Sarah]: Hi Alex!`")
    
    dialogue_text = st.text_area("Script:", height=200, placeholder="[Alex]: Hello there!\n[Sarah]: Hi Alex, how are you?", key="tab2_script")
    
    st.divider()
    st.markdown("#### 👥 Character Setup")
    
    if "num_chars" not in st.session_state:
        st.session_state.num_chars = 2

    col_add, col_rem, _ = st.columns([1, 1, 4])
    if col_add.button("➕ Add Character"):
        st.session_state.num_chars += 1
    if col_rem.button("➖ Remove Character") and st.session_state.num_chars > 1:
        st.session_state.num_chars -= 1

    char_configs = {}
    
    # Generate dynamic UI for each character
    for i in range(st.session_state.num_chars):
        st.markdown(f"**Character {i+1}**")
        c_name, c_lang, c_voice = st.columns([2, 3, 3])
        
        default_name = "Alex" if i == 0 else ("Sarah" if i == 1 else f"Character {i+1}")
        c_name_val = c_name.text_input("Name", value=default_name, key=f"c_name_{i}")
        
        c_lang_val = c_lang.selectbox(
            "Language", 
            all_locales, 
            format_func=lambda x: LANGUAGE_MAP.get(x, x),
            key=f"c_lang_{i}"
        )
        
        filtered_v = [v for v in voices if v["Locale"] == c_lang_val]
        v_names = [v["ShortName"].split("-")[-1].replace("Neural","") + f" ({v['Gender']})" for v in filtered_v]
        c_voice_val = c_voice.selectbox("Voice", v_names, key=f"c_voice_{i}")
        
        # Store mapping: "alex" -> "en-US-GuyNeural"
        char_configs[c_name_val.lower()] = filtered_v[v_names.index(c_voice_val)]["ShortName"]

    st.write("")
    if st.button("🎬 Generate Dialogue Audio", use_container_width=True, type="primary"):
        if not dialogue_text.strip():
            st.warning("Please enter a script.")
        else:
            start_time = time.time()
            bar = st.progress(0, text="Processing Script...")
            
            lines = [line.strip() for line in dialogue_text.split('\n') if line.strip()]
            final_audio = AudioSegment.empty()
            
            # Default voice fallback (first character's voice)
            default_voice = list(char_configs.values())[0]

            try:
                for idx, line in enumerate(lines):
                    match = re.match(r"^\[(.*?)\]:\s*(.*)", line)
                    if match:
                        speaker = match.group(1).lower()
                        text = match.group(2)
                        voice = char_configs.get(speaker, default_voice)
                    else:
                        text = line
                        voice = default_voice

                    bar.progress(int((idx/len(lines))*100), text=f"Generating line {idx+1} of {len(lines)}...")
                    audio_bytes = asyncio.run(generate_audio_async(text, voice))
                    
                    segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                    final_audio += segment + AudioSegment.silent(duration=500) # 0.5s pause between lines

                bar.progress(100, text="Merging Audio...")
                out_buffer = io.BytesIO()
                final_audio.export(out_buffer, format="mp3", bitrate="192k")
                bar.empty()
                
                duration = round(time.time() - start_time, 1)
                st.success(f"🎉 Dialogue generated in **{duration} seconds**!")
                st.audio(out_buffer.getvalue(), format="audio/mp3")
                st.download_button("⬇️ Download Dialogue MP3", out_buffer.getvalue(), "WordWave_Dialogue.mp3", "audio/mp3", use_container_width=True)
            except Exception as e:
                st.error(f"Error mixing dialogue: {e}")

# ==========================================
# TAB 3: AUDIOBOOK STUDIO
# ==========================================
with tab3:
    st.markdown("### 📚 Audiobook & Subtitle Studio")
    
    studio_text = st.text_area("Paste long text here (Max 50,000 characters):", height=250, key="tab3_text")
    
    with st.expander("🛠️ Studio Settings", expanded=True):
        st.markdown("**Audio & Subtitles**")
        generate_srt = st.checkbox("Generate SRT Subtitles", value=True)
        
        st.markdown("**Background Music (Optional)**")
        music_file = st.file_uploader("Upload Background Music (MP3)", type=["mp3"])
        music_volume = st.slider("Music Volume Reduction (dB)", -30, -5, -15)
        
        st.markdown("**Smart Cleanup**")
        clean_pdf = st.checkbox("Remove PDF line breaks (fixes weird pausing)", value=True)

    st.write("")
    if st.button("🏭 Start Audiobook Production", use_container_width=True, type="primary"):
        if not studio_text.strip():
            st.warning("Please enter text.")
        else:
            start_time = time.time()
            
            if clean_pdf:
                studio_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', studio_text)
            
            chunks = [p for p in studio_text.split('\n') if p.strip()]
            
            bar = st.progress(0, text="Initializing Audio Engine...")
            final_audio = AudioSegment.empty()
            submaker = edge_tts.SubMaker() if generate_srt else None

            try:
                # Default voice for audiobook chunks
                default_audiobook_voice = "en-US-ChristopherNeural"
                
                for i, chunk in enumerate(chunks):
                    bar.progress(int((i/len(chunks))*100), text=f"Synthesizing chunk {i+1} of {len(chunks)}...")
                    audio_bytes = asyncio.run(generate_audio_async(chunk, default_audiobook_voice, submaker=submaker))
                    segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                    final_audio += segment + AudioSegment.silent(duration=300)

                if music_file:
                    bar.progress(90, text="Mixing Background Music...")
                    music = AudioSegment.from_file(music_file, format="mp3")
                    music = music - abs(music_volume)
                    
                    if len(music) < len(final_audio):
                        loops = (len(final_audio) // len(music)) + 1
                        music = music * loops
                    
                    music = music[:len(final_audio)]
                    final_audio = final_audio.overlay(music)

                bar.progress(95, text="Finalizing File...")
                out_buffer = io.BytesIO()
                final_audio.export(out_buffer, format="mp3", bitrate="192k")
                
                bar.empty()
                duration = round(time.time() - start_time, 1)
                st.success(f"🎉 Audiobook Production Complete! (Took {duration}s)")
                
                st.audio(out_buffer.getvalue(), format="audio/mp3")
                st.download_button("⬇️ Download Full Audiobook (MP3)", out_buffer.getvalue(), "WordWave_Audiobook.mp3", "audio/mp3", use_container_width=True)
                
                if generate_srt:
                    srt_data = submaker.get_srt()
                    if srt_data:
                        st.download_button("⬇️ Download Subtitles (SRT)", srt_data, "WordWave_Subtitles.srt", "text/plain", use_container_width=True)
                        
            except Exception as e:
                st.error(f"Production Error: {e}")
