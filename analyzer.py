import datetime
import pprint
import leather
from api import AlphaVantageStockAPI
from concurrent.futures import ThreadPoolExecutor, as_completed


class Analyzer(object):

    MIN_HOLD_DAYS = 7
    GAIN_PERCENT_TARGET = 0.2
    LOSS_PERCENT_FLOOR = 0.08
    MAX_WORKERS = 4
    NUM_DAYS_AVERAGED = 50

    @classmethod
    def analyze(cls, symbols, start_date=None, num_days_averaged=None):
        num_days_averaged = num_days_averaged or cls.NUM_DAYS_AVERAGED

        analysis_by_symbol = {}
        futures = []
        with ThreadPoolExecutor(max_workers=min(len(symbols), cls.MAX_WORKERS)) as executor:
            for symbol in symbols:
                future = executor.submit(cls._analyze, symbol, start_date, num_days_averaged)
                futures.append(future)
            for future in as_completed(futures):
                analysis = future.result()
                analysis_by_symbol[analysis["symbol"]] = analysis
        return analysis_by_symbol

    @classmethod
    def _analyze(cls, symbol, start_date, num_days_averaged):
        """
        Say you buy a stock at price P.
        After holding the stock for M days, stop and sell if:
            1. Current price <= P * (1 - LOSS_PERCENT_FLOOR)
            2. If current price >= P * (1 + GAIN_PERCENT_TARGET)

        If we hit the upper limit, this counts as a "win".
        If we hit the lower limit, this counts as a "loss".

        To get the score, apply this simple strategy for the given period, and then average the win chances.
        """

        historical_quotes = AlphaVantageStockAPI.get_historical_quotes(
            symbol=symbol, time_series_type=AlphaVantageStockAPI.TimeSeriesType.TIME_SERIES_DAILY,
            output_size=AlphaVantageStockAPI.OutputSize.FULL)

        total_wins = 0
        total_losses = 0
        results_by_date = {}
        sorted_dates = sorted(historical_quotes)
        for day, date in enumerate(sorted_dates):
            if start_date and date < start_date:
                # We haven't reached the start_date yet
                continue

            if date + datetime.timedelta(days=cls.MIN_HOLD_DAYS) >= datetime.datetime.today():
                # We haven't held the stock for enough time yet
                # TODO: Should I still check if the lower limit is reached?
                continue

            results = cls._get_results(buy_date=date, historical_quotes=historical_quotes)
            num_hold_days = results["days"]
            if results["g/l"] > 0:
                total_wins += 1
                results_by_date[date] = {
                    "is_win": True,
                    "num_hold_days": num_hold_days
                }
            elif results["g/l"] < 0:
                total_losses += 1
                results_by_date[date] = {
                    "is_win": False,
                    "num_hold_days": num_hold_days
                }

        day = 0
        period = 0
        num_period_wins = 0
        num_period_losses = 0
        win_rate_by_period = {}
        for date, result in results_by_date.items():
            is_win = result["is_win"]

            total_wins += (1 if is_win else 0)
            num_period_wins += (1 if is_win else 0)

            total_losses += (0 if is_win else 1)
            num_period_losses += (0 if is_win else 1)

            day = (day + 1) % num_days_averaged
            if day == 0:
                win_rate_by_period[period] = \
                    num_period_wins / ((num_period_wins + num_period_losses) or 1)
                num_period_wins = 0
                num_period_losses = 0
                period += 1

        return dict(
            symbol=symbol,
            total_wins=total_wins,
            total_losses=total_losses,
            win_rate_by_period=win_rate_by_period
        )

    @classmethod
    def _get_results(cls, buy_date, historical_quotes):
        day = 0
        price_diff = 0
        curr_price = 0
        start_price = float(historical_quotes[buy_date]["close"])
        floor_price = start_price * (1 - cls.LOSS_PERCENT_FLOOR)
        target_price = start_price * (1 + cls.GAIN_PERCENT_TARGET)
        sorted_dates = sorted(historical_quotes)
        for date in sorted_dates:
            quote = historical_quotes[date]
            curr_price = float(quote["close"])
            price_diff = curr_price - start_price

            if date < buy_date:
                continue

            if day >= cls.MIN_HOLD_DAYS:
                if curr_price <= floor_price or curr_price >= target_price:
                    return {
                        "g/l": price_diff / (start_price or 1),
                        "days": day,
                        "buy_price": start_price,
                        "sell_price": curr_price
                    }
            day += 1
        return {
            "g/l": price_diff / (start_price or 1),
            "days": day,
            "buy_price": start_price,
            "sell_price": curr_price
        }


if __name__ == "__main__":
    analyzed_symbols = (
        ("SHOP", "CHKDG", "NKE", "KO"),
        ("FB", "AAPL", "BABA", "AMZN"),
        ("JNJ", "JPM", "VSA", "PFE"),
        ("GOOG", "FB", "VZA", "T")
    )
    for index, symbols in enumerate(analyzed_symbols):
        all_results = Analyzer.analyze(
            symbols=symbols, start_date=datetime.datetime.strptime("2000-01-01", "%Y-%m-%d"))
        # pprint.pprint(all_results)

        chart = leather.Chart('Win Rate By {}-Day Period'.format(Analyzer.NUM_DAYS_AVERAGED))
        for symbol, results in all_results.items():
            month_line = [
                (period, results["win_rate_by_period"][period]) for period in sorted(results["win_rate_by_period"])]
            chart.add_line(month_line, name="{} (Monthly)".format(symbol))

        chart_ouput_path = \
            "/home/schimpf1/Desktop/projects/StockHarvester/test/stock_harvester_results_{}.svg".format("+".join(symbols))
        chart.to_svg(chart_ouput_path)
        print("\nChart results were written to {}".format(chart_ouput_path))
