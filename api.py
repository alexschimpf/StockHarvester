import requests
import logging
from app_config import APP_CONFIG
import enum
import json
from datetime import datetime
from collections import OrderedDict

LOGGER = logging.getLogger("api")


class AlphaVantageStockAPI(object):

    # https://www.alphavantage.co/documentation/

    API_TIMEOUT = 10
    QUOTES_URL = "https://www.alphavantage.co/query"

    class TimeSeriesType(enum.Enum):
        TIME_SERIES_INTRADAY = 0
        TIME_SERIES_DAILY = 1
        TIME_SERIES_DAILY_ADJUSTED = 2
        TIME_SERIES_WEEKLY = 3
        TIME_SERIES_MONTHLY = 4

    class OutputSize(enum.Enum):
        COMPACT = 0
        FULL = 1

    @classmethod
    def get_historical_quotes(cls, symbol, time_series_type, output_size):
        params = dict(
            function=time_series_type.name,
            outputsize=output_size.name.lower(),
            symbol=symbol,
            apikey=APP_CONFIG["ALPHAVANTAGE_API_KEY"])
        response = requests.get(url=cls.QUOTES_URL,
                                params=params,
                                timeout=cls.API_TIMEOUT)
        if response.status_code == 200:
            return cls._get_quotes_by_period(response.text)
        else:
            raise Exception("Quotes API returned status code: {}".format(response.status_code))

    @classmethod
    def _get_quotes_by_period(cls, response):
        if not response:
            raise Exception("Quotes response is empty!")

        quotes_by_period = OrderedDict()
        response = json.loads(response)
        possible_keys = [key for key in response.keys() if "time series" in key.lower()]
        if len(possible_keys) > 1:
            raise Exception("Couldn't determine correct time series key in: {}".format(",".join(possible_keys)))
        time_series_key = possible_keys[0]
        for period, quote in response[time_series_key].items():
            quotes_by_period[datetime.strptime(period, "%Y-%m-%d")] = dict(
                open=quote["1. open"],
                high=quote["2. high"],
                low=quote["3. low"],
                close=quote["4. close"],
                volume=quote["5. volume"]
            )
        return quotes_by_period


class GoogleFinanceAPI(object):

    API_TIMEOUT = 10
    HISTORIAL_QUOTES_URL = "https://www.google.com/finance/historical"
    LATEST_QUOTES_URL = "http://finance.google.com/finance/info"
    LATEST_QUOTE_FIELDS = dict(
        id="Id",
        t="Stock Symbol",
        e="Index",
        l="Last Trade Price",
        l_cur="Last Trade With Currency",
        ltt="Last Trade Time",
        lt_dts="Last Trade Date Time",
        lt="Last Trade Date Time Long",
        div="Dividend",
        yld="Yield",
        s="Last Trade Size",
        c="Change",
        cp="Change Percent",
        el="Ext Hrs Last Trade Price",
        el_cur="Ext Hrs Last Trade With Currency",
        elt="Ext Hrs Last Trade Date Time Long",
        ec="Ext Hrs Change",
        ecp="Ext Hrs Change Percent",
        pcls_fix="Previous Close Price"
    )

    @classmethod
    def get_latest_quotes(cls, symbols):
        params = dict(
            client="ig",
            q=",".join(symbols))
        response = requests.get(url=cls.LATEST_QUOTES_URL,
                                params=params,
                                timeout=cls.API_TIMEOUT)
        if response.status_code == 200:
            return cls._get_quotes_by_symbol(response.text)
        else:
            raise Exception("Quotes API returned status code: {}".format(response.status_code))

    @classmethod
    def get_historical_quotes(cls, symbol, start_date, end_date):
        params = dict(
            q=symbol,
            startdate=start_date,
            enddate=end_date,
            output="csv")
        response = requests.get(url=cls.HISTORIAL_QUOTES_URL,
                                params=params,
                                timeout=cls.API_TIMEOUT)
        if response.status_code == 200:
            return cls._get_quotes_by_date(response.text)
        else:
            raise Exception("Quotes API returned status code: {}".format(response.status_code))

    @classmethod
    def _get_quotes_by_date(cls, response):
        if not response:
            raise Exception("Quotes response is empty!")

        quotes_by_date = {}
        for quote in response.split("\n")[1:]:
            if not quote:
                continue
            date, open, high, low, close, volume = quote.split(",")
            quotes_by_date[date] = dict(
                open=open,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
        return quotes_by_date

    @classmethod
    def _get_quotes_by_symbol(cls, response):
        if not response:
            raise Exception("Quotes response is empty!")

        quotes_by_symbol = {}
        response = json.loads(response[4:])
        for quote in response:
            reformatted_quote = {}
            for key, value in quote.items():
                if key not in cls.LATEST_QUOTE_FIELDS:
                    print(key)
                    continue
                reformatted_quote[cls.LATEST_QUOTE_FIELDS[key]] = value
            quotes_by_symbol[quote["t"]] = reformatted_quote

        return quotes_by_symbol
        

class YahooFinanceAPI(object):

    # TODO: https://github.com/c0redumb/yahoo_quote_download/blob/master/yahoo_quote_download/yqd.py

    API_TIMEOUT = 10
    QUOTES_URL = "http://download.finance.yahoo.com/d/quotes.csv"
    USED_FIELDS = "sd1l1yrghm3m4vee7e8e9j1"
    QUOTES_FIELDS = dict(
        d="dividend/share",
        e="earnings/share",
        e7="eps estimate current year",
        e8="eps estimate next year",
        e9="eps estimate next quarter",
        g="day's low",
        h="day's high",
        j="52-week low",
        k="52-week high",
        j1="market capitalization",
        m3="50-day moving average",
        m4="200-day moving average",
        n="name",
        o="open",
        p="previous close",
        p5="price/sales",
        p6="price/book",
        r="p/e ratio",
        r5="peg ratio",
        r6="price/eps estimate current year",
        r7="price/eps estimate next year",
        s="symbol",
        t8="1 year target price",
        v="volume",
        x="stock exchange", 
        y="dividend yield"
    )

    @classmethod
    def get_latest_quotes(cls, symbols):
        params = dict(
            s='+'.join(symbols),
            f=cls.USED_FIELDS)
        response = requests.get(url=cls.QUOTES_URL,
                                params=params,
                                timeout=cls.API_TIMEOUT)
        if response.status_code == 200:
            return cls._get_data_by_symbol(response.text)
        else:
            raise Exception("Quotes API returned status code: {}".format(response.status_code))

    @classmethod
    def _get_data_by_symbol(cls, response):
        if not response:
            raise Exception("Quotes response is empty!")

        data_by_symbol = {}
        response = response.split("\n")
        for quote in response:
            if not quote:
                continue

            symbol, date, last_trade, dividend_yield, pe_ratio, low, high, moving_average_50, \
            moving_average_200, volume, earnings_per_share, eps_curr_year, eps_next_year, \
            eps_next_quarter, market_cap = quote.split(',')
            data_by_symbol[symbol] = dict(
                date=date,
                last_trade=last_trade,
                dividend_yield=dividend_yield,
                pe_ratio=pe_ratio,
                low=low,
                high=high,
                moving_average_50=moving_average_50,
                moving_average_200=moving_average_200,
                volume=volume,
                earnings_per_share=earnings_per_share,
                eps_curr_year=eps_curr_year,
                eps_next_year=eps_next_year,
                eps_next_quarter=eps_next_quarter,
                market_cap=market_cap
            )

        return data_by_symbol
