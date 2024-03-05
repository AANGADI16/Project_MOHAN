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

# Function to convert UTC time to Indian Standard Time (IST)
def convert_to_ist(utc_time):
    utc_time = pytz.utc.localize(utc_time)  # Make sure the time is in UTC
    ist_time = utc_time.astimezone(pytz.timezone('Asia/Kolkata'))  # Convert to IST
    return ist_time

# Function to fetch historical data
def get_historical_data(symbol, from_date, to_date, interval):
    try:
        historical_data = kite.historical_data(instrument_token=symbol['instrument_token'],
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
        df = pd.DataFrame(historical_data)
    except:
        print('issue in fetching historical data from Kite')
    

    
    try:
        df.set_index('date', inplace=True)

    except:
        print('schema is not correct')
    return df

def get_historical_data_minute(symbol, from_date, to_date, interval):
    try:
        historical_data = kite.historical_data(instrument_token=symbol,
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
    except:
        print('issue in fetching historical data from Kite')
    

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
def place_buy_order(stock_symbol, quantity):
    response = kite.place_order(
        tradingsymbol=stock_symbol,
        exchange="NSE",
        transaction_type="BUY",
        quantity=quantity,
        order_type="MARKET",
        product="CNC",  # Cash and Carry (hold overnight)
        variety="amo"
    )
    print("Response from place_order:", response)
    # Access the 'order_id' key if the response is a dictionary
    if isinstance(response, dict):
        order_id = response.get('order_id')
        return order_id
    else:
        print("Response is not a dictionary")
        return None

# Function to place sell order for a stock with stop loss
def place_sell_order(stock_symbol, quantity):
    order_id = kite.place_order(
        tradingsymbol=stock_symbol,
        exchange="NSE",
        transaction_type="SELL",
        quantity=quantity,
        order_type="MARKET",
        product="CNC",
        # stoploss=str(stop_loss)  # Set stop loss
        variety="regular"
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

# Function to calculate ATR (Average True Range)
def calculate_atr(data, period=14):
    data['H-L'] = abs(data['high'] - data['low'])
    data['H-PC'] = abs(data['high'] - data['close'].shift(1))
    data['L-PC'] = abs(data['low'] - data['close'].shift(1))
    data['TR'] = data[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    data['ATR'] = data['TR'].rolling(period).mean()
    return data['ATR']


def calculate_supertrend(data, period=20, multiplier=2):
    # Calculate ATR
    data['TR'] = abs(data['high'] - data['low'])
    data['ATR'] = data['TR'].rolling(window=period).mean()
    
    # Calculate Upper Basic and Lower Basic
    data['Upper Basic'] = (data['high'] + data['low']) / 2 + multiplier * data['ATR']
    data['Lower Basic'] = (data['high'] + data['low']) / 2 - multiplier * data['ATR']
    
    # Initialize Upper Band and Lower Band
    data['Upper Band'] = data['Upper Basic']
    data['Lower Band'] = data['Lower Basic']
    
    # Calculate Upper Band and Lower Band
    for i in range(period, len(data)):
        data.loc[data.index[i], 'Upper Band'] = min(data['Upper Basic'].iloc[i], data['Upper Band'].iloc[i-1])
        data.loc[data.index[i], 'Lower Band'] = max(data['Lower Basic'].iloc[i], data['Lower Band'].iloc[i-1])
    
    # Calculate Trend
    data['Trend'] = None
    for i in data.index:
        print(pd.DataFrame(data))
        if data['close'].loc[i] > data['Upper Band'].loc[i]:
            data.loc[i, 'Trend'] = 'UP'
        elif data['close'].loc[i] < data['Lower Band'].loc[i]:
            data.loc[i, 'Trend'] = 'DOWN'
    
    return data


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

entry_price = {}  # Dictionary to store entry prices for each stock

bought_stocks = []

stocks_bought = []

bought_stocks_info = []

# Function to scan NSE equity stocks and identify stocks with green candle near 44-day MA
def scan_and_trade():
    print("Scanning and trading...")
    # Dictionary to store stocks that pass buy logic
    buy_stocks = {}
    # while True:
    # Get all NSE equity instruments
    instruments = kite.instruments("NSE")
    nse_equity_stocks = [instrument for instrument in instruments if instrument['segment'] == "NSE" and 
                            instrument['exchange'] == "NSE" and instrument['instrument_type'] == "EQ" and 
                            instrument['last_price'] < 1000 and instrument['tradingsymbol'][0].isalpha() and 
                            not instrument['name'] == ''
                            and 'ETF' not in instrument['tradingsymbol']
                            and 'VIVO-SM' not in instrument['tradingsymbol']
                             ]

    # Iterate through each stock
    # for stock in tqdm(nse_equity_stocks, desc="Scanning stocks", unit="stock"):
    for stock in nse_equity_stocks:
        # print(f"Scanning {stock['tradingsymbol']}...")
        # Fetch historical data for the last  90 days
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=90
                                                
                                                )).strftime('%Y-%m-%d')
        data = get_historical_data(stock, from_date, to_date, 'day')

        # Calculate 44-day moving average
        calculate_44_day_moving_average(data)

        # Calculate ATR
        data['ATR'] = calculate_atr(data) 

        # Calculate Supertrend
        calculate_supertrend(data, period=20, multiplier=2)

        print(f"supertrend value today: {data['Trend']}")

        # Check if the DataFrame has enough rows
        # print(data)
        if len(data) >= 2:

            # Check if the slope of 44-day moving average is increasing
            try:
                if is_ma_slope_increasing(data, window=5) and data['Trend'].iloc[-1] == 'UP':
                    # print(f"using bigger window to identify the slope of 44MA for stock {stock['tradingsymbol']}")
                    # Calculate ATR
                    atr = calculate_atr(data) 
                    # Monitor and exit trades based on ATR
                    
                    # try:
                    #     if stock in stop_loss_values:
                    #         monitor_and_exit_trade(stock, data, atr)
                    # except Exception as e:
                    #     print(f"Error occurred while processing {stock['tradingsymbol']}: {e}")


                # Check if the previous two days' candles are near the 44-day MA line
                    # try:
                    if len(data) >= 2:
                        # if (data['open'].iloc[-3] < data['close'].iloc[-3] ) and (data['open'].iloc[-2] < data['close'].iloc[-2] ) and (data['open'].iloc[-1] < data['close'].iloc[-1] ):
                        #data['low'].iloc[-1] <= data['44_day_mavg'].iloc[-1] or  TODO this condition is suppressed as more results are returned.
                            if ((data['open'].iloc[-1] <= data['44_day_mavg'].iloc[-1]) and (data['close'].iloc[-1] > data['44_day_mavg'].iloc[-1] )):
                                #to check volume spurt threshold =1 means 100% rise in volume
                                if detect_volume_spurt(data, threshold=1): 
                                    # Place buy order if not already bought
                                    # if stock not in stop_loss_values:
                                        buy_stocks[stock['tradingsymbol']] = (data['close'].iloc[-1] - data['open'].iloc[-1]) / data['open'].iloc[-1] * 100
                                        entry_price[stock['tradingsymbol']] = data['close'].iloc[-1] 
                                        # Set initial stop-loss to the lowest low of the previous two candles
                                        stop_loss_values[stock['tradingsymbol']] = min(data['low'].iloc[-1], data['low'].iloc[-2])
                                        stocks_bought.append(stock)
                                        quantity_to_buy = calculate_quantity(data['close'].iloc[-1]) # Determine quantity based on price
                                        bought_quantities[stock['tradingsymbol']] = quantity_to_buy  # Update bought quantity
                                        print(f"Initial Stop Loss set for symbol {stock['tradingsymbol']}: {stop_loss_values[stock['tradingsymbol']]}")
                    else:
                        print(f"Data for stock does not have enough rows to perform the comparison for stock : {stock['tradingsymbol']}")
                    # except Exception as e:
                    #     print(f"Error occurred while processing {stock['tradingsymbol']}: {e}")

            except:
                if is_ma_slope_increasing(data, window=2) and data['Trend'].iloc[-1] == 'UP' :
                    # print(f"using smaller window to identify the slope of 44MA for stock {stock['tradingsymbol']}")
                    # Calculate ATR
                    atr = calculate_atr(data) 
                    # Monitor and exit trades based on ATR
                    # if stock in stop_loss_values:
                    #     monitor_and_exit_trade(stock, data, atr) 
                    # try:
                    if len(data) >= 2:
                        # if (data['open'].iloc[-3] < data['close'].iloc[-3] ) and (data['open'].iloc[-2] < data['close'].iloc[-2] ) and (data['open'].iloc[-1] < data['close'].iloc[-1] ):
                        #data['low'].iloc[-1] <= data['44_day_mavg'].iloc[-1] or  TODO this condition is suppressed as more results are returned.
                            if ((data['open'].iloc[-1] <= data['44_day_mavg'].iloc[-1]) and (data['close'].iloc[-1] > data['44_day_mavg'].iloc[-1] )):
                                #to check volume spurt threshold =1 means 100% rise in volume
                                if detect_volume_spurt(data, threshold=1): 
                                    # Place buy order if not already bought
                                    # if stock not in stop_loss_values:
                                        buy_stocks[stock['tradingsymbol']] = (data['close'].iloc[-1] - data['open'].iloc[-1]) / data['open'].iloc[-1] * 100
                                        entry_price[stock['tradingsymbol']] = data['close'].iloc[-1] 
                                        # Set initial stop-loss to the lowest low of the previous two candles
                                        stop_loss_values[stock['tradingsymbol']] = min(data['low'].iloc[-1], data['low'].iloc[-2])
                                        stocks_bought.append(stock)
                                        quantity_to_buy = calculate_quantity(data['close'].iloc[-1]) # Determine quantity based on price
                                        bought_quantities[stock['tradingsymbol']] = quantity_to_buy  # Update bought quantity
                                        print(f"Initial Stop Loss set for symbol {stock['tradingsymbol']}: {stop_loss_values[stock['tradingsymbol']]}")
                    else:
                        print(f"Data for stock does not have enough rows to perform the comparison for stock : {stock['tradingsymbol']}")
                    # except Exception as e:
                        # print(f"Error occurred while processing {stock['tradingsymbol']}: {e}")
        else:
            print(f"Not enough data in DataFrame to perform calculations for stock : {stock['tradingsymbol']}")

    # Sort buy_stocks dictionary based on percentage day change
    sorted_buy_stocks = sorted(buy_stocks.items(), key=lambda x: x[1], reverse=True)
    print(sorted_buy_stocks)
    for stock in stocks_bought:
        print(stock['instrument_token'])
        print(stock['tradingsymbol'])

    # Place buy orders for top 10 stocks
    if len(sorted_buy_stocks) > 0 :
        for stock_info, _ in tqdm(sorted_buy_stocks[:10], desc="Placing buy orders", unit="order"):
            stock = stock_info  # Access the 'tradingsymbol' key from the stock_info dictionary
            print(f" Placing the buy order for {stock}")
            # place_buy_order(stock, quantity=bought_quantities[stock]) TODO error in extracting the value from the dictionary
            try:  # Check if the instrument is not in TR/BE category
                print(f"Placing the buy order for {stock}")
                place_buy_order(stock, quantity=1)
            except:
                print(f"Skipping {stock} as it is in TR/BE category")
            # Fetch latest data for the bought stock
            to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
            from_date = to_ist(datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            # data = get_historical_data_minute(stock, from_date, to_date, 'day')
            # Track the entry price
            # entry_price[stock] = data['open'].iloc[-1]  # Assuming open price as entry price
            # Update bought stocks list
            bought_stocks.append(stock)  # Add the bought stock to the list
            # Get the current date as the executed date
            executed_date = datetime.now().strftime('%Y-%m-%d')
            # Append the stock information to the list
            # Fetch latest data for the bought stock
            for item in stocks_bought:
                    if item['tradingsymbol'] == stock:
                        instrument_token = item['instrument_token']
                        # print(f"Found instrument token for {stock}: {instrument_token}")
                        break
                    else:
                        print(f"Could not find instrument token for {stock}")
                        continue
            try:
                to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
                from_date = to_ist(datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
                data_1 = get_historical_data_minute(instrument_token, from_date, to_date, 'day')
                entry_price_1 = data_1['open'].iloc[-1]  # Assuming open price as entry price


                bought_stocks_info.append({
                    'Stock': stock,
                    'Executed Date': executed_date,
                    'Entry Price': entry_price_1,
                    'Stop Loss': stop_loss_values.get(stock, 'N/A')  # Assuming stop_loss_values is a dictionary
                })

                # Write the collected information to a CSV file
                with open('bought_stocks_info.csv', 'w', newline='') as csvfile:
                    fieldnames = ['Stock', 'Executed Date', 'Entry Price', 'Stop Loss']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for stock_info in bought_stocks_info:
                        writer.writerow(stock_info)
            except:
                print('Error in csv writing block')
    else:
        print('No stocks to place orders as no stocks met the condition in scan_and_trade')


            
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

initial_buy_completed = False  # Flag to track if initial buy operation is completed

# Get current Indian Standard Time (IST)
current_ist_time = convert_to_ist(datetime.utcnow())
print("Current IST:", current_ist_time)

# Check if the current time is within trading hours (9:15 AM to 3:30 PM IST)
trading_start_time_to_buy = datetime.combine(datetime.now(), time(11, 15))
trading_end_time_to_buy = datetime.combine(datetime.now(), time(15, 30))
#TODO implement a logic where I can sell the stock between 9:15 to 15:30 and buy between 11:15 to 15:30
trading_start_time = datetime.combine(datetime.now(), time(11, 15))
trading_end_time = datetime.combine(datetime.now(), time(15, 30))

        # if current_ist_time.time() < trading_start_time.time() or current_ist_time.time() > trading_end_time.time():

while True:
    current_ist_time = convert_to_ist(datetime.utcnow())
    # Check if today is a trading day
    if datetime.now(ist).weekday() < 5:
        # if current_ist_time.time() >= trading_start_time.time() and current_ist_time.time() <= trading_end_time.time():
            # Place buy order once daily
            # if datetime.now(ist).time() >= datetime.time(hour=9, minute=15) and datetime.now(ist).time() <= datetime.time(hour=9, minute=30): TODO this condition can be depreciated as it narrows the buy order time by just 15 mins
            if len(bought_stocks) < 10:
                # Call scan_and_trade function only if stocks were sold previously
                if not initial_buy_completed or stocks_sold:
                    scan_and_trade()
                    initial_buy_completed = True  # Set flag to indicate initial buy operation completed

            else:
                # Monitor trades every 5 minutes
                for stock in stop_loss_values:
                    print(f"Monitoring stock: {stock}")

                    for item in stocks_bought:
                        if item['tradingsymbol'] == stock:
                            instrument_token = item['instrument_token']
                            # print(f"Found instrument token for {stock}: {instrument_token}")
                            break
                    else:
                        print(f"Could not find instrument token for {stock}")
                        continue
                    
                    # Fetch latest data for the stock
                    to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
                    from_date = to_ist(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    data = get_historical_data_minute(instrument_token, from_date, to_date, 'minute')

                    # # Print contents of stocks_bought and stop_loss_values
                    # print("stocks_bought:", stocks_bought)
                    # print("stop_loss_values:", stop_loss_values)


                    # Check if stop-loss is hit
                    if data['low'].iloc[-1] < stop_loss_values[stock]:
                        # Place sell order if stop-loss hit
                        place_sell_order(stock, quantity=1)
                        stocks_sold.append({

                        "Symbol": stock,
                        # "Quantity": bought_quantities[stock], #TODO bought quantites need to be updated with a logic
                        "Quantity": 1,
                        "Sell Price": data['low'].iloc[-1],
                        "Stop Loss": stop_loss_values[stock]
                        })
                        print(f"Stop Loss Hit for symbol {stock}. Sell order placed.")
                        del stop_loss_values[stock]  # Remove stop-loss for the symbol after selling
                        del bought_quantities[stock]  # Remove bought quantities
                        bought_stocks.remove(stock)
                        continue
                    print(stop_loss_values[stock])

                    # Check if the price reached 1:1 of stop-loss and update stop-loss accordingly
                    if data['close'].iloc[-1] >= stop_loss_values[stock] + (stop_loss_values[stock] - entry_price[stock]) * 0.5:
                        new_stop_loss = data['close'].iloc[-1] - (stop_loss_values[stock] - entry_price[stock])
                        if new_stop_loss > entry_price[stock]:
                            stop_loss_values[stock] = new_stop_loss
                            print(f"Stop Loss updated for symbol {stock}: {stop_loss_values[stock]}")
                        else:
                            print(f"New stop loss calculation for {stock} is less than entry price, stop loss not updated.")

                    # # Remove sold stocks from the bought_stocks list 
                    # if stock in bought_stocks:
                    #     bought_stocks.remove(stock)

                # Print profit/loss in tabular format
                if stocks_sold:
                    print(tabulate(stocks_sold, headers='keys', tablefmt='grid'))
                    save_results_to_csv(stocks_sold)
                sleep(300)  # 5 minutes in seconds
                
        # else:
        #     print(f"Outside trading hours, current time is {current_ist_time.time()}")
        #     sleep(900)
    else:
        print("Today is not a trading day.")
        sleep(86400)  # Sleep for 24 hours until next trading day