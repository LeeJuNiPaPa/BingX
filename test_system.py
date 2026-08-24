import sys
import json
from parser import parse_signal_text
from trader import OrderEngine
from config import current_config

# Ensure UTF-8 console output for emojis
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_tests():
    print("=" * 60)
    print("🧪 BingX 자연어 자동 매매 시스템 통합 테스트")
    print("=" * 60)

    sample_signal = """비트코인 롱 10배 🔼🔼
1차매수 76.5~77.4K 비중20%
2차매수 74.5~75.4K 비중20%
3차매수 72.5~73.4K 비중20%
4차매수 71.5~72.4K 비중20%
익절가 대기
손절가 대기"""

    print("\n1. 📥 시그널 메세지 파싱 테스트:")
    print("------------------------------------------------------------")
    signal = parse_signal_text(sample_signal)
    print(f"• 종목 (Symbol): {signal.symbol}")
    print(f"• 포지션 (Position): {signal.position_side} ({signal.leverage}배)")
    print(f"• 매수 차수 (Entries count): {len(signal.entries)} 단계")
    for entry in signal.entries:
        print(f"  - {entry.step}차매수: {entry.start_price:,.1f} ~ {entry.end_price:,.1f} USDT (비중 {entry.portion_pct:.0f}%)")
    print(f"• 익절가: {signal.take_profit} | 손절가: {signal.stop_loss}")

    assert signal.symbol == "BTC-USDT"
    assert signal.position_side == "LONG"
    assert signal.leverage == 10
    assert len(signal.entries) == 4
    print("✅ 1단계: 시그널 파싱 파이프라인 검증 성공!")

    print("\n2. ⚙️ N등분 분할 매수 주문 생성 테스트 (10/20/30등분):")
    print("------------------------------------------------------------")

    engine = OrderEngine()

    for split_n in [10, 20, 30]:
        res = engine.execute_signal(signal, custom_split_count=split_n)
        total_orders = sum(s.split_count for s in res.step_summaries)
        print(f"• {split_n}등분 설정시:")
        print(f"  - 총 분할 지정가 주문 개수: {total_orders} 개 ({len(res.step_summaries)}차 x {split_n}개)")
        first_step = res.step_summaries[0]
        print(f"  - 1차매수 범위: {first_step.orders[0]['price']} ~ {first_step.orders[-1]['price']} USDT")
        print(f"  - 1차매수 주문 1건당 수량: {first_step.orders[0]['quantity']} BTC")
        assert total_orders == 4 * split_n

    print("✅ 2단계: 10/20/30등분 분할 주문 계산 검증 성공!")

    print("\n============================================================")
    print("🎉 ALL TESTS PASSED! 모든 시스템 검증이 완료되었습니다.")
    print("============================================================")

if __name__ == "__main__":
    run_tests()
