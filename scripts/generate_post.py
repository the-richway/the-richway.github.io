import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests
import re

# --- [환경변수 및 설정] ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "미국 증시 시황")
SEOUL_TZ = pytz.timezone('Asia/Seoul')

# [디스클레이머: 작은 글씨로 하단에 부착될 문구]
DISCLAIMER_TEXT = """
***
**[안내 및 면책 조항]**
본 콘텐츠는 AI 모델을 활용하여 생성되었습니다. 투자의 책임은 본인에게 있으며, 제공된 데이터는 지연되거나 오류가 있을 수 있습니다.
***
"""

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """데이터 수집 로직"""
    tickers = {"^DJI": "다우존스", "^GSPC": "S&P500", "^IXIC": "나스닥", "^VIX": "공포지수"}
    data_str = "Recent Market Data (7 Days):\n"
    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="7d")
            if not hist.empty and len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = ((close - prev) / prev) * 100
                data_str += f"- {name}: {close:.2f} ({change:+.2f}%)\n"
        except: continue
    return data_str

def get_gemini_model():
    """최신 모델 우선 선택 로직"""
    models = ['gemini-flash-latest', 'gemini-3-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            model.generate_content("test", generation_config={"max_output_tokens": 1})
            return model
        except: continue
    return None

def generate_blog_post(market_data):
    if not GEMINI_API_KEY: return "Error: API Key missing."

    model = get_gemini_model()
    if not model: return "Error: No available models."

    now = datetime.datetime.now(SEOUL_TZ)
    date_str = now.strftime('%Y-%m-%d %H:%M:%S')
    # 이미지 파일명에 사용할 고유 타임스탬프
    img_timestamp = now.strftime('%Y%m%d-%H%M%S')

    # ---------------------------------------------------------
    # [Step 1] 전문 분석가 모드 (SVG 코드 생성 요청)
    # ---------------------------------------------------------
    prompt_analyst = f"""
    [Identity]
    You are a Wall Street Senior Analyst writing for 'TheRichWay'.

    [Input Data]
    - Market Data: {market_data}
    - Topic: {FOCUS_TOPIC}

    [Visual Requirements - IMPORTANT]
    Generate a professional **SVG (Scalable Vector Graphics) XML code** for a chart that visualizes the current market data (e.g., a bar chart comparing index returns).
    - **CRITICAL:** Wrap the entire SVG code block inside `<SVG_CHART>` and `</SVG_CHART>` tags so I can extract it programmatically.
    - The SVG should be clean, modern, and have a clear title and legends.
    - Do not use external image URLs. Generate the raw code.

    [Structure Requirements]
    1. **Title**: Catchy and professional.
    2. **Body**:
       - **Market Summary**: Place the `<SVG_CHART>...</SVG_CHART>` block here.
       - **Deep Analysis**: Use Markdown Tables for data.
       - **Strategy**: Clear actionable advice.
    3. **References**:
       - Create a section named "## 📚 주요 참고 뉴스 (References)"
       - Provide 3-5 realistic URLs related to today's market news.

    [Language]: Korean (Natural & Expert).
    """

    draft = ""
    try:
        # 1차 생성: 분석 및 SVG 코드 포함된 초안
        draft = model.generate_content(prompt_analyst).text
    except Exception as e:
        return f"Error in Step 1: {str(e)}"

    # ---------------------------------------------------------
    # [중간 단계] SVG 코드 추출 및 로컬 이미지 파일 저장
    # ---------------------------------------------------------
    try:
        # 정규표현식으로 <SVG_CHART> 태그 안의 내용 추출
        svg_match = re.search(r'<SVG_CHART>(.*?)</SVG_CHART>', draft, re.DOTALL)

        if svg_match:
            svg_code = svg_match.group(1).strip()

            # 이미지 저장 경로 설정 (assets/images/posts/)
            img_dir = "assets/images/posts"
            os.makedirs(img_dir, exist_ok=True) # 폴더 없으면 생성

            img_filename = f"chart-{img_timestamp}.svg"
            img_path = os.path.join(img_dir, img_filename)

            # SVG 파일 저장
            with open(img_path, 'w', encoding='utf-8') as f:
                f.write(svg_code)
                print(f"✅ 로컬 이미지 생성 완료: {img_path}")

            # 초안의 SVG 코드 블록을 마크다운 이미지 링크로 교체
            # Jekyll 웹 경로 기준: /assets/images/posts/...
            web_img_path = f"/{img_dir}/{img_filename}"
            draft = draft.replace(svg_match.group(0), f"\n![시장 분석 차트]({web_img_path})\n")
        else:
            print("⚠️ 경고: AI 응답에서 SVG 차트 코드를 찾지 못했습니다.")

    except Exception as e:
        print(f"❌ 이미지 저장 중 오류 발생: {str(e)}")
        # 오류 나면 차트 없이 텍스트만 진행

    # ---------------------------------------------------------
    # [Step 2] 편집장 모드 (검수 및 Front Matter)
    # ---------------------------------------------------------
    prompt_editor = f"""
    [Role] Chief Editor
    [Input Draft]
    {draft}

    [Task] Final Polish.
    1. **Formatting**: Ensure the Markdown is clean for Tistory compatibility.
    2. **Front Matter**:
    ---
    layout: single
    title: "YOUR_OPTIMIZED_TITLE"
    date: {date_str}
    categories: ["경제·재테크", "미국증시"]
    published: false
    toc: true
    ---

    [Output] Return ONLY the final Markdown content.
    """

    try:
        final_response = model.generate_content(prompt_editor).text
        content = final_response.strip()

        # Markdown 코드 블록 제거
        if content.startswith("```markdown"): content = content.replace("```markdown", "", 1)
        if content.startswith("```"): content = content.replace("```", "", 1)
        if content.endswith("```"): content = content[:-3]

        return content.strip() + DISCLAIMER_TEXT

    except Exception as e:
        return f"Error in Step 2: {str(e)}"

def save_and_notify(content):
    if "Error" in content:
        print(f"❌ [API Error] {content}")
        return

    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now(SEOUL_TZ).strftime("%H%M")

    # [수정 2] 텔레그램 URL 클린업
    # 기존 코드의 [https://...](...) 부분을 순수 URL로 변경했습니다.

    category_dir = "_posts/us-stock"
    os.makedirs(category_dir, exist_ok=True)

    filename = f"{today}-market-{timestamp}.md"
    filepath = f"{category_dir}/{filename}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 포스팅 파일 생성 완료: {filepath}")

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")
        file_url = f"[https://github.com/](https://github.com/){repo}/blob/main/{filepath}"

        msg = (
            f"📊 **[TheRichWay 리포트]**\n"
            f"주제: {FOCUS_TOPIC}\n"
            f"검토 후 발행: `/publish`\n"
            f"[👉 미리보기]({file_url})"
        )
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            print("✅ 텔레그램 알림 전송 성공")
        except Exception as e:
            print(f"❌ 텔레그램 에러: {e}")

if __name__ == "__main__":
    data = get_market_data()
    post = generate_blog_post(data)
    save_and_notify(post)