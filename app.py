import streamlit as st
import anthropic
import json
import re
import trafilatura
import subprocess
import os
from elevenlabs.client import ElevenLabs
from elevenlabs import save

anthropic_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
eleven_client = ElevenLabs(api_key=st.secrets["ELEVENLABS_API_KEY"])

os.makedirs("output", exist_ok=True)

st.title("AI 쇼츠 생성기")

source = st.radio("소스 선택", ["AI 자동 생성", "URL 입력"])

if source == "AI 자동 생성":
    topic = st.text_input("주제 또는 키워드", "2025년 AI 트렌드")
    video_file = None
else:
    col1, col2 = st.columns(2)
    with col1:
        url = st.text_input("뉴스/블로그 URL (스크립트용)")
    with col2:
        video_file = st.file_uploader("영상 파일 업로드", type=["mp4", "mov", "avi"])
        if video_file:
            with open("output/original.mp4", "wb") as f:
                f.write(video_file.read())
            st.success("영상 업로드 완료!")

    topic = ""
    if url:
        with st.spinner("URL 내용 추출 중..."):
            downloaded = trafilatura.fetch_url(url)
            extracted = trafilatura.extract(downloaded)
            if extracted:
                st.success("추출 완료!")
                st.text_area("추출된 내용 미리보기", extracted[:500] + "...", height=150)
                topic = f"다음 내용을 숏폼 스크립트로 만들어줘:\n{extracted[:2000]}"
            else:
                st.error("URL에서 내용을 가져오지 못했어요.")
    elif video_file:
        manual_topic = st.text_input("영상 주제/내용 간단히 설명", placeholder="예: 한국 올리브영 추천 제품 리스트")
        if manual_topic:
            topic = f"다음 주제로 한국어 숏폼 스크립트를 만들어줘:\n{manual_topic}"
        else:
            topic = ""
    else:
        topic = ""

lang = st.selectbox("출력 언어", ["한국어", "영어", "중국어(도우인용)"])
voice_options = {
    "여성 - 기본 (Rachel)": "21m00Tcm4TlvDq8ikWAM",
    "여성 - 한국어 자연스러운 (Bella)": "EXAVITQu4vr4xnSDxMaL",
    "남성 - 기본 (Josh)": "TxGEqnHWrfWFTfGW9XjX",
    "남성 - 깊은 목소리 (Arnold)": "VR6AewLTigWG4xSOukaG",
}
selected_voice = st.selectbox("목소리 선택", list(voice_options.keys()))
voice_id = voice_options[selected_voice]

def mute_and_merge(video_path, audio_path, out_path="output/merged.mp4"):
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        out_path
    ]
    subprocess.run(cmd, check=True)
    return out_path

if st.button("스크립트 생성"):
    if not topic:
        st.warning("주제 또는 URL을 입력해주세요!")
    else:
        with st.spinner("스크립트 생성 중..."):
            message = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": f"""
다음 주제로 {lang} 숏폼 영상 스크립트를 만들어줘.
주제: {topic}

반드시 JSON 형식으로만 응답해. 다른 말은 하지 마:
{{
  "hook": "3초 안에 시선 잡는 첫 문장",
  "body": ["포인트1", "포인트2", "포인트3"],
  "cta": "팔로우/댓글 유도 마지막 문장"
}}
"""
                }]
            )

        raw = message.content[0].text
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            result = json.loads(match.group())

            st.success("스크립트 완료!")
            st.markdown(f"**훅:** {result['hook']}")
            for i, point in enumerate(result['body'], 1):
                st.markdown(f"**{i}.** {point}")
            st.markdown(f"**CTA:** {result['cta']}")

            full_script = result['hook'] + " " + " ".join(result['body']) + " " + result['cta']

            with st.spinner("TTS 변환 중..."):
                audio = eleven_client.text_to_speech.convert(
                    text=full_script,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2"
                )
                save(audio, "output/script.mp3")

            st.success("TTS 완료!")
            st.audio("output/script.mp3")

            if video_file:
                with st.spinner("음성 합치는 중..."):
                    mute_and_merge("output/original.mp4", "output/script.mp3")
                    st.success("🎉 최종 영상 완성!")

                with open("output/merged.mp4", "rb") as f:
                    st.download_button(
                        label="⬇️ 최종 영상 다운로드",
                        data=f,
                        file_name="shorts_final.mp4",
                        mime="video/mp4"
                    )
        else:
            st.warning("스크립트 생성 결과:")
            st.write(raw)