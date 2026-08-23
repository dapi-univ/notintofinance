import math
from datetime import date, timedelta
from decimal import Decimal

from app.schemas.domain import MarketBar, ProviderHistory, ProviderUniverse, StockIdentity

MOCK_STOCKS = (
    ("BBCA", "Bank Central Asia Tbk.", Decimal("8450")),
    ("ANTM", "Aneka Tambang Tbk.", Decimal("3120")),
    ("TLKM", "Telkom Indonesia (Persero) Tbk.", Decimal("2890")),
    ("ASII", "Astra International Tbk.", Decimal("5175")),
    ("GOTO", "GoTo Gojek Tokopedia Tbk.", Decimal("74")),
    ("BMRI", "Bank Mandiri (Persero) Tbk.", Decimal("5480")),
)


class MockMarketDataProvider:
    name = "mock"

    async def get_stock_history(
        self,
        ticker: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 260,
    ) -> ProviderHistory:
        code = ticker.upper()
        try:
            index, (matched, name, base) = next(
                (index, row) for index, row in enumerate(MOCK_STOCKS) if row[0] == code
            )
        except StopIteration as error:
            raise KeyError(code) from error
        bars = _generate_bars(base, index, limit=max(limit, 120))
        if date_from:
            bars = [bar for bar in bars if bar.trade_date >= date_from]
        if date_to:
            bars = [bar for bar in bars if bar.trade_date <= date_to]
        return ProviderHistory(
            stock=StockIdentity(ticker=matched, company_name=name),
            bars=bars[-limit:],
        )

    async def get_daily_market_summary(
        self, *, trade_date: date | None = None
    ) -> list[ProviderHistory]:
        histories = [await self.get_stock_history(row[0], limit=260) for row in MOCK_STOCKS]
        output: list[ProviderHistory] = []
        for history in histories:
            eligible = [
                bar for bar in history.bars if trade_date is None or bar.trade_date <= trade_date
            ]
            if eligible:
                output.append(ProviderHistory(stock=history.stock, bars=[eligible[-1]]))
        return output

    async def get_stock_universe(self) -> ProviderUniverse:
        stocks = [
            StockIdentity(ticker=ticker, company_name=name) for ticker, name, _base in MOCK_STOCKS
        ]
        return ProviderUniverse(stocks=stocks, total=len(stocks))


def _generate_bars(base: Decimal, seed: int, *, limit: int) -> list[MarketBar]:
    end = date(2026, 8, 21)
    cursor = end
    dates: list[date] = []
    while len(dates) < limit:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    dates.reverse()

    bars: list[MarketBar] = []
    previous = base
    for index, trade_date in enumerate(dates):
        wave = Decimal(str(math.sin((index + seed * 5) / 8)))
        drift = Decimal(index - limit // 2) * base * Decimal("0.00035")
        close = max(
            Decimal("1"), (base + drift + wave * base * Decimal("0.035")).quantize(Decimal("1"))
        )
        open_price = max(
            Decimal("1"),
            (previous * (Decimal("1") + Decimal(str(math.cos(index + seed) * 0.004)))).quantize(
                Decimal("1")
            ),
        )
        high = max(open_price, close) + max(
            Decimal("1"), (base * Decimal("0.008")).quantize(Decimal("1"))
        )
        low = max(
            Decimal("1"),
            min(open_price, close)
            - max(Decimal("1"), (base * Decimal("0.007")).quantize(Decimal("1"))),
        )
        volume = 12_000_000 + ((index * 7919 + seed * 2_300_000) % 38_000_000)
        frequency = 2_200 + ((index * 193 + seed * 811) % 9_000)
        bars.append(
            MarketBar(
                trade_date=trade_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                previous=previous,
                volume_shares=volume,
                value_idr=close * volume,
                frequency=frequency,
                foreign_buy_shares=volume // 5,
                foreign_sell_shares=volume // 6,
                source="mock",
            )
        )
        previous = close
    return bars
