from kiteconnect import KiteConnect
import pandas as pd
import os
import pyotp
import datetime as dt
import json
import time
import requests

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


# # # List of symbols to monitor
# # symbols = [41729, 878593, 4774913,1769729,103425]  # Add more symbols as needed
# symbols = [3478273]

# # # Function to fetch historical data
# def get_historical_data(symbol, from_date, to_date, interval):
#     historical_data = kite.historical_data(instrument_token=symbol,
#                                            from_date=from_date,
#                                            to_date=to_date,
#                                            interval=interval)
#     df = pd.DataFrame(historical_data)
#     df.set_index('date', inplace=True)
#     return df

# # # Function to calculate 44-day moving average
# def calculate_44_day_moving_average(data):
#     data['44_day_mavg'] = data['close'].rolling(window=44, min_periods=1).mean()

# # Function to place buy order
# def place_buy_order(symbol, quantity):
#     kite.place_order(tradingsymbol='ACE', exchange="NSE", transaction_type="BUY", quantity=quantity, order_type="MARKET", product="CNC",variety="regular")

# # Function to place sell order
# def place_sell_order(symbol, quantity):
#     kite.place_order(tradingsymbol='ACE', exchange="NSE", transaction_type="SELL", quantity=quantity, order_type="MARKET", product="CNC",variety="regular")

# # Dictionary to store stop-loss values for each symbol
# stop_loss_values = {}

# import pytz

# def is_trading_day():
#     # Check if the current day is a trading day (Monday to Friday)

#     current_time = dt.datetime.now(pytz.timezone('Asia/Kolkata'))
#     return current_time.weekday() < 5

# def is_trading_hours():
#     # Check if the current time is within trading hours (9:29 AM to 3:30 PM)
#     current_time = dt.datetime.now(pytz.timezone('Asia/Kolkata'))
#     return dt.time(9, 29) <= current_time.time() <= dt.time(15, 30)

# def check_intersection_and_stop_loss(symbol):
#     while True:
#         if is_trading_day() and is_trading_hours():
#             # Fetch historical data for the last 2 days
#             to_date = dt.datetime.now().strftime('%Y-%m-%d')
#             from_date = (dt.datetime.now() - dt.timedelta(days=2)).strftime('%Y-%m-%d')
#             data = get_historical_data(symbol, from_date, to_date, 'minute')

#             # Calculate 44-day moving average
#             calculate_44_day_moving_average(data)

#             # Check if 44-day moving average is going up
#             if data['44_day_mavg'].iloc[-1] > data['44_day_mavg'].iloc[-2]:
#                 # Check for intersection every 5 minutes
#                 # TODO check if the below condition is required?
#                 # if data['close'].iloc[-1] > data['44_day_mavg'].iloc[-1] and data['close'].iloc[-2] < data['44_day_mavg'].iloc[-2]:
#                     # Place buy order if not already bought
#                     if symbol not in stop_loss_values:
#                         place_buy_order(symbol, quantity=1)
#                         stop_loss_values[symbol] = data['low'].iloc[-1]  # Set initial stop-loss
#                         print(f"Initial Stop Loss set for symbol {symbol}: {stop_loss_values[symbol]}")

#             # Update trailing stop loss if the current price is higher than the previous stop loss
#             if symbol in stop_loss_values and data['close'].iloc[-1] > stop_loss_values[symbol]:
#                 stop_loss_values[symbol] = data['close'].iloc[-1] * 0.98  # Update stop-loss to 2% below current price
#                 print(f'Trailing stoploss updated to new value : {stop_loss_values[symbol]}')
            
#             # Check for stop-loss hit every minute
#             if symbol in stop_loss_values and data['low'].iloc[-1] < stop_loss_values[symbol]:
#                 # Place sell order if stop-loss hit
#                 place_sell_order(symbol, quantity=1)
#                 print(f"Stop Loss Hit for symbol {symbol}. Sell order placed.")
#                 del stop_loss_values[symbol]  # Remove stop-loss for the symbol after selling
        
#         # Wait for 5 minutes before checking again
#         time.sleep(300)  # 5 minutes in seconds


# # Iterate through each symbol and monitor
# for symbol in symbols:
#     # Start monitoring for intersection and stop-loss
#     check_intersection_and_stop_loss(symbol)


from kiteconnect import KiteConnect
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import pytz

# Initialize Kite Connect client
api_key = "your_api_key"
access_token = "your_access_token"
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# Function to fetch historical data for a stock
def get_historical_data(symbol, from_date, to_date, interval):
    historical_data = kite.historical_data(instrument_token=symbol['instrument_token'],
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
    df = pd.DataFrame(historical_data)
    df.set_index('date', inplace=True)
    return df

# Function to calculate 44-day moving average
def calculate_44_day_moving_average(data):
    data['44_day_mavg'] = data['close'].rolling(window=44, min_periods=1).mean()

# Function to place buy order for a stock
def place_buy_order(symbol, quantity):
    order_id = kite.place_order(
        tradingsymbol=symbol['tradingsymbol'],
        exchange="NSE",
        transaction_type="BUY",
        quantity=quantity,
        order_type="MARKET",
        product="CNC"  # Cash and Carry (hold overnight)
    )['order_id']
    print(f"Buy order placed for {symbol['tradingsymbol']}: {order_id}")
    return order_id

# Function to place sell order for a stock
def place_sell_order(symbol, quantity):
    order_id = kite.place_order(
        tradingsymbol=symbol['tradingsymbol'],
        exchange="NSE",
        transaction_type="SELL",
        quantity=quantity,
        order_type="MARKET",
        product="CNC"
    )['order_id']
    print(f"Sell order placed for {symbol['tradingsymbol']}: {order_id}")
    return order_id

# Function to monitor bought stocks and manage stop-loss
def monitor_bought_stocks(symbol):
    while True:
        # Fetch historical data for the last 2 days
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        data = get_historical_data(symbol, from_date, to_date, 'minute')

        # Calculate 44-day moving average
        calculate_44_day_moving_average(data)

        # Update trailing stop loss if the current price is higher than the previous stop loss
        if symbol in stop_loss_values and data['close'].iloc[-1] > stop_loss_values[symbol]:
            stop_loss_values[symbol] = data['close'].iloc[-1] * 0.98  # Update stop-loss to 2% below current price
            print(f'Trailing stoploss updated to new value : {stop_loss_values[symbol]}')
        
        # Check for stop-loss hit every minute
        if symbol in stop_loss_values and data['low'].iloc[-1] < stop_loss_values[symbol]:
            # Place sell order if stop-loss hit
            place_sell_order(symbol, quantity=1)
            print(f"Stop Loss Hit for {symbol['tradingsymbol']}. Sell order placed.")
            del stop_loss_values[symbol]  # Remove stop-loss for the symbol after selling
        
        # Wait for 5 minutes before checking again
        time.sleep(300)  # 5 minutes in seconds

# Main function to scan NSE equity stocks, identify stocks with green candle near 44-day MA, and place buy orders
def scan_and_trade():
    # Get all NSE equity instruments
    instruments = kite.instruments("NSE")
    nse_equity_stocks = [instrument for instrument in instruments if instrument['segment'] == "NSE" and 
                         instrument['exchange'] == "NSE" and instrument['instrument_type'] == "EQ" and 
                         instrument['last_price'] < 3000 and not instrument['tradingsymbol'][0].isalpha() and 
                         not instrument['name'] == '']

    # Iterate through each stock
    for stock in nse_equity_stocks:
        print(f"Scanning {stock['tradingsymbol']}...")
        # Fetch historical data for the last 2 days
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        data = get_historical_data(stock, from_date, to_date, 'day')

        # Calculate 44-day moving average
        calculate_44_day_moving_average(data)

        # Check if the green candle is near the 44-day MA
        if data['close'].iloc[-1] > data['44_day_mavg'].iloc[-1]:
            # Place buy order
            order_id = place_buy_order(stock, quantity=1)
            print(f"Buy order placed for {stock['tradingsymbol']}: {order_id}")

            # Start monitoring for stop-loss and trailing stop-loss
            stop_loss_values[stock] = min(data['low'].iloc[-1], data['low'].iloc[-2])  # Set initial stop-loss
            monitor_bought_stocks(stock)
            
# Initialize stop-loss values dictionary
stop_loss_values = {}

# Execute the scan and trade function
scan_and_trade()