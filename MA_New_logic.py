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

# Function to convert UTC time to Indian Standard Time (IST)
def convert_to_ist(utc_time):
    utc_time = pytz.utc.localize(utc_time)  # Make sure the time is in UTC
    ist_time = utc_time.astimezone(pytz.timezone('Asia/Kolkata'))  # Convert to IST
    return ist_time

# Function to fetch historical data
def get_historical_data(symbol, from_date, to_date, interval):
    # try:
    historical_data = kite.historical_data(instrument_token=symbol['instrument_token'],
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
    # except:
        # print('issue in fetching historical data from Kite')
    

    df = pd.DataFrame(historical_data)
    try:
        df.set_index('date', inplace=True)

    except:
        print('schema is not correct')
    return df

# Function to calculate 44-day moving average
def calculate_44_day_moving_average(data):
    try:
        data['44_day_mavg'] = data['close'].rolling(window=44, min_periods=1).mean()
    except:
        print('schema not correct')

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

# # Dictionary to store stop-loss values for each symbol
stop_loss_values = {}

# Function to identify volume spurts
def detect_volume_spurt(data, threshold):
    # Calculate average volume for the last four days
    # average_volume = data['volume'].tail(4).mean()
    
    # Get the volume of the most recent day
    current_volume = data['volume'].iloc[-1]
    
    # Check if the current volume is greater than the average volume
    if current_volume > data['volume'].iloc[-2]:
        return True
    else:
        return False
    

# Function to check if overall slope of 44-day MA is increasing
def is_ma_slope_increasing(data, window):
    try:
        # Calculate the difference between the current and previous moving averages
        ma_diff = data['44_day_mavg'].iloc[-1] - data['44_day_mavg'].iloc[-window]

        # Check if the moving average difference is positive
        return ma_diff > 0
    except IndexError:
        # Handle the case where there are not enough rows in the DataFrame
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
        # Exit trade logic here
        print(f"Candle crossed ATR for {symbol}. Exiting trade.")
        # Place sell order
        place_sell_order(symbol, quantity=1)
        # Remove stop-loss value from dictionary
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
    # Dictionary to store stocks that pass buy logic
    buy_stocks = {}
    while True:
        # Get current Indian Standard Time (IST)
        current_ist_time = convert_to_ist(datetime.utcnow())
        print("Current IST:", current_ist_time)

        # Check if the current time is within trading hours (9:15 AM to 3:30 PM IST)
        trading_start_time = datetime.combine(datetime.now(), time(9, 15))
        trading_end_time = datetime.combine(datetime.now(), time(15, 30))

        # if current_ist_time.time() < trading_start_time.time() or current_ist_time.time() > trading_end_time.time():
        #     print("Not within trading hours.")
        #     # Sleep for 1 hour and check again
        #     sleep(3600)  # 1 hour in seconds
        #     continue

        # Get all NSE equity instruments
        instruments = kite.instruments("NSE")
        nse_equity_stocks = [instrument for instrument in instruments if instrument['segment'] == "NSE" and 
                             instrument['exchange'] == "NSE" and instrument['instrument_type'] == "EQ" and 
                             instrument['last_price'] < 3000 and instrument['tradingsymbol'][0].isalpha() and 
                             not instrument['name'] == ''
                             and 'ETF' not in instrument['tradingsymbol']]

        # Iterate through each stock
        for stock in nse_equity_stocks:
            # print(f"Scanning {stock['tradingsymbol']}...")
            # Fetch historical data for the last 2 days
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=360)).strftime('%Y-%m-%d')
            data = get_historical_data(stock, from_date, to_date, 'day')

            # Calculate 44-day moving average
            calculate_44_day_moving_average(data)

            # Check if the DataFrame has enough rows
            # print(data)
            if len(data) >= 2:

                # Check if the slope of 44-day moving average is increasing
                try:
                    if is_ma_slope_increasing(data, window=5):
                        # print('using bigger window to identify the slope of 44MA') 
                        # Calculate ATR
                        atr = calculate_atr(data) 
                        # Monitor and exit trades based on ATR
                        
                        try:
                            if stock in stop_loss_values:
                                monitor_and_exit_trade(stock, data, atr)
                        except:
                            pass
                            # print('no stocks available in the stock list')


                    # Check if the previous two days' candles are near the 44-day MA line
                    try:
                        if len(data) >= 2:
                            # if (data['open'].iloc[-3] < data['close'].iloc[-3] ) and (data['open'].iloc[-2] < data['close'].iloc[-2] ) and (data['open'].iloc[-1] < data['close'].iloc[-1] ):
                            #data['low'].iloc[-1] <= data['44_day_mavg'].iloc[-1] or  TODO this condition is suppressed as more results are returned.
                                if ((data['open'].iloc[-1] <= data['44_day_mavg'].iloc[-1]) and (data['close'].iloc[-1] > data['44_day_mavg'].iloc[-1] )):
                                    #to check volume spurt threshold =1 means 100% rise in volume
                                    if detect_volume_spurt(data, threshold=1): 
                                        # Place buy order if not already bought
                                        print(f"Placing the buy order for {stock}")
                                        if stock not in stop_loss_values:
                                            buy_stocks[stock] = (data['Close'].iloc[-1] - data['Open'].iloc[-1]) / data['Open'].iloc[-1] * 100
                                            # Set initial stop-loss to the lowest low of the previous two candles
                                            stop_loss_values[stock] = min(data['low'].iloc[-1], data['low'].iloc[-2])
                                            quantity_to_buy = calculate_quantity(data['Close'].iloc[-1]) # Determine quantity based on price
                                            bought_quantities[stock] = quantity_to_buy  # Update bought quantity
                                            print(f"Initial Stop Loss set for symbol {stock}: {stop_loss_values[stock]}")
                        else:
                            print(f"Data for stock does not have enough rows to perform the comparison for stock : {stock['tradingsymbol']}")
                    except:

                        print(f"Error in the for loop of the stock")

                except:
                    if is_ma_slope_increasing(data, window=2):
                        # print('Using smaller window to identify the slope of 44MA')
                        # Calculate ATR
                        atr = calculate_atr(data) 
                        # Monitor and exit trades based on ATR
                        if stock in stop_loss_values:
                            monitor_and_exit_trade(stock, data, atr) 
                        try:
                            if len(data) >= 2:
                                # if (data['open'].iloc[-3] < data['close'].iloc[-3] ) and (data['open'].iloc[-2] < data['close'].iloc[-2] ) and (data['open'].iloc[-1] < data['close'].iloc[-1] ):
                                #data['low'].iloc[-1] <= data['44_day_mavg'].iloc[-1] or  TODO this condition is suppressed as more results are returned.
                                    if ((data['open'].iloc[-1] <= data['44_day_mavg'].iloc[-1]) and (data['close'].iloc[-1] > data['44_day_mavg'].iloc[-1] )):
                                        #to check volume spurt threshold =1 means 100% rise in volume
                                        if detect_volume_spurt(data, threshold=1): 
                                            # Place buy order if not already bought
                                            print(f"Placing the buy order for {stock}")
                                            if stock not in stop_loss_values:
                                                buy_stocks[stock] = (data['Close'].iloc[-1] - data['Open'].iloc[-1]) / data['Open'].iloc[-1] * 100
                                                # Set initial stop-loss to the lowest low of the previous two candles
                                                stop_loss_values[stock] = min(data['low'].iloc[-1], data['low'].iloc[-2])
                                                quantity_to_buy = calculate_quantity(data['Close'].iloc[-1]) # Determine quantity based on price
                                                bought_quantities[stock] = quantity_to_buy  # Update bought quantity
                                                print(f"Initial Stop Loss set for symbol {stock}: {stop_loss_values[stock]}")
                            else:
                                print(f"Data for stock does not have enough rows to perform the comparison for stock : {stock['tradingsymbol']}")
                        except:

                            print(f"Error in the for loop of the stock")
            else:
                print(f"Not enough data in DataFrame to perform calculations for stock : {stock['tradingsymbol']}")

        # Sort buy_stocks dictionary based on percentage day change
        sorted_buy_stocks = sorted(buy_stocks.items(), key=lambda x: x[1], reverse=True)
    
        # Place buy orders for top 10 stocks
        for stock, _ in sorted_buy_stocks[:10]:
            print(stock)
            # place_buy_order(stock, quantity=bought_quantities[stock])

            # Fetch latest data for the bought stock
            to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
            from_date = to_ist(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            data = get_historical_data(stock, from_date, to_date, 'minute')
    
            # Track the entry price
            entry_price[stock] = data['open'].iloc[-1]  # Assuming open price as entry price
            
# # Set timezone to Indian Standard Time (IST)
ist = pytz.timezone('Asia/Kolkata')

# Function to convert time to IST
def to_ist(time):
    return time.astimezone(ist)
            

from tabulate import tabulate

# Initialize variables
stocks_sold = []  # List to track stocks sold

def save_results_to_csv(results):
    csv_file_path = 'transaction_results.csv'

    # Check if the CSV file exists, if not, create it and write the header
    if not os.path.exists(csv_file_path):
        with open(csv_file_path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=results[0].keys())
            writer.writeheader()

    # Append the new results to the CSV file
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=results[0].keys())
        writer.writerows(results)



while True:
    # Check if today is a trading day
    if datetime.now(ist).weekday() < 5:
        # Place buy order once daily
        if datetime.now(ist).time() >= datetime.time(hour=9, minute=15) and datetime.now(ist).time() <= datetime.time(hour=9, minute=30):
            # Call scan_and_trade function only if stocks were sold previously
            if stocks_sold:
                scan_and_trade()
                stocks_sold = []  # Reset the list
        else:
            # Monitor trades every 5 minutes
            for stock in stop_loss_values:
                # Fetch latest data for the stock
                to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
                from_date = to_ist(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                data = get_historical_data(stock, from_date, to_date, 'minute')

                # Check if stop-loss is hit
                if data['low'].iloc[-1] < stop_loss_values[stock]:
                    # Place sell order if stop-loss hit
                    place_sell_order(stock, quantity=bought_quantities[stock])
                    print(f"Stop Loss Hit for symbol {stock}. Sell order placed.")
                    del stop_loss_values[stock]  # Remove stop-loss for the symbol after selling
                    del bought_quantities[stock]  # Remove bought quantities
                    continue

                # Check if the price reached 1:1 of stop-loss and update stop-loss accordingly
                if data['close'].iloc[-1] >= stop_loss_values[stock] + (stop_loss_values[stock] - entry_price) * 0.5:
                    new_stop_loss = data['close'].iloc[-1] - (stop_loss_values[stock] - entry_price)
                    if new_stop_loss > entry_price:
                        stop_loss_values[stock] = new_stop_loss
                        print(f"Stop Loss updated for symbol {stock}: {stop_loss_values[stock]}")
                    else:
                        print(f"New stop loss calculation for {stock} is less than entry price, stop loss not updated.")

            # Print profit/loss in tabular format
            if stocks_sold:
                print(tabulate(stocks_sold, headers='keys', tablefmt='grid'))
                save_results_to_csv(stocks_sold)
            sleep(300)  # 5 minutes in seconds
    else:
        print("Today is not a trading day.")
        sleep(86400)  # Sleep for 24 hours until next trading day


        #TODO to remove below code

        # Monitor stop-loss for existing positions
        # while True:
        #     # Check if the current time is within trading hours (9:15 AM to 3:30 PM IST)
        #     # if current_ist_time.time() >= time(hour=9, minute=15) and current_ist_time.time() <= time(hour=15, minute=30):
        #         # Check for stop-loss hit for existing positions every 5 minutes
        #         for stock in stop_loss_values.keys():
        #             # Fetch latest data for the stock
        #             to_date = datetime.now().strftime('%Y-%m-%d')
        #             from_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        #             data = get_historical_data(stock, from_date, to_date, 'minute')
        #             # Check if stop-loss is hit
        #             if data['low'].iloc[-1] < stop_loss_values[stock]:
        #                 # Place sell order if stop-loss hit
        #                 place_sell_order(stock, quantity=1)
        #                 print(f"Stop Loss Hit for symbol {stock}. Sell order placed.")
        #                 del stop_loss_values[stock]  # Remove stop-loss for the symbol after selling
            # else:
                # print("Trading hours ended.")
                # break

            # Sleep for 5 minutes before checking again
            # sleep(300)  # 5 minutes in seconds
                

# Main loop to restart the trading process on the next trading day
# while True:
    # Run the trading process
# scan_and_trade()
    # Sleep until the next trading day
    # next_trading_day = datetime.now(pytz.timezone('Asia/Kolkata')) + datetime.timedelta(days=1)
    # next_trading_day = next_trading_day.replace(hour=9, minute=15, second=0, microsecond=0)
    # current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    # sleep((next_trading_day - current_time).total_seconds())




