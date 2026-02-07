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

    # ---------------------------------------------------------
    # [Step 1] 전문 분석가 모드 (표/데이터 위주)
    # ---------------------------------------------------------
    prompt_analyst = f"""
    [Identity]
    You are a Wall Street Senior Analyst.
    Your goal is to provide a sharp, data-driven analysis of the US market.
    Do NOT mention your name or "TheRichWay" in the text.

    [Input Data]
    - Market Data: {market_data}
    - Topic: {FOCUS_TOPIC}

    [Content Requirements]
    1. **Visuals (Markdown Tables)**:
       - Since we cannot use images, you MUST use **Markdown Tables** extensively.
       - Create a summary table of the indices at the beginning.
       - If mentioning sectors, use a table to show winners vs. losers.
    2. **Analysis**:
       - Deep dive into WHY the market moved.
       - Connect macroeconomics (rates, inflation) to stock movements.
    3. **References (News Curation)**:
       - Create a section named "## 📚 주요 참고 뉴스" at the end.
       - **CRITICAL:** 80% of the news sources must be **Korean media** (e.g., Hankyung, Maeil, Yonhap). 20% can be major global sources (Bloomberg, WSJ).
       - Provide 3-5 links.

    [Language]: Korean (Natural & Expert).
    """

    draft = ""
    try:
        # 1차 생성: 초안 작성
        draft = model.generate_content(prompt_analyst).text
    except Exception as e:
        return f"Error in Step 1: {str(e)}"

    # ---------------------------------------------------------
    # [Step 2] 편집장 모드 (브랜딩 제거 및 포맷팅)
    # ---------------------------------------------------------
    prompt_editor = f"""
    [Role] Chief Editor
    [Input Draft]
    {draft}

    [Task] Final Polish.
    1. **Branding Removal**: Ensure terms like "TheRichWay", "Report", "Writer" are REMOVED. The output should look like a pure analysis article.
    2. **Formatting**: Ensure Markdown tables are correctly formatted for compatibility.
    3. **Front Matter**:
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

    category_dir = "_posts/us-stock"
    os.makedirs(category_dir, exist_ok=True)

    filename = f"{today}-market-{timestamp}.md"
    filepath = f"{category_dir}/{filename}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 포스팅 파일 생성 완료: {filepath}")

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")

        # [수정 완료] 텔레그램 URL 오류 수정
        # 기존: f"[https://github.com/](...){repo}..." -> 마크다운 중복으로 깨짐
        # 수정: 순수한 URL 문자열로 변경
        file_url = f"[https://github.com/](https://github.com/){repo}/blob/main/{filepath}"

        # [수정 완료] 브랜딩 문구 제거 (TheRichWay Report 등 삭제)
        msg = (
            f"📊 **[미국 증시 분석 완료]**\n"
            f"주제: {FOCUS_TOPIC}\n"
            f"특징: 데이터 표 포함, 국내 뉴스 큐레이션\n\n"
            f"검토 후 발행: `/publish`\n"
            f"[👉 리포트 미리보기]({file_url})"
        )
        try:
            # requests.post 사용 시 json 파라미터 활용 (안정성)
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            )
            if response.status_code == 200:
                print("✅ 텔레그램 알림 전송 성공")
            else:
                print(f"❌ 텔레그램 전송 실패: {response.text}")
        except Exception as e:
            print(f"❌ 텔레그램 에러: {e}")

if __name__ == "__main__":
    data = get_market_data()
    post = generate_blog_post(data)
    save_and_notify(post)