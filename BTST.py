from kiteconnect import KiteConnect
import pandas as pd
import os
import pyotp
import datetime as dt
import json
import time
import requests
import pytz

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

# Function to get instruments for NSE equity with price less than 3000
def get_instruments():
    instruments = kite.instruments("NSE")
    nse_instruments = [instrument for instrument in instruments if instrument['segment'] == "NSE" and instrument['exchange'] == "NSE" and instrument['last_price'] < 3000 and not instrument['tradingsymbol'][0].isalpha() and not instrument['name'] == '']
    return nse_instruments

# Function to get historical data for a stock
def get_historical_data(symbol, from_date, to_date):
    return kite.historical_data(instrument_token=symbol['instrument_token'],
                                 from_date=from_date,
                                 to_date=to_date,
                                 interval="day")

# Function to calculate average volume
def calculate_average_volume(data):
    return sum(candle['volume'] for candle in data) / len(data)

# Function to check for volume surge
def is_volume_surge(data):
    average_volume = calculate_average_volume(data)
    return data[-1]['volume'] > 2 * average_volume

# Function to check if the stock closed near the high of the day
def is_close_near_high(data):
    return data[-1]['close'] >= 0.95 * data[-1]['high']

# Function to check for pre-market activity
def is_premarket_surge(data):
    # Add your pre-market data retrieval and analysis logic here
    return data[-1]['pre_open'] > data[-2]['close']

# Function to identify potential gap-up stocks based on various criteria
def identify_gap_up_stocks():
    gap_up_stocks = []
    today = dt.datetime.today().date()
    from_date = today - dt.timedelta(days=10)  # Fetch historical data for the past 10 days
    to_date = today - dt.timedelta(days=1)  # Exclude today's data to avoid lookahead bias

    for stock in get_instruments():
        data = get_historical_data(stock, from_date, to_date)
        if not data:
            continue
        
        if is_volume_surge(data) and is_close_near_high(data):
            # Add more criteria here (e.g., pre-market activity, relative strength, technical indicators)
            # For example:
            # if is_premarket_surge(data):
            #     gap_up_stocks.append(stock['tradingsymbol'])
            gap_up_stocks.append(stock)

    return gap_up_stocks

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
    return order_id

# Function to place sell order for a stock with stop loss and trailing stop loss
def place_sell_order(symbol, quantity, stop_loss):
    try:
        # Get previous day close price for stop loss calculation
        from_date = datetime.now().date() - timedelta(days=1)
        to_date = datetime.now().date() - timedelta(days=1)
        data = get_historical_data(symbol, from_date, to_date)
        if data:
            previous_close = data[-1]['close']
            stop_loss_price = previous_close * 0.98  # 2% stop loss
            trailing_stop_loss_price = previous_close * 0.02  # 2% trailing stop loss
            order_id = kite.place_order(
                tradingsymbol=symbol['tradingsymbol'],
                exchange="NSE",
                transaction_type="SELL",
                quantity=quantity,
                order_type="MARKET",
                product="CNC",
                stoploss=str(stop_loss_price),  # Set stop loss
                trailing_stoploss=str(trailing_stop_loss_price)  # Set trailing stop loss
            )['order_id']
            return order_id
        else:
            print(f"Error: No historical data found for {symbol['tradingsymbol']}")
            return None
    except Exception as e:
        print(f"Error placing sell order for {symbol['tradingsymbol']}: {str(e)}")
        return None

# # Function to execute the strategy
# def execute_strategy():
#     # Get potential gap-up stocks at 3:15 PM IST
#     gap_up_stocks = identify_gap_up_stocks()

#     # Calculate stop loss (2% of previous day close)
#     stop_loss_percentage = 0.02
#     previous_day_close = None
#     if gap_up_stocks:  # If there are potential gap-up stocks
#         today = dt.datetime.now().date()
#         from_date = today - dt.timedelta(days=2)  # Fetch historical data for the past 2 days
#         to_date = today - dt.timedelta(days=1)  # Exclude today's data to avoid lookahead bias
#         for stock in gap_up_stocks:
#             data = get_historical_data(stock, from_date, to_date)
#             if data:
#                 previous_day_close = data[-1]['close']
#                 break  # Stop after finding the first valid previous day close
#     print(gap_up_stocks)

#     if previous_day_close is not None:
#         stop_loss = previous_day_close * stop_loss_percentage

#         # Place buy orders for potential gap-up stocks
#         for stock in gap_up_stocks:
#             # Place buy order
#             order_id = place_buy_order(stock, 1)  # Place buy order for 1 share
#             print(f"Buy order placed for {stock['tradingsymbol']}: {order_id}")

#         # Wait for the next trading day (9:30 AM IST) to execute sell orders with stop loss
#         current_time = dt.datetime.now(pytz.timezone('Asia/Kolkata'))
#         next_trading_day = current_time + dt.timedelta(days=1)
#         next_trading_day_9_30 = next_trading_day.replace(hour=9, minute=30, second=0, microsecond=0)

#         while dt.datetime.now(pytz.timezone('Asia/Kolkata')) < next_trading_day_9_30:
#             time.sleep(60)  # Sleep for 1 minute

#         # Execute sell orders with stop loss
#         for stock in gap_up_stocks:
#             # Place sell order with stop loss
#             order_id = place_sell_order(stock, 1, stop_loss)
#             print(f"Sell order placed for {stock['tradingsymbol']} with stop loss: {order_id}")
#     else:
#         print("No potential gap-up stocks found or unable to fetch historical data.")

# # Execute the strategy
# execute_strategy()


def is_trading_day(date):
    # Check if the day is a weekday (0: Monday, 1: Tuesday, ..., 4: Friday)
    return date.weekday() < 5

def execute_strategy():
    while True:
        # Get current time
        current_time = dt.datetime.now(pytz.timezone('Asia/Kolkata'))
        
        # Check if it's a trading day and between 9:29 AM and 3:30 PM IST
        if is_trading_day(current_time) and current_time.time() >= dt.time(9, 29) and current_time.time() <= dt.time(15, 30):
            # Execute the strategy
            # Get potential gap-up stocks at 3:15 PM IST
            gap_up_stocks = identify_gap_up_stocks()

            # Calculate stop loss (2% of previous day close)
            stop_loss_percentage = 0.02
            previous_day_close = None
            if gap_up_stocks:  # If there are potential gap-up stocks
                today = dt.datetime.now().date()
                from_date = today - dt.timedelta(days=2)  # Fetch historical data for the past 2 days
                to_date = today - dt.timedelta(days=1)  # Exclude today's data to avoid lookahead bias
                for stock in gap_up_stocks:
                    data = get_historical_data(stock, from_date, to_date)
                    if data:
                        previous_day_close = data[-1]['close']
                        break  # Stop after finding the first valid previous day close

            if previous_day_close is not None:
                stop_loss = previous_day_close * stop_loss_percentage

                # Place buy orders for potential gap-up stocks
                for stock in gap_up_stocks:
                    # Place buy order
                    order_id = place_buy_order(stock, 1)  # Place buy order for 1 share
                    print(f"Buy order placed for {stock['tradingsymbol']}: {order_id}")

                # Wait for the next trading day (9:30 AM IST) to execute sell orders with stop loss
                current_time = dt.datetime.now(pytz.timezone('Asia/Kolkata'))
                next_trading_day = current_time + dt.timedelta(days=1)
                next_trading_day_9_30 = next_trading_day.replace(hour=9, minute=30, second=0, microsecond=0)

                while dt.datetime.now(pytz.timezone('Asia/Kolkata')) < next_trading_day_9_30:
                    time.sleep(60)  # Sleep for 1 minute

                # Execute sell orders with stop loss
                for stock in gap_up_stocks:
                    # Place sell order with stop loss
                    order_id = place_sell_order(stock, 1, stop_loss)
                    print(f"Sell order placed for {stock['tradingsymbol']} with stop loss: {order_id}")
            else:
                print("No potential gap-up stocks found or unable to fetch historical data.")

            # Sleep for 1 minute before checking again
            time.sleep(60)
        else:
            # If it's not a trading day or outside trading hours, sleep until the next trading day
            next_trading_day = current_time
            if not is_trading_day(next_trading_day):
                # If it's a weekend, move to the next Monday
                while not is_trading_day(next_trading_day):
                    next_trading_day += dt.timedelta(days=1)
                next_trading_day = next_trading_day.replace(hour=9, minute=29, second=0, microsecond=0)
            else:
                # If it's after market hours, move to the next trading day
                if current_time.time() > dt.time(15, 30):
                    next_trading_day += dt.timedelta(days=1)
                    next_trading_day = next_trading_day.replace(hour=9, minute=29, second=0, microsecond=0)

            # Calculate the time difference until the next trading day
            time_difference = next_trading_day - current_time

            # Sleep until the next trading day
            time.sleep(time_difference.total_seconds())

# Execute the strategy
execute_strategy()
