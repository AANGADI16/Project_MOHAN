from kiteconnect import KiteConnect
import pandas as pd
import os
import pyotp
from datetime import datetime, time, timedelta, timezone
import json
import requests
import pytz
from time import sleep
import csv
from tqdm import tqdm  # Import tqdm for progress bars
from Exit_Stratergy import exit_stratergy

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
        df.set_index('date', inplace=True)
        return df
    except:
        return []
        print('issue in fetching historical data from Kite')
    
    

def get_historical_data_minute(symbol, from_date, to_date, interval):
    # try:
        historical_data = kite.historical_data(instrument_token=symbol,
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
        df = pd.DataFrame(historical_data)
        return df
    # except:
    #     return []
    #     print('issue in fetching historical data from Kite')
    

# Function to calculate 44-day moving average
def calculate_44_day_moving_average(data):
    try:
        data['44_day_mavg'] = data['close'].rolling(window=44, min_periods=1).mean()
    except:
        print('schema not correct')

# Function to place buy order for a stock
def place_buy_order(stoploss_price ,price,stock_symbol, quantity):
    response = kite.place_order(
        tradingsymbol=stock_symbol,
        exchange="NSE",
        transaction_type="BUY",
        quantity=quantity,
        price=price,
        order_type="LIMIT",
        product="CNC",  # Cash and Carry (hold overnight)
        variety="regular",
        trigger_price=stoploss_price # Specify stoploss price
        # validity="GTT"  # Validity of the order (DAY, IOC, GTT)
    )
    print("Response from place_order:", response)
    # Access the 'order_id' key if the response is a dictionary
    if isinstance(response, dict):
        order_id = response.get('order_id')
        return order_id
    else:
        print("Response is not a dictionary")
        return None
    
def place_buy_order_test(stoploss ,price,target,symbol, quantity):
    # try:
        # Place regular buy order

        regular_order_id = kite.place_order(
            tradingsymbol=symbol,
            exchange=kite.EXCHANGE_NSE,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=quantity,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=price,
            product='CNC',
            variety="regular"
        )
        
        # Place GTT stoploss order
        stoploss_order_id = kite.place_gtt(tradingsymbol=symbol,
                                           exchange = 'NSE',
                                            trigger_type=kite.GTT_TYPE_SINGLE,
                                            last_price=price,
                                            trigger_values=[stoploss],
                                            orders=[{'transaction_type': 'SELL',
                                                     'quantity': quantity,
                                                     'price': stoploss-1,
                                                     'order_type': 'LIMIT',
                                                     'product': 'CNC'}])
        
        # Place GTT target order
        target_order_id = kite.place_gtt(tradingsymbol=symbol,
                                        trigger_type=kite.GTT_TYPE_SINGLE,
                                          exchange = 'NSE',
                                          last_price=price,
                                          trigger_values=[target],
                                          orders=[{'transaction_type': 'SELL',
                                                   'quantity': quantity,
                                                   'price': target+1,
                                                   'order_type':'LIMIT',
                                                   'product': 'CNC'}])

        print("Buy order placed successfully")
        print("Regular order ID:", regular_order_id)
        print("Stoploss GTT order ID:", stoploss_order_id)
        print("Target GTT order ID:", target_order_id)
    
    # except Exception as e:
    #     print("Error placing order:", e)
    
def modify_stoploss(order_id, stoploss_price):
    """
    Function to modify the stoploss of an existing order.
    """
    response = kite.modify_order(
        order_id=order_id,
        trigger_price=stoploss_price,
        variety="regular"
        # validity = 'GTT'
    )
    return response

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
    )
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
    try:
        data['H-L'] = abs(data['high'] - data['low'])
        data['H-PC'] = abs(data['high'] - data['close'].shift(1))
        data['L-PC'] = abs(data['low'] - data['close'].shift(1))
        data['TR'] = data[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        data['ATR'] = data['TR'].rolling(period).mean()
        return data['ATR']
    except Exception as e:
        print("An error occurred:", e)
    


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
    

file_path_stocks_bought = 'bought_stocks_info.csv' #TODO replace with actual file name
bought_stocks_df = pd.read_csv(file_path_stocks_bought)

instruments = 'instruments.csv'
instruments_df = pd.read_csv(instruments)




entry_price = {}  # Dictionary to store entry prices for each stock

bought_stocks = bought_stocks_df['STOCK'].to_list()

stocks_bought = []

bought_stocks_info = []

order_ids = {}

nifty500_df = pd.read_csv('ind_nifty500list.csv')
nifty500 = nifty500_df['Symbol'].to_list()

# Function to scan NSE equity stocks and identify stocks with green candle near 44-day MA
def scan_and_trade():
    print("Scanning and trading...")
    # Dictionary to store stocks that pass buy logic
    buy_stocks = {}
    # while True:
    # Get all NSE equity instruments
    instruments = kite.instruments("NSE")
    # instruments = nifty500
    nse_equity_stocks = [instrument for instrument in instruments if instrument['segment'] == "NSE" and 
                            instrument['exchange'] == "NSE" and instrument['instrument_type'] == "EQ" and 
                            instrument['last_price'] < 1000 and instrument['tradingsymbol'][0].isalpha() and 
                            not instrument['name'] == ''
                            and 'ETF' not in instrument['tradingsymbol']
                            and 'VIVO-SM' not in instrument['tradingsymbol']
                            and 'AHIMSA-ST' not in instrument['tradingsymbol']
                            # and 'AUTOIND' in instrument['tradingsymbol']
                             ]
    
    # nse_equity_stocks = nifty500

    # Iterate through each stock
    # for stock in tqdm(nse_equity_stocks, desc="Scanning stocks", unit="stock"):
    a=0
    for stock in nse_equity_stocks:
        # print(stock['tradingsymbol'])
        # print(f"nifty500 {nifty500}")
        if stock['tradingsymbol'] in nifty500:
            b=a+1
            a=a+1
            print(f"{b} Scanning {stock['tradingsymbol']}...")
            # Fetch historical data for the last  90 days
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            data = get_historical_data(stock, from_date, to_date, 'day')

            if len(data) >= 0:

                # Calculate 44-day moving average
                calculate_44_day_moving_average(data)

                # Calculate ATR
                data['ATR'] = calculate_atr(data) 

                # Calculate Supertrend
                calculate_supertrend(data, period=20, multiplier=2)

                # print(f"supertrend value today: {data['Trend']}")

                # Check if the DataFrame has enough rows
                # print(data)
                if len(data) >= 2:

                    # Check if the slope of 44-day moving average is increasing
                    try:
                        if is_ma_slope_increasing(data, window=30) and data['Trend'].iloc[-1] == 'UP':
                            # print(f"using bigger window to identify the slope of 44MA for stock {stock['tradingsymbol']}")
                            # Calculate ATR
                            atr = calculate_atr(data)


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
                                                stop_loss_values[stock['tradingsymbol']] = min(data['low'].iloc[-1],data['low'].iloc[-2], data['low'].iloc[-3])
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
                                                stop_loss_values[stock['tradingsymbol']] = min(data['low'].iloc[-1], data['low'].iloc[-2], data['low'].iloc[-3])
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
        else:
                # print(f"Not in the provided list of scanning stock : {stock['tradingsymbol']}")
            pass
    

    # Sort buy_stocks dictionary based on percentage day change
    sorted_buy_stocks = sorted(buy_stocks.items(), key=lambda x: x[1], reverse=False) #14Mar: changed the sorting to ascending


    # Place buy orders for top 10 stocks
    if len(sorted_buy_stocks) > 0 :
        for stock_info, _ in tqdm(sorted_buy_stocks[:10], desc="Placing buy orders", unit="order"):
            stock = stock_info  # Access the 'tradingsymbol' key from the stock_info dictionary
            print(f" Placing the buy order for {stock}")
            # place_buy_order(stock, quantity=bought_quantities[stock]) TODO error in extracting the value from the dictionary
            # try:  # Check if the instrument is not in TR/BE category
            print(f"Placing the buy order for {stock} with entry price{entry_price.get(stock)} with stoploss price {stop_loss_values.get(stock, 0)}")
            stoploss_price = stop_loss_values.get(stock, 0)
            buy_price = entry_price.get(stock)
            target = buy_price+(buy_price-stoploss_price) * 3 #TODO risk to reward ratio is 1:3
            # order_ids[stock] = place_buy_order(stoploss_price,buy_price,stock, quantity=1)
            place_buy_order_test(stoploss_price,buy_price,target,stock, quantity=1)
            bought_stocks.append(stock)
            executed_date = datetime.now().strftime('%Y-%m-%d')
            # except:
            # print(f"Skipping {stock} as it is in TR/BE category")
            # Fetch latest data for the bought stock
            to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
            from_date = to_ist(datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            # TODO work on below for loop it is causing error Fetch latest data for the bought stock
            for item in stocks_bought:
                    if item['tradingsymbol'] == stock:
                        instrument_token = stocks_bought[0]['instrument_token']
                        # instrument_token = instruments_df['instrument_token'](instruments_df['tradingsymbol'] == stock)
                        

                        # print(f"Found instrument token for {stock}: {instrument_token}")
                        break
                    else:
                        print(f"Could not find instrument token for {stock}")
                        continue
            # try:
            to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
            from_date = to_ist(datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            data_1 = get_historical_data_minute(instrument_token, from_date, to_date, 'day')
            entry_price_1 = data_1['open'].iloc[-1]  # Assuming open price as entry price


            bought_stocks_info.append({
                'STOCK': stock,
                'EXECUTEDDATE': executed_date,
                'ENTRYPOINT': entry_price_1,
                'STOPLOSS': stop_loss_values.get(stock, 0),  # Assuming stop_loss_values is a dictionary
                'QUANTITIES': 1 #TODO need to make it dynamic
            })

            # Write the collected information to a CSV file
            with open('bought_stocks_info.csv', 'a', newline='') as csvfile:  # Use 'a' for append mode
                fieldnames = ['STOCK', 'EXECUTEDDATE', 'ENTRYPOINT', 'STOPLOSS','QUANTITIES']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Check if the file is empty
                if csvfile.tell() == 0:
                    writer.writeheader()  # Write header only if the file is empty

                # Append data to the file
                for stock_info in bought_stocks_info:
                    writer.writerow(stock_info)
            # except:
            #     print('Error in csv writing block')
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
trading_start_time = datetime.combine(datetime.now(), time(9, 15))
trading_end_time = datetime.combine(datetime.now(), time(15, 30))

        # if current_ist_time.time() < trading_start_time.time() or current_ist_time.time() > trading_end_time.time():

while True:
    current_ist_time = convert_to_ist(datetime.utcnow())
    # Check if today is a trading day
    if datetime.now(ist).weekday() < 5:
        if current_ist_time.time() >= trading_start_time.time() and current_ist_time.time() <= trading_end_time.time():
            # Place buy order once daily
            # if datetime.now(ist).time() >= datetime.time(hour=9, minute=15) and datetime.now(ist).time() <= datetime.time(hour=9, minute=30): TODO this condition can be depreciated as it narrows the buy order time by just 15 mins
            if len(bought_stocks) < 100:
                # Call scan_and_trade function only if stocks were sold previously
                print(f"previously bought stocks are: {bought_stocks}")
                if not initial_buy_completed or stocks_sold:
                    scan_and_trade()
                    initial_buy_completed = True  # Set flag to indicate initial buy operation completed

            else:
                # 12Mar: below three lines are used to take the stockfrom the refreshed list of csv saved.
                file_path_stocks_bought = 'bought_stocks_info.csv' #TODO replace with actual file name
                bought_stocks_df = pd.read_csv(file_path_stocks_bought)
                bought_stocks = bought_stocks_df['STOCK'].to_list()
                # Monitor trades every 5 minutes
                for stock in bought_stocks:
                    entry_price = bought_stocks_df[bought_stocks_df['STOCK'] == stock]['ENTRYPOINT'].iloc[0] # 12Mar: to bring in the stoploss directly from the saved excel for already placed orders                    
                    stop_loss_values = bought_stocks_df[bought_stocks_df['STOCK'] == stock]['STOPLOSS'].iloc[0] # 12Mar: to bring in the stoploss directly from the saved excel for already placed orders
                    print(f"Monitoring stock: {stock}")

                    # for item in stocks_bought: #12Mar: Previous condition was for item in stocks_bought:
                    #     # if item['tradingsymbol'] == stock: #12Mar: commented this condition as it is not relavant
                    #         instrument_token = instruments_df[instruments_df['tradingsymbol'] == stock]['instrument_token']
                    #         # print(f"Found instrument token for {stock}: {instrument_token}")
                    #         break
                    # else:
                    #     print(f"Could not find instrument token for {stock}")
                    #     continue

                    instrument_token = instruments_df[instruments_df['tradingsymbol'] == stock]['instrument_token']
            
                    # Fetch latest data for the stock
                    to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
                    from_date = to_ist(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

                    for value in instrument_token.astype(str).values:
                        
                        data = get_historical_data_minute(str(value), from_date, to_date, 'minute')
        

                    # # Print contents of stocks_bought and stop_loss_values
                    # print("stocks_bought:", stocks_bought)
                    print(f"stop_loss_values{stock}: {stop_loss_values}")
                    print(f"entry price: {entry_price}")

                    # if len(data) >= 2:
                        # Check if stop-loss is hit
                    if data['low'].iloc[-1] < stop_loss_values:
                        # Place sell order if stop-loss hit
                        place_sell_order(stock, quantity=bought_stocks_df[bought_stocks_df['STOCK']== stock]['QUANTITIES'].iloc[0])
                        stocks_sold.append({
                        "Symbol": stock,
                        # "Quantity": bought_quantities[stock], #TODO bought quantites need to be updated with a logic
                        "Quantity": bought_stocks_df[bought_stocks_df['STOCK']== stock]['QUANTITIES'].iloc[0],
                        "Sell Price": data['low'].iloc[-1],
                        "Stop Loss": stop_loss_values
                        })
                        print(f"Stop Loss Hit for symbol {stock}. Sell order placed.")
                        del stop_loss_values  # Remove stop-loss for the symbol after selling
                        del bought_quantities  # Remove bought quantities
                        bought_stocks.remove(stock)
                        continue

                    

                    # Check if the price reached 1:1 of stop-loss and update stop-loss accordingly
                    elif data['close'].iloc[-1] >= entry_price + (entry_price - stop_loss_values):
                        new_stop_loss = data['close'].iloc[-1] - (entry_price - stop_loss_values)
                        sleep(20)
                        if new_stop_loss > entry_price:
                            stop_loss_values = new_stop_loss
                            order_id = order_ids.get(stock)
                            # modify_stoploss(order_id,stop_loss_values)
                            print(f"Stop Loss updated for symbol {stock} (Order ID: {order_id}): {stop_loss_values}")
                        else:
                            print(f"New stop loss calculation for {stock} is less than entry price, stop loss not updated.")
                    else:
                        msg = exit_stratergy(stock, kite)
                        if msg:
                            bought_stocks.remove(stock)
                            print(f"sold stock using exit stratergy{stock}")
                        else:
                            print(f"Stocks were not sold")

                        continue

                    # # Print profit/loss in tabular format
                    # if stocks_sold:
                    #     print(tabulate(stocks_sold, headers='keys', tablefmt='grid'))
                    #     save_results_to_csv(stocks_sold)
                sleep(600)  # 5 minutes in seconds
            sleep(600)  # 5 minutes in seconds
                    

                
        else:
            print(f"Outside trading hours, current time is {current_ist_time.time()}")
            sleep(900)
    else:
        print("Today is not a trading day.")
        sleep(86400)  # Sleep for 24 hours until next trading day