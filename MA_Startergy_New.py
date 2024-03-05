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
    request_token = e_msg.split('request_token=')[1].split(' ')[0].split('&action')[0]
    print('Successful Login with Request Token:{}'.format(request_token))

access_token = kite.generate_session(request_token,creds['api_secret'])['access_token']
kite.set_access_token(access_token)

# Function to convert UTC time to Indian Standard Time (IST)
def convert_to_ist(utc_time):
    utc_time = pytz.utc.localize(utc_time)  # Make sure the time is in UTC
    ist_time = utc_time.astimezone(pytz.timezone('Asia/Kolkata'))  # Convert to IST
    return ist_time

# Function to fetch historical data
def get_historical_data(symbol, from_date, to_date, interval):
    print("Fetching historical data for", symbol['tradingsymbol'])
    historical_data = kite.historical_data(instrument_token=symbol['instrument_token'],
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
    df = pd.DataFrame(historical_data)
    try:
        df.set_index('date', inplace=True)
    except:
        print('Schema is not correct')
    return df

# Function to calculate 44-day moving average
def calculate_44_day_moving_average(data):
    try:
        data['44_day_mavg'] = data['close'].rolling(window=44, min_periods=1).mean()
    except:
        print('Schema not correct')

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

# Function to place sell order for a stock with stop loss
def place_sell_order(symbol, quantity, stop_loss):
    order_id = kite.place_order(
        tradingsymbol=symbol['tradingsymbol'],
        exchange="NSE",
        transaction_type="SELL",
        quantity=quantity,
        order_type="MARKET",
        product="CNC",
        stoploss=str(stop_loss)  # Set stop loss
    )['order_id']
    return order_id

# Dictionary to store stop-loss values for each symbol
stop_loss_values = {}

# Function to identify volume spurts
def detect_volume_spurt(data, threshold):
    current_volume = data['volume'].iloc[-1]
    if current_volume > data['volume'].iloc[-2]:
        return True
    else:
        return False

# Function to check if overall slope of 44-day MA is increasing
def is_ma_slope_increasing(data, window):
    try:
        ma_diff = data['44_day_mavg'].iloc[-1] - data['44_day_mavg'].iloc[-window]
        return ma_diff > 0
    except IndexError:
        print("Not enough data in DataFrame to calculate moving average slope")
        return False

# Function to calculate Average True Range (ATR)
def calculate_atr(data, period=14):
    data['high_low'] = abs(data['high'] - data['low'])
    data['high_close'] = abs(data['high'] - data['close'].shift())
    data['low_close'] = abs(data['low'] - data['close'].shift())
    data['true_range'] = data[['high_low', 'high_close', 'low_close']].max(axis=1)
    atr = data['true_range'].rolling(window=period).mean().iloc[-1]
    return atr

# Function to check if candle crosses ATR
def check_cross_atr(data, atr):
    if data['Close'].iloc[-1] < (data['Close'].iloc[-2] - atr):
        return True
    return False

# Function to monitor and exit trades based on ATR
def monitor_and_exit_trade(symbol, data, atr):
    if check_cross_atr(data, atr):
        print(f"Candle crossed ATR for {symbol}. Exiting trade.")
        place_sell_order(symbol, quantity=1)
        del stop_loss_values[symbol]

#Function to calculate quantities
def calculate_quantity(price):
    if price < 100:
        return 1
    elif 100 <= price < 500:
        return 1
    elif 500 <= price < 1000:
        return 1
    elif 1000 <= price < 3000:
        return 1
    else:
        return 1  # Default quantity if price exceeds 3000

bought_quantities = {}
entry_price = {}  # Dictionary to store entry prices for each stock

# Function to scan NSE equity stocks and identify stocks with green candle near 44-day MA
def scan_and_trade():
    print("Scanning and trading...")
    buy_stocks = {}

    instruments = kite.instruments("NSE")
    nse_equity_stocks = [instrument for instrument in instruments if instrument['segment'] == "NSE" and 
                         instrument['exchange'] == "NSE" and instrument['instrument_type'] == "EQ" and 
                         instrument['last_price'] < 3000 and instrument['tradingsymbol'][0].isalpha() and 
                         not instrument['name'] == '' and 'ETF' not in instrument['tradingsymbol']]

    for stock in tqdm(nse_equity_stocks, desc="Scanning stocks", unit="stock"):
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=360)).strftime('%Y-%m-%d')
        data = get_historical_data(stock, from_date, to_date, 'day')
        calculate_44_day_moving_average(data)

        if len(data) >= 2:
            try:
                if is_ma_slope_increasing(data, window=5):
                    atr = calculate_atr(data) 
                    if stock in stop_loss_values:
                        monitor_and_exit_trade(stock, data, atr)
            except Exception as e:
                print(f"Error occurred while processing {stock['tradingsymbol']}: {e}")

            try:
                if len(data) >= 2 and ((data['open'].iloc[-1] <= data['44_day_mavg'].iloc[-1]) and (data['close'].iloc[-1] > data['44_day_mavg'].iloc[-1] )):
                    if detect_volume_spurt(data, threshold=1): 
                        buy_stocks[stock] = (data['Close'].iloc[-1] - data['Open'].iloc[-1]) / data['Open'].iloc[-1] * 100
                        stop_loss_values[stock] = min(data['low'].iloc[-1], data['low'].iloc[-2])
                        quantity_to_buy = calculate_quantity(data['Close'].iloc[-1]) 
                        bought_quantities[stock] = quantity_to_buy
            except Exception as e:
                print(f"Error occurred while processing {stock['tradingsymbol']}: {e}")

    sorted_buy_stocks = sorted(buy_stocks.items(), key=lambda x: x[1], reverse=True)

    for stock, _ in tqdm(sorted_buy_stocks[:10], desc="Placing buy orders", unit="order"):
        to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
        from_date = to_ist(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        data = get_historical_data(stock, from_date, to_date, 'minute')
        entry_price[stock] = data['open'].iloc[-1]  # Assuming open price as entry price

# Set timezone to Indian Standard Time (IST)
ist = pytz.timezone('Asia/Kolkata')

# Function to convert time to IST
def to_ist(time):
    return time.astimezone(ist)

from tabulate import tabulate

stocks_sold = []  # List to track stocks sold

def save_results_to_csv(results):
    csv_file_path = 'transaction_results.csv'

    if not os.path.exists(csv_file_path):
        with open(csv_file_path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=results[0].keys())
            writer.writeheader()

    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=results[0].keys())
        writer.writerows(results)

while True:
    scan_and_trade()