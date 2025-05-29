import requests
import config

def fetch_price_data():
    market_data_url = f"https://api.coingecko.com/api/v3/coins/{config.COIN_ID}?localization=false&tickers=false&market_data=true"
    ohlc_url = f"https   ://api.coingecko.com/api/v3/coins/{config.COIN_ID}/ohlc?vs_currency={config.VS_CURRENCY}&days=14"

    results = {}

    try:
        # Fetch market data (current price, percentage changes)
        response_market = requests.get(market_data_url)
        response_market.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
        market_data = response_market.json()["market_data"]

        results["current_price"] = market_data["current_price"][config.VS_CURRENCY]
        results["p1h"] = market_data.get("price_change_percentage_1h_in_currency", {}).get(config.VS_CURRENCY, 0)
        results["p24h"] = market_data.get("price_change_percentage_24h_in_currency", {}).get(config.VS_CURRENCY, 0)
        results["p7d"] = market_data.get("price_change_percentage_7d_in_currency", {}).get(config.VS_CURRENCY, 0)

        # Fetch OHLC data
        response_ohlc = requests.get(ohlc_url)
        response_ohlc.raise_for_status() # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
        results["ohlc"] = response_ohlc.json()
        # Enhanced debug print for OHLC data
        print(f"Debug: Total OHLC data points received: {len(results['ohlc'])}")
        print(f"Debug: First 3 OHLC data points: {results['ohlc'][:3]}")
        print(f"Debug: Last 3 OHLC data points: {results['ohlc'][-3:]}")

        return results
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from CoinGecko: {e}")
        return None
    except KeyError as e:
        print(f"Error parsing CoinGecko response (KeyError): {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        return None
