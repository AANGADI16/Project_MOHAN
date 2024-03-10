from kiteconnect import KiteConnect
import pandas as pd
import os
import pyotp
from datetime import datetime, time, timedelta
import json
import requests
import pytz
from time import sleep
import csv
from tqdm import tqdm  # Import tqdm for progress bars
import time as tm

bought_quantities = {}

creds = {'user_id':"SO8558",'password':"Abhi$hekQ16",'totp_key':"HKDJTKIB6VOZ5XBHCEEC65TRIOM6CITR",'api_key':'dhqso54nt4ui6ka5', 'api_secret':'z3j37dln7sfswh34bribrbvlaybgu13h' }
     
base_url = "https://kite.zerodha.com"
login_url = "https://kite.zerodha.com/api/login"
twofa_url = "https://kite.zerodha.com/api/twofa"
instruments_url = "https://api.kite.trade/instruments"

session = requests.Session()
response = session.post(login_url,data={'user_id':creds['user_id'],'password':creds['password']})
request_id = json.loads(response.text)['data']['request_id']
twofa_pin = pyotp.TOTP(creds['totp_key']).now()
response_1 = session.post(twofa_url,data={'user_id':creds['user_id'],'request_id':request_id,'twofa_value':twofa_pin,'twofa_type':'totp'})
kite = KiteConnect(api_key=creds['api_key'])
kite_url = kite.login_url()


try:
  session.get(kite_url)
except Exception as e:
  e_msg = str(e)
  #print(e_msg)
  request_token = e_msg.split('request_token=')[1].split(' ')[0].split('&action')[0]
  print('Successful Login with Request Token:{}'.format(request_token))

access_token = kite.generate_session(request_token,creds['api_secret'])['access_token']
kite.set_access_token(access_token)

def get_holdings(symbols):
    """Function to retrieve holdings for specific stocks from Kite."""
    holdings = kite.holdings()
    specific_holdings = [holding for holding in holdings if holding['tradingsymbol'] in symbols]
    # print(specific_holdings)
    return specific_holdings

symbols_to_monitor = ["INDBANK",
                      	"AARTIIND",
                          "AARTIPHARM",
                          "ADVENZYMES",
                          "BAJAJHIND",
                          "CLEAN",
                          "HAPPSTMNDS",
                          "ENTERO",
                          "FEDFINA",
                        "PATELENG",	
                        "SBICARD",	
                        "AWL",	
                        "SUTLEJTEX",	
                        "KHAICHEM",	
                        "JWL",	
                        "KPITTECH",	
                        "HERCULES",	
                        "MSUMI",	
                        "JPPOWER-BE",	
                        "ISMTLTD",	
                        "HDFCBANK",	
                        "ATGL",	
                        "INDUSTOWER"]
# specific_holdings = get_holdings(symbols_to_monitor)


# get_holdings()

def fetch_historical_data(symbol, from_date, to_date, interval):
    """Function to fetch historical data for a given symbol."""
    historical_data = kite.historical_data(
        instrument_token=symbol,
        from_date=from_date,
        to_date=to_date,
        interval=interval
    )
    return pd.DataFrame(historical_data)


def calculate_holding_age(tradebook_path, symbol):
    """
    Function to calculate the holding age for a specific symbol based on the tradebook data.

    Args:
    - tradebook_path (str): Path to the tradebook CSV file.
    - symbol (str): Symbol for which holding age is to be calculated.

    Returns:
    - int: Holding age in days for the specified symbol.
    """
    # Read tradebook CSV file
    tradebook_df = pd.read_csv(tradebook_path)

    # Filter data where trade_type is 'buy' and symbol matches
    symbol_buy_trades_df = tradebook_df[(tradebook_df['trade_type'] == 'buy') & (tradebook_df['symbol'] == symbol)]

    # Find the latest trade_date for the symbol
    latest_trade_date = symbol_buy_trades_df['trade_date'].max()

    # Calculate holding age for the symbol
    if pd.notnull(latest_trade_date):
        current_date = datetime.now()
        latest_trade_date = datetime.strptime(latest_trade_date, "%d-%m-%Y")  # Convert to datetime object
        holding_age = (current_date - latest_trade_date).days
        return holding_age
    else:
        # If no trade found for the symbol, return None
        return None

def get_bought_price(tradebook_path, symbol):
    """
    Function to get the bought price for a specific symbol based on the tradebook data.

    Args:
    - tradebook_path (str): Path to the tradebook CSV file.
    - symbol (str): Symbol for which bought price is to be retrieved.

    Returns:
    - float: Bought price for the specified symbol.
    """
    # Read tradebook CSV file
    tradebook_df = pd.read_csv(tradebook_path)

    # Filter data where trade_type is 'buy' and symbol matches
    symbol_buy_trades_df = tradebook_df[(tradebook_df['trade_type'] == 'buy') & (tradebook_df['symbol'] == symbol)]

    # Find the latest trade_date for the symbol
    latest_trade_date = symbol_buy_trades_df['trade_date'].max()

    # If no trade found for the symbol, return None
    if pd.isnull(latest_trade_date):
        return None

    # Get the bought price for the latest trade
    bought_price = symbol_buy_trades_df.loc[symbol_buy_trades_df['trade_date'] == latest_trade_date, 'price'].iloc[0]
    return bought_price

# Example usage:
tradebook_path = "tradebook.csv"  # Replace with the actual file path


def monitor_holdings(holdings):
    """Function to monitor holdings and apply selling conditions."""
    # while True:
        # Check if it's trading time
        # if is_trading_time():
    for holding in holdings:
        symbol = holding['tradingsymbol']

        holding_age = calculate_holding_age(tradebook_path, symbol)
        print(f"Holding age for {symbol}: {holding_age} days")

        bought_price = get_bought_price(tradebook_path, symbol)
        print(f"Bought price for {symbol}: {bought_price}")


        # Fetch historical data
        historical_data = fetch_historical_data(holding['instrument_token'], from_date, to_date, interval)
        # Check if stock has crossed 30-day high

        # if holding['average_price'] > historical_data['close'].tail(30).max():
        #     print(f"{symbol} has crossed its 30-day high.")
            # Calculate overall gain
        # overall_gain = ((holding['last_price'] - holding['average_price']) / holding['average_price']) * 100
        overall_gain = ((holding['last_price']- holding['average_price']) / holding['average_price']) * 100
        # If overall gain is 25% within 4 weeks
        if overall_gain >= 25 and holding_age <= 20:
            # Move stop loss to 20% of the gain price
            stop_loss_price = holding['average_price'] * 1.2
            print(f"Moving stop loss for {symbol} to {stop_loss_price}.")
            # Update stop loss for the stock
            update_stop_loss(symbol, stop_loss_price)

        # Check if the stock has reached a 20-25% gain
        elif overall_gain >= 20 and overall_gain <= 25:
            print(f"Selling {symbol} as it has reached a 20-25% gain.")
            print(f"Selling {holding['quantity']} quantities")

        # Wait for 8 weeks and then sell and overall_gain of 10%
        elif holding_age >= 40 and overall_gain >= 10:
            print(f"Selling {symbol} after 8 weeks with 10% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])
        
        # Wait for 16 weeks and then sell and overall_gain of 10%
        elif holding_age >= 80 and overall_gain >= 10:
            print(f"Selling {symbol} after 16 weeks with 10% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        # Wait for 32 weeks and then sell and overall_gain of 10%
        elif holding_age >= 160 and overall_gain >= 10:
            print(f"Selling {symbol} after 32 weeks with 10% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        # Wait for 32 weeks and then sell and overall_gain of 10%
        elif holding_age >= 200 and overall_gain >= 10:
            print(f"Selling {symbol} after 40 weeks with 10% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        elif holding_age >= 200 and overall_gain >= 5:
            print(f"Selling {symbol} after 40 weeks with 5% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        elif holding_age >= 160 and overall_gain >= 5:
            print(f"Selling {symbol} after 32 weeks with 5% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        elif holding_age >= 160 and overall_gain >= 2.5:
            print(f"Selling {symbol} after 16 weeks with 2.5% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        elif holding_age >= 160 and overall_gain >= 0:
            print(f"Selling {symbol} after 8 weeks with 5% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        elif holding_age >= 40 and overall_gain >= 5:
            print(f"Selling {symbol} after 8 weeks with 5% profit.")
            # Place sell order for the stock
            place_sell_order(symbol, holding['quantity'])

        else:
            print(f"Overall gain is {overall_gain}")

            
                # Place sell order for the stock
                # place_sell_order(symbol, holding['quantity'])
                # else:
                #     print("Not trading time. Monitoring will resume during trading hours.")
                #     # Wait for 5 minutes before checking again
                #     tm.sleep(300)

def update_stop_loss(symbol, stop_loss_price):
    """Function to update stop loss for a stock."""
    try:
        # Get instrument token for the symbol
        # instrument_token = get_instrument_token(symbol)
        # Place modify order to update stop loss
        kite.modify_order(
            variety="regular",
            order_id="your_order_id",  # Replace with actual order ID
            parent_order_id="your_parent_order_id",  # Replace with actual parent order ID
            tradingsymbol=symbol,
            exchange="NSE",
            transaction_type="SELL",
            quantity=1,
            order_type="SL-M",
            product="CNC",
            trigger_price=stop_loss_price
        )
        print(f"Stop loss updated for {symbol} to {stop_loss_price}.")
    except Exception as e:
        print(f"Error updating stop loss for {symbol}: {e}")

def place_sell_order(symbol, quantity):
    """Function to place a sell order for a stock."""
    try:
        # Get instrument token for the symbol
        # instrument_token = get_instrument_token(symbol)
        # Place sell order
        kite.place_order(
            tradingsymbol=symbol,
            exchange="NSE",
            transaction_type="SELL",
            quantity=quantity,  # Use the quantity obtained from holdings
            order_type="MARKET",
            product="CNC",
            variety="regular"
        )
        print(f"Sell order placed for {symbol}.")
    except Exception as e:
        print(f"Error placing sell order for {symbol}: {e}")

def is_trading_time():
    """Function to check if it's trading time."""
    now = datetime.now()
    trading_start_time = time(9, 15)  # Assuming trading starts at 9:15 AM
    trading_end_time = time(15, 30)   # Assuming trading ends at 3:30 PM
    return trading_start_time <= now.time() <= trading_end_time

# Example date range and interval for historical data
to_date = datetime.now().strftime('%Y-%m-%d')
from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
interval = "day"

# Main function
def main():
    holdings = get_holdings(symbols_to_monitor)
    monitor_holdings(holdings)

main()