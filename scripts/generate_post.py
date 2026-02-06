import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests
import time

# --- 환경변수 및 설정 ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "")
SEOUL_TZ = pytz.timezone('Asia/Seoul')
MAX_RETRIES = 3

# Gemini 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """야후 파이낸스 데이터 수집 (분분석가가 사용할 로우 데이터)"""
    tickers = {"^DJI": "다우존스", "^GSPC": "S&P500", "^IXIC": "나스닥"}
    data_str = "현재 미국 증시 데이터:\n"
    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d") # 주간 흐름 파악을 위해 5일치 수집
            if len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((close - prev_close) / prev_close) * 100
                high_5d = hist['High'].max()
                low_5d = hist['Low'].min()
                data_str += f"- {name}: 현재가 {close:.2f} (전일대비 {change_pct:+.2f}%), 5일 최고치 {high_5d:.2f}, 5일 최저치 {low_5d:.2f}\n"
        except Exception as e:
            print(f"⚠️ Error fetching {symbol}: {e}")
    return data_str

def generate_blog_post(market_data):
    if not GEMINI_API_KEY:
        return "Error: Gemini API Key is missing."

    models_to_try = ['gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-1.5-flash-latest']
    model = None

    for attempt in range(1, MAX_RETRIES + 1):
        for m_name in models_to_try:
            try:
                test_model = genai.GenerativeModel(m_name)
                test_model.generate_content("Health check")
                model = test_model
                break
            except: continue
        if model: break
        if attempt < MAX_RETRIES: time.sleep(attempt * 2)

    if not model:
        return "Error: 모든 Gemini 모델 연결에 실패했습니다."

    now = datetime.datetime.now(SEOUL_TZ)
    today_date = now.strftime('%Y-%m-%d')
    full_now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # --- 파워 블로거 및 데이터 분석가 페르소나 주입 프롬프트 ---
    prompt = f"""
    [Role Definition]
    당신은 월 방문자 100만 명을 보유한 '미국 주식 전문 파워 블로거'이자 '냉철한 데이터 분석가'입니다.
    독자들이 이해하기 쉬운 언어를 사용하되, 전문적인 인사이트를 포함하세요. 데이터를 절대 왜곡하지 마세요.

    [Input Data]
    - 시장 데이터: {market_data}
    - 오늘 날짜: {today_date}
    - 중점 이슈: {FOCUS_TOPIC if FOCUS_TOPIC else '최근 1주일간의 주요 경제 지표 및 증시 흐름'}

    [Task] 최근 1주일간의 미국증시 뉴스 및 데이터를 바탕으로 블로그 포스팅을 작성하세요.

    [Guidelines & SEO]
    1. 제목: 클릭을 유도하는 자극적이면서도 핵심이 담긴 제목 (왜곡 없음)
    2. 키워드 필히 포함: '미국 증시', '나스닥 전망', '오늘의 주식'
    3. 본문 구조:
       - 상단에 "<p align='right'><small><i>AI Gemini에 의해 자동 생성된 리포트입니다.</i></small></p>" 명시.
       - 서론: 현재 시장의 분위기 요약 (공포/탐욕 단계 등 분석가의 시각).
       - 본론 1: 주요 3대 지수 분석 (제공된 수치를 바탕으로 마크다운 표 구성).
       - 본론 2: 특징주 및 주요 뉴스 해석 (관련 있는 분석과 링크 형태 포함).
       - 결론: 투자자를 위한 한 줄 요약 및 내일 관전 포인트.
    4. 가독성: 불렛 포인트(-), 볼드체(**), 표를 적극 활용하여 시각화할 것.

    [Output Format - Jekyll Front Matter]
    ---
    layout: post
    title: "AI가 생성한 제목"
    date: {full_now_str}
    categories: [경제·재테크, 미국증시]
    published: false
    ---
    (이후 본문 작성)
    """

    try:
        response = model.generate_content(prompt)
        text = response.text
        # 마크다운 블록 기호 제거
        text = text.replace("```markdown", "").replace("```", "").strip()
        return text
    except Exception as e:
        return f"Error during content generation: {e}"

def save_post(content):
    # 파일명 형식 수정: YYYY-MM-DD-title.md
    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    filename = f"{today}-us-market-analysis.md"
    filepath = f"_posts/{filename}"

    os.makedirs("_posts", exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def send_telegram_alert(filename):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    repo_name = os.environ.get("GITHUB_REPOSITORY", "jmp1533/therichway.github.io")
    # 이슈 생성 링크를 통한 수동 승인 유도
    issue_title = f"approve-{filename}"
    approve_url = f"https://github.com/{repo_name}/issues/new?title={issue_title}&body=포스팅을+공개하려면+Submit+new+issue를+누르세요."

    message = (
        f"📊 **[미국증시 리포트 생성 완료]**\n"
        f"분석 주제: {FOCUS_TOPIC if FOCUS_TOPIC else '주간 정기 시황'}\n"
        f"상태: **비공개(Draft)**\n\n"
        f"내용을 확인하신 후 아래 링크에서 승인하면 블로그에 즉시 공개됩니다.\n"
        f"[👉 포스팅 승인 및 발행하기]({approve_url})"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    print("🚀 분석 시작: 미국 시장 데이터 수집 중...")
    data = get_market_data()

    print("🧠 AI 분석 중: 전문 분석가 페르소나 적용...")
    post = generate_blog_post(data)

    if "Error" not in post:
        saved_file = save_post(post)
        print(f"✅ 생성 완료: {saved_file}")
        send_telegram_alert(saved_file)
    else:
        print(f"❌ 오류 발생: {post}")
        exit(1)