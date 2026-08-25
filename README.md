# 🤖 BingX 자연어 자동 매매 & AI 텔레그램 봇

BingX 선물 거래소 연동 **자연어 시그널 분할 지정가 매매**, **실시간 시세 조회**, **Gemini AI 지식 대화** 및 **친근한 불알친구 페르소나**를 지원하는 통합 텔레그램 트레이딩 봇입니다.

---

## 🌟 주요 기능 (Key Features)

1. **🛡️ 자연어 시그널 파싱 & N등분 지정가 분할 매수 Grid**:
   - 카카오톡/텔레그램의 자연어 매매 시그널(예: `비트코인 롱 10배 1차매수 76.5~77.4K...`)을 자동 해석합니다.
   - 각 차수별 가격 범위를 **10/20/30등분 균등 지정가 분할 주문**으로 자동 생성하여 리스크를 분산합니다.
2. **✅ 안전 승인 매매 카드**:
   - 시그널 수신 시 거래소로 주문이 바로 전송되지 않으며, **매매 상세 내역 카드**를 미리 표시합니다.
   - 사용자가 카드의 **`[✅ 승인]`** 버튼을 클릭해야만 BingX 거래소로 실제 주문이 전송됩니다.
3. **📈 실시간 코인 시세 조회**:
   - `"1ETH가 몇 USDT?"`, `"비트코인 얼마야?"` 입력 시 BingX 거래소의 현재가, 24시간 변동률, 고가/저가를 즉시 응답합니다.
4. **🤖 Gemini AI 멀티 모델 자동 전환 (Failover)**:
   - Google Gemini AI와 연동되어 자유 질의응답 및 지식 대화를 지원합니다.
   - 특정 모델의 무료 한도 초과(`429 Resource Exhausted`) 또는 장애 시 `gemini-3.6-flash` ➡️ `gemini-2.5-flash` ➡️ `gemini-1.5-flash` 순으로 자동으로 전환되어 서비스가 끊기지 않습니다.
5. **👬 친근한 AI 페르소나 ('불알친구' 모드)**:
   - 편안한 반말과 유쾌한 장난끼, 든든한 우정을 자랑하는 절친 성격 모드가 적용되어 있습니다.
   - 텔레그램 내에서 `/persona` 명령어로 자유롭게 AI 성격을 커스텀할 수 있습니다.

---

## 📦 빠른 시작 (Quick Start)

### 1. 필수가상환경 및 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 2. `.env` 환경 변수 설정
`.env.example` 파일의 내용을 복사하여 `.env` 파일을 만들고 키 정보를 설정합니다:
```ini
# BingX API Credentials
BINGX_API_KEY=your_bingx_api_key
BINGX_SECRET_KEY=your_bingx_secret_key
BINGX_BASE_URL=https://open-api.bingx.com

# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ALLOWED_USER_IDS=

# AI LLM Config
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODELS=gemini-3.6-flash,gemini-2.5-flash,gemini-1.5-flash

# Default Trading Config
DEFAULT_SPLIT_COUNT=10
DEFAULT_MARGIN_TYPE=ISOLATED
```

### 3. 봇 실행
```bash
python telegram_bot.py
```

---

## 📌 주요 명령어 (Commands)

- `/start` 또는 `/help` : 사용 안내 및 주요 명령어 모음
- `/l` : 클릭 가능한 터치 메뉴 호출
- `/con` 또는 `/config` : 분할 수(10/20/30등분) 및 마진 모드(ISOLATED/CROSSED) 변경
- `/con 500` : 기본 매매 금액을 500 USDT로 직접 설정 (`/con auto` 로 잔고% 복원)
- `/bal` 또는 `/balance` : BingX 계좌 잔고 및 사용 가능 증거금 조회
- `/model` 또는 `/gemini` : Gemini AI 모델 우선순위 확인 및 변경
- `/persona` 또는 `/friend` : AI 성격 확인 및 커스텀 (`/persona reset` 으로 불알친구 모드 복원)

---

## 📜 변경 이력 (CHANGELOG)

### [v1.4.0] - 2026-08-25
#### ✨ 추가 기능 (Added)
- **AI 페르소나 ('불알친구' 모드) 시스템 도입**:
  - System Instruction을 적용하여 친근하고 유쾌한 절친 어조의 대화 모드 추가
- **`/persona` (`/friend`) 명령어 추가**:
  - 텔레그램 내에서 AI 성격을 자유롭게 변경하고 기본 '불알친구' 모드로 리셋할 수 있는 기능 지원
  - `.env` 파일의 `AI_PERSONA` 항목을 통한 영구 성격 설정 지원

---

### [v1.3.0] - 2026-08-25
#### ✨ 추가 기능 (Added)
- **Google Gemini AI 대화 엔진 연동**:
  - `gemini-3.6-flash` 최신 모델 기반 무제한 자유 지식 대화 기능 지원
- **Gemini 모델 우선순위 및 자동 전환 (Failover) 시스템**:
  - 무료 사용량 초과(HTTP 429 / Resource Exhausted) 또는 장애 발생 시 설정된 다음 모델로 자동 전환되는 로직 구현
- **`/model` (`/gemini`) 명령어 추가**:
  - 텔레그램 내에서 모델 우선순위 목록 조회 및 동적 변경 지원

---

### [v1.2.0] - 2026-08-25
#### ✨ 추가 기능 (Added)
- **BingX 실시간 코인 시세 조회 기능**:
  - `"1ETH가 몇 USDT?"`, `"비트코인 가격"` 등의 질문 시 BingX 실시간 현재가, 24시간 변동률, 고가/저가 조회 및 응답
- **기본 질의응답 및 상식 내장 엔진**:
  - 세계 수도 조회, 현재 날짜/시간, 간단한 사칙연산, 인사 및 안내 기능 탑재
- **메시지 의도 분석(Intent Classifier)**:
  - 매매 시그널 / 코인 시세 / 일반 대화를 자동 분류하여 응답하는 파이프라인 구현

---

### [v1.1.0] - 2026-08-25
#### 🐛 버그 수정 & 안정화 (Fixed & Improved)
- **BingX API 서명(Signature) 검증 오류 해결**:
  - HMAC-SHA256 서명이 포함된 URL Query String 바인딩 방식으로 POST 요청 구조를 개선하여 `code: 100001` 거부 문제 해결
- **주문 승인 카드 UI 가독성 개선**:
  - 1건당 분할 매수 수량 표시를 기존 코인 수량(BTC)에서 **USDT 금액** 단위로 변경
- **BingX V2 익절/손절(TP/SL) 파라미터 적용**:
  - `TAKE_PROFIT_MARKET`, `STOP_MARKET` 규격 JSON 파라미터 연동
- **계좌 잔액 캡핑 처리**:
  - 설정 금액이 잔액을 초과할 경우 사용 가능 잔액으로 자동 조정하여 `Insufficient margin` 에러 방지

---

### [v1.0.0] - 2026-08-25
#### 🚀 최초 릴리즈 (Initial Release)
- **자연어 매매 시그널 파서 (`parser.py`)**:
  - 텍스트 시그널에서 종목, 방향(LONG/SHORT), 레버리지, N차 매수 가격 범위, 비중, 익절가, 손절가 자동 추출
- **N등분 지정가 분할 매수 그리드 엔진 (`trader.py`)**:
  - 설정된 등분 수(10/20/30등분 등)에 맞춰 균등 분할 지정가 주문 생성
- **텔레그램 안전 승인 카드 인터페이스 (`telegram_bot.py`)**:
  - 시그널 수신 시 주문을 바로 실행하지 않고 미리보기 카드 제공 후 `[✅ 승인]` 클릭 시에만 실행되도록 설계
- **보안 설정**:
  - `.env` 및 `.gitignore`를 활용한 API Key 및 토큰 보안 관리 기반 구축
