import datetime
import pprint
import leather
from api import AlphaVantageStockAPI
from concurrent.futures import ThreadPoolExecutor, as_completed


class Analyzer(object):

    MIN_HOLD_DAYS = 7
    GAIN_PERCENT_TARGET = 0.15
    LOSS_PERCENT_FLOOR = 0.08

    @classmethod
    def analyze(cls, symbols, start_date=None):
        analysis_by_symbol = {}
        futures = []
        with ThreadPoolExecutor(max_workers=min(len(symbols), 4)) as executor:
            for symbol in symbols:
                analyze_fn = lambda: cls._analyze(symbol=symbol, start_date=start_date)
                future = executor.submit(analyze_fn)
                futures.append(future)
            for future in as_completed(futures):
                analysis = future.result()
                analysis_by_symbol[analysis["symbol"]] = analysis
        return analysis_by_symbol

    @classmethod
    def _analyze(cls, symbol, start_date):
        """
        AATR Rating = Average Anytime Trade Return

        Say you buy a stock at price P.
        After holding the stock for M days, stop and sell if:
            1. Current price <= P * (1 - LOSS_PERCENT_FLOOR)
            2. If current price >= P * (1 + GAIN_PERCENT_TARGET)

        To get the AATR Rating, apply this simple strategy from start_date until today,
        and then average the returns (negative or positive) from each.

        This should give us some kind of idea of our general odds based on a simple
        lower/upper limit strategy. This "should" be similar to the average trend line but is
        also affected by volatility.
        """
        num_wins = 0
        num_losses = 0
        days_til_loss = []
        days_til_gain = []
        average_returns = []
        average_returns_by_year = {}
        average_returns_by_month = {}
        historical_quotes = AlphaVantageStockAPI.get_historical_quotes(
            symbol=symbol, time_series_type=AlphaVantageStockAPI.TimeSeriesType.TIME_SERIES_DAILY,
            output_size=AlphaVantageStockAPI.OutputSize.FULL)
        for date in sorted(historical_quotes):
            if start_date and date < start_date:
                continue
            if date + datetime.timedelta(days=cls.MIN_HOLD_DAYS) >= datetime.datetime.today():
                continue

            buy_info = cls._get_buy_info(buy_date=date, historical_quotes=historical_quotes)
            try:
                average_returns_by_year[date.year].append(buy_info["g/l"])
            except KeyError:
                average_returns_by_year[date.year] = [buy_info["g/l"]]
            try:
                average_returns_by_month["{}_{}".format(date.year, date.month)].append(buy_info["g/l"])
            except KeyError:
                average_returns_by_month["{}_{}".format(date.year, date.month)] = [buy_info["g/l"]]

            if buy_info["g/l"] > 0:
                days_til_gain.append(buy_info["days"])
                num_wins += 1
            elif buy_info["g/l"] < 0:
                days_til_loss.append(buy_info["days"])
                num_losses += 1
            average_returns.append(buy_info["g/l"])

        aatr_by_month = {}
        for month, returns in average_returns_by_month.items():
            aatr_by_month[datetime.datetime.strptime(month, "%Y_%m")] = sum(returns) / (len(returns) or 1)

        aatr_by_year = {}
        for year, returns in average_returns_by_year.items():
            aatr_by_year[year] = sum(returns) / (len(returns) or 1)

        average_days_til_loss = sum(days_til_loss) / (len(days_til_loss) or 1)
        average_days_til_gain = sum(days_til_gain) / (len(days_til_gain) or 1)
        average_gain_loss = sum(average_returns) / (len(average_returns) or 1)
        win_chance = num_wins / (num_wins + num_losses)
        return dict(
            symbol=symbol,
            num_wins=num_wins,
            num_losses=num_losses,
            average_gain_loss=average_gain_loss,
            average_days_til_gain=average_days_til_gain,
            average_days_til_loss=average_days_til_loss,
            win_chance=win_chance,
            average_anyimte_trade_return_by_month=aatr_by_month,
            average_anyimte_trade_return_by_year=aatr_by_year
        )


    @classmethod
    def _get_buy_info(cls, buy_date, historical_quotes):
        day = 0
        price_diff = 0
        curr_price = 0
        start_price = float(historical_quotes[buy_date]["close"])
        loss_price = start_price * (1 - cls.LOSS_PERCENT_FLOOR)
        gain_price = start_price * (1 + cls.GAIN_PERCENT_TARGET)
        sorted_dates = sorted(historical_quotes)
        for date in sorted_dates:
            quote = historical_quotes[date]
            curr_price = float(quote["close"])
            price_diff = curr_price - start_price

            if date < buy_date:
                continue

            if day >= cls.MIN_HOLD_DAYS:
                if curr_price <= loss_price or curr_price >= gain_price:
                    return {
                        "g/l": price_diff / (start_price or 1),
                        "days": day,
                        "buy_price": start_price,
                        "sell_price": curr_price
                    }
            day += 1
        return {
            "g/l": price_diff / start_price,
            "days": day,
            "buy_price": start_price,
            "sell_price": curr_price
        }


if __name__ == "__main__":
    for index, symbols in enumerate((("WB", "BAC", "SHOP", "CHKDG"),
                                     ("FB", "AAPL", "BABA", "AMZN"),
                                     ("JNJ", "JPM", "VSA", "PFE"))):
        results = Analyzer.analyze(symbols=symbols, start_date=datetime.datetime.strptime("2012-01-01", "%Y-%m-%d"))
        pprint.pprint(results)

        chart = leather.Chart('AATR By Month/Year')
        for symbol, result in results.items():
            average_anyimte_trade_return_by_month = result["average_anyimte_trade_return_by_month"]
            average_anyimte_trade_return_by_year = result["average_anyimte_trade_return_by_year"]
            min_year = min(average_anyimte_trade_return_by_year)

            month_line = []
            for month in sorted(average_anyimte_trade_return_by_month):
                aatr = average_anyimte_trade_return_by_month[month]
                x = ((int(month.year) - int(min_year)) * 12) + int(month.month) - 1
                y = float(aatr)
                month_line.append((x, y))
            chart.add_line(month_line, name="{} (Monthly)".format(symbol))

            # year_line = []
            # for year in sorted(average_anyimte_trade_return_by_year):
            #     aatr = average_anyimte_trade_return_by_year[year]
            #     x = (int(year) - int(min_year)) * 12
            #     y = float(aatr)
            #     year_line.append((x, y))
            # year_line.append((year_line[-1][0] + 12, year_line[-1][1]))
            # chart.add_line(year_line, name="{} (Yearly)".format(symbol))

        chart_ouput_path = "/home/schimpf1/Desktop/stock_harvester_results_{}.svg".format("+".join(symbols))
        chart.to_svg(chart_ouput_path)
        print("\nChart results were written to {}".format(chart_ouput_path))
