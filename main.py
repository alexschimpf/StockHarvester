from pprint import pprint
from api import YahooFinanceAPI, GoogleFinanceAPI, AlphaVantageStockAPI

yahoo_results = \
    YahooFinanceAPI.get_latest_quotes(symbols=("GOOG", "AMZN", "AAPL", "MSFT"))
print("--- Yahoo Finance latest quotes ---\n")
pprint(yahoo_results)

google_latest_results = \
    GoogleFinanceAPI.get_latest_quotes(symbols=("GOOG", "AMZN", "AAPL", "MSFT"))
print("\n--- Google Finance latest quotes ---\n")
pprint(google_latest_results)

google_historical_results = \
    GoogleFinanceAPI.get_historical_quotes(symbol="GOOG", start_date="8-20-2016", end_date="8-20-2017")
print("\n--- Google Finance historical quotes ---\n")
pprint(google_historical_results)

alphavantage_results = AlphaVantageStockAPI.get_historical_quotes(
    symbol="GOOG", time_series_type=AlphaVantageStockAPI.TimeSeriesType.TIME_SERIES_DAILY,
    output_size=AlphaVantageStockAPI.OutputSize.COMPACT)
print("\n--- AlphaVantage historical quotes ---\n")
pprint(alphavantage_results)