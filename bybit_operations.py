from pybit.unified_trading import HTTP
import os # For potential future direct use, though API keys will be imported initially.

# IMPORTANT: The following global variables are expected to be imported from watch_coin.py
# or defined/loaded here in a future refactoring step if this module becomes more independent.
# For now, they are accessed via watch_coin.py's global scope when these functions are called from there.
# - BYBIT_API_KEY
# - BYBIT_API_SECRET
# - BYBIT_QUOTE_CURRENCY (used in place_spot_market_order for message formatting)
# - notify (used in place_spot_market_order for notifications)

def get_bybit_client():
    # Ensure global BYBIT_API_KEY and BYBIT_API_SECRET are accessible
    # These would typically be passed as arguments or accessed via a config module/object
    # For now, assuming they are available in the scope where this function is called from (watch_coin.py)
    # If BYBIT_API_KEY and BYBIT_API_SECRET are not directly available, this function will need modification
    # or they must be imported from watch_coin.
    
    # This function relies on BYBIT_API_KEY and BYBIT_API_SECRET being available globally
    # from the calling script (watch_coin.py in this case).
    if not os.environ.get("BYBIT_API_KEY") or not os.environ.get("BYBIT_API_SECRET"): # Re-check within function for clarity
        print("Warning: Bybit API Key or Secret not found in environment. Ensure they are set.")
        # Attempting to use potentially imported globals as a fallback, though direct env check is better for standalone use.
        # This part might be redundant if direct global imports are confirmed in the next step.
        # For now, this illustrates a dependency.
        # The subtask specifies API keys are still globally defined in watch_coin.py at this stage.
        # So, direct use of BYBIT_API_KEY, BYBIT_API_SECRET (from watch_coin) is implied.
        # Let's assume they will be imported in the next step.
        # For this step, we write the function as if those names are available in its scope.
        # The placeholder comment above the function definition already notes this.
        # To make this function truly work when called from watch_coin.py *before* imports are fixed,
        # it would need to access watch_coin.BYBIT_API_KEY, or these are passed as args.
        # The prompt states: "API keys... are still globally defined in watch_coin.py at this stage"
        # This implies these functions, when *called* from watch_coin.py, can see them.
        # However, good practice is to make dependencies explicit.
        # The *next* subtask is to import them. So for now, we assume they are magically available.
        # To avoid NameError if run standalone, I should refer to them as os.environ.get() here or ensure they are passed.
        # The original code used global BYBIT_API_KEY directly. I will keep that structure for now,
        # anticipating the import step.
        pass # The global variables will be handled by imports in the next step

    try:
        # Initialize for Unified Trading Account.
        # IMPORTANT: testnet=True connects to Bybit's test environment.
        # For live trading, set testnet=False. Ensure you understand the risks
        # and have tested thoroughly before trading with real funds.
        session = HTTP(
            testnet=True,  # Use True for testnet, False for live
            api_key=os.environ.get("BYBIT_API_KEY"), # Direct use of global from watch_coin will be fixed by import
            api_secret=os.environ.get("BYBIT_API_SECRET"), # Direct use of global from watch_coin will be fixed by import
        )
        print("Successfully connected to Bybit (Testnet).")
        return session
    except Exception as e:
        print(f"Error connecting to Bybit: {e}")
        return None


def get_spot_balance(client, currency_symbol):
    if not client:
        return 0.0
    try:
        response = client.get_wallet_balance(accountType="UNIFIED", coin=currency_symbol) # For UTA, use UNIFIED. For older Spot, use "SPOT"
        if response and response.get('retCode') == 0 and response.get('result', {}).get('list'):
            coin_list_data = response['result']['list'] 
            if coin_list_data: 
                account_balance_info = coin_list_data[0]
                coin_data_list = account_balance_info.get('coin', [])
                if coin_data_list:
                    for c_data in coin_data_list:
                        if c_data.get('coin') == currency_symbol:
                             return float(c_data.get('availableToWithdraw', 0.0)) 
                    print(f"Warning: {currency_symbol} not found in Bybit balance response coin list.")
                    return 0.0 
                else:
                    print(f"Warning: No coin data in Bybit balance response for {currency_symbol}.")
                    return 0.0 
            else:
                print(f"Warning: Empty list in Bybit balance response for {currency_symbol}.")
                return 0.0 
        else:
            print(f"Error fetching balance for {currency_symbol}: {response.get('retMsg', 'Unknown error')}")
            return 0.0
    except Exception as e:
        print(f"Exception fetching balance for {currency_symbol}: {e}")
        return 0.0


def place_spot_market_order(client, trading_symbol, order_side, order_quantity, bybit_quote_currency, notify_func):
    # Parameters bybit_quote_currency and notify_func added to make dependencies explicit
    if not client:
        return None
    try:
        str_order_quantity = str(order_quantity)

        response = client.place_order(
            category="spot",
            symbol=trading_symbol,
            side=order_side,
            orderType="Market",
            qty=str_order_quantity,
        )
        if response and response.get('retCode') == 0:
            order_id = response.get('result', {}).get('orderId', 'N/A')
            base_currency_traded = trading_symbol.replace(bybit_quote_currency, '') 
            success_msg = f"Bybit: Successfully placed {order_side} order for {order_quantity} {base_currency_traded}: Order ID {order_id}"
            print(success_msg)
            notify_func(success_msg) 
            return response['result']
        else:
            error_msg = response.get('retMsg', 'Unknown error')
            print(f"Error placing {order_side} order for {trading_symbol}: {error_msg}")
            notify_func(f"Bybit order error: {error_msg}") 
            return None
    except Exception as e:
        print(f"Exception placing {order_side} order for {trading_symbol}: {e}")
        notify_func(f"Bybit order exception: {str(e)}") 
        return None
