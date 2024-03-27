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
import logging
import schedule

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

# Function to place buy order with GT

# Function to fetch live market data
def get_live_market_data(symbol):
    try:
        market_data = kite.quote(symbol)
        return market_data
    except Exception as e:
        logging.error("Error fetching market data for {}: {}".format(symbol, str(e)))
        return None
    
def get_historical_data(symbol, from_date, to_date, interval):
    try:
        historical_data = kite.historical_data(instrument_token=symbol['instrument_token'],
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
        df = pd.DataFrame(historical_data)
        df.set_index('date', inplace=True)
        pd.DataFrame(df).to_csv('data.csv')
        return df
    except:
        return []

ist = pytz.timezone('Asia/Kolkata')  
def to_ist(time):
    return time.astimezone(ist)

scalping_df = pd.read_csv('ind_nifty500list.csv')
scalping_s = scalping_df['Symbol'].to_list()

def place_buy_order(stoploss ,price,target,symbol, quantity):
    # try:
        # Place regular buy order

        buy_order_id = kite.place_order(
            tradingsymbol=symbol,
            exchange=kite.EXCHANGE_NSE,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=quantity,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=price,
            product='CNC',
            variety="regular"
        )
        #Placing the sell order
        sleep(30)
        sell_order_id = kite.place_order(
        tradingsymbol=symbol,
        exchange="NSE",
        transaction_type="SELL",
        quantity=quantity,
        order_type="LIMIT",
        product="CNC",
        price=target,
        # stoploss=str(stop_loss)  # Set stop loss
        variety="regular"
    )
    #     #Placing the stoploss order
    #     stoploss_order_id = kite.place_order(
    #     tradingsymbol=symbol,
    #     exchange="NSE",
    #     transaction_type="SELL",
    #     quantity=quantity,
    #     order_type="LIMIT",
    #     product="MIS",
    #     price=stoploss*0.9,
    #     # stoploss=str(stop_loss)  # Set stop loss
    #     variety="regular"
    # )
        
        # Place GTT stoploss order
        stoploss_order_id = kite.place_gtt(tradingsymbol=symbol,
                                           exchange = 'NSE',
                                            trigger_type=kite.GTT_TYPE_SINGLE,
                                            last_price=price,
                                            trigger_values=[stoploss*0.998],
                                            orders=[{'transaction_type': 'SELL',
                                                     'quantity': quantity,
                                                     'price': (stoploss*0.998)-0.5,
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

        print(f"Buy, Stoploss and Sell order placed successfully")
        # print("Regular order ID:", regular_order_id)
        # print("Stoploss GTT order ID:", stoploss_order_id)
        # print("Target GTT order ID:", target_order_id)

def calculate_macd(data, short_window=12, long_window=26, signal_window=9):
    # Calculate short-term and long-term EMAs
    short_ema = data['close'].ewm(span=short_window, adjust=False).mean()
    long_ema = data['close'].ewm(span=long_window, adjust=False).mean()
    
    # Calculate MACD line
    macd_line = short_ema - long_ema
    
    # Calculate signal line
    signal_line = macd_line.ewm(span=signal_window, adjust=False).mean()
    
    # Calculate MACD histogram
    macd_histogram = macd_line - signal_line
    
    return macd_line, signal_line, macd_histogram

def check_bullish_crossover(macd_line, signal_line, prev_macd_line, prev_signal_line):
    bullish_crossover = (macd_line > signal_line) & (prev_macd_line <= prev_signal_line)
    pd.DataFrame(bullish_crossover).to_csv('macd.csv')
    return bullish_crossover

def calculate_rsi(data, window=14):
    # Calculate price changes
    delta = data['close'].diff()

    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Calculate average gain and average loss
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()

    # Calculate relative strength (RS)
    rs = avg_gain / avg_loss

    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))
    pd.DataFrame(rsi).to_csv('rsi.csv')
    
    return rsi

def calculate_pivot_points(data):
    high = data['high']
    low = data['low']
    close = data['close']
    
    # Calculate Pivot Point (PP)
    pp = (high + low + close) / 3
    
    # Calculate Support and Resistance Levels
    s1 = (2 * pp) - high
    s2 = pp - (high - low)
    r1 = (2 * pp) - low
    r2 = pp + (high - low)
    
    # Return calculated pivot points
    pivot_points = {
        'PP': pp,
        'S1': s1,
        'S2': s2,
        'R1': r1,
        'R2': r2
    }
    pd.DataFrame(pivot_points).to_csv('pivot_points.csv')
    return pivot_points


def calculate_44_day_moving_average(data):
    try:
        data['44_day_mavg'] = data['close'].rolling(window=50, min_periods=1).mean()
    except:
        print('schema not correct')

# Function to check if overall slope of 44-day MA is increasing
def is_ma_slope_increasing(data, window):
    try:
        # Calculate the difference between the current and previous moving averages
        ma_diff = data['44_day_mavg'].iloc[-5] - data['44_day_mavg'].iloc[-window]

        # Check if the moving average difference is positive
        return ma_diff < 0
    except IndexError:
        # Handle the case where there are not enough rows in the DataFrame
        print("Not enough data in DataFrame to calculate moving average slope")
        return False

bought_stocks_info = []

# Scalping strategy function
def scalping_strategy(symbols, quantity=1):
    scalping_df = pd.read_csv('ind_nifty500list.csv')
    
    scalping_s = scalping_df['Symbol'].to_list()
    instruments = kite.instruments("NSE")
    # instruments = nifty500
    nse_equity_stocks = [instrument for instrument in instruments if instrument['segment'] == "NSE" and 
                            instrument['exchange'] == "NSE" and instrument['instrument_type'] == "EQ" and 
                            instrument['last_price'] < 1000 and instrument['tradingsymbol'][0].isalpha() and 
                            not instrument['name'] == ''
                            and 'ETF' not in instrument['tradingsymbol']
                            and 'BEE' not in instrument['tradingsymbol']
                            and 'VIVO-SM' not in instrument['tradingsymbol']
                            and 'AHIMSA-ST' not in instrument['tradingsymbol']
                            # and 'TATACONSUM' in instrument['tradingsymbol']
                             ]
    
    for stock in nse_equity_stocks:
        # print(stock['tradingsymbol'])
        # print(f"nifty500 {nifty500}")
        if stock['tradingsymbol'] in scalping_s:
            print(f"scanning stock...{stock['tradingsymbol']}")
            # Fetch latest data for the stock
            to_date = to_ist(datetime.now()).strftime('%Y-%m-%d')
            from_date = to_ist(datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            data = get_historical_data(stock,from_date,to_date, '5minute')
            if len(data) >= 1:
                # Calculate MACD
                macd_line, signal_line, macd_hist = calculate_macd(data)
                # Keep track of previous MACD and signal line values
                prev_macd_line = macd_line.shift(1)
                prev_signal_line = signal_line.shift(1)
                # Check for bullish crossovers
                bullish_crossover = check_bullish_crossover(macd_line, signal_line, prev_macd_line, prev_signal_line)
                # Calculate RSI
                rsi = calculate_rsi(data)

                # Check if RSI is between 70 and 30
                rsi_threshold = (rsi >= 30) & (rsi <= 70)

                # #Calculate Supertrend
                # supertrend = calculate_supertrend(data)

                #calculating MA
                calculate_44_day_moving_average(data)

                ma_flag = is_ma_slope_increasing(data, 10)

                pp = calculate_pivot_points(data)

                if (data['open'].iloc[-1] < data['close'].iloc[-1]):
                    # if (2*(data['close'].iloc[-1]-data['open'].iloc[-1])<(data['open'].iloc[-1]-data['low'].iloc[-1])) or (2*(data['close'].iloc[-1]-data['open'].iloc[-1])<(data['high'].iloc[-1]-data['close'].iloc[-1])):
                    if (2*(data['close'].iloc[-1]-data['open'].iloc[-1])<(data['high'].iloc[-1]-data['close'].iloc[-1])):    
                        if(data['open'].iloc[-2] < data['close'].iloc[-1]):
                            if (bullish_crossover.iloc[-4] or bullish_crossover.iloc[-3] or bullish_crossover.iloc[-2] or bullish_crossover.iloc[-1])  and rsi.iloc[-1] <= 50 and ma_flag:
                                print('passed MACD, RSI and -ve slope MA condition')
                                if (data['close'].iloc[-1] > pp['PP'].iloc[-1]) and (data['close'].iloc[-1] < pp['R1'].iloc[-1]):
                                    print('passed pivot point condition')
                                    buy_price = data['close'].iloc[-1] + 0.1  # Add a buffer of 0.05 to the high price
                                    stoploss = data['low'].iloc[-1]
                                    target_price = buy_price + (buy_price - stoploss)*2

                                    print(f"buy price {buy_price}, stoploss = {stoploss}, target_price = {target_price}")

                                    place_buy_order(stoploss, buy_price, target_price,stock['tradingsymbol'], quantity)

                                    scalping_s.remove(stock['tradingsymbol'])

                                    bought_stocks_info.append({
                                        'STOCK': stock['tradingsymbol'],
                                        'EXECUTEDDATE': to_ist(datetime.now()).strftime('%Y-%m-%d'),
                                        'ENTRYPOINT': buy_price,
                                        'STOPLOSS': stoploss,  # Assuming stop_loss_values is a dictionary
                                        'QUANTITIES': 1 #TODO need to make it dynamic
                                    })

                                    # Write the collected information to a CSV file
                                    with open('Scalping_Intraday.csv', 'a', newline='') as csvfile:  # Use 'a' for append mode
                                        fieldnames = ['STOCK', 'EXECUTEDDATE', 'ENTRYPOINT', 'STOPLOSS','QUANTITIES']
                                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                                        # Check if the file is empty
                                        if csvfile.tell() == 0:
                                            writer.writeheader()  # Write header only if the file is empty

                                        # Append data to the file
                                        for stock_info in bought_stocks_info:
                                            writer.writerow(stock_info)

                    # elif data['open'].iloc[-2] > data['close'].iloc[-2] and data['close'].iloc[-1] > data['open'].iloc[-1] and ((data['open'].iloc[-2] - data['close'].iloc[-2]) < (data['close'].iloc[-1] - data['open'].iloc[-1]) ) and bullish_crossover.iloc[-1] and rsi.iloc[-1] <= 70:
                    #     print(f"placing buy order for intraday scalping for stock {stock['tradingsymbol']}")           # Calculate trigger price
                    #     buy_price = data['close'].iloc[-1] + 0.5  # Add a buffer of 0.05 to the high price
                    #     stoploss = data['low'].iloc[-2]
                    #     target_price = buy_price + (buy_price - (stoploss-1))*4

                    #     print(f"buy price {buy_price}, stoploss = {stoploss}, target_price = {target_price}")

                    #     place_buy_order(stoploss, buy_price, target_price,stock['tradingsymbol'], quantity)

                    #     scalping_s.remove(stock['tradingsymbol'])

                    #     bought_stocks_info.append({
                    #                 'STOCK': stock['tradingsymbol'],
                    #                 'EXECUTEDDATE': to_ist(datetime.now()).strftime('%Y-%m-%d'),
                    #                 'ENTRYPOINT': buy_price,
                    #                 'STOPLOSS': stoploss,  # Assuming stop_loss_values is a dictionary
                    #                 'QUANTITIES': 1 #TODO need to make it dynamic
                    #             })

                    #     # Write the collected information to a CSV file
                    #     with open('Scalping_Intraday.csv', 'a', newline='') as csvfile:  # Use 'a' for append mode
                    #         fieldnames = ['STOCK', 'EXECUTEDDATE', 'ENTRYPOINT', 'STOPLOSS','QUANTITIES']
                    #         writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    #         # Check if the file is empty
                    #         if csvfile.tell() == 0:
                    #             writer.writeheader()  # Write header only if the file is empty

                    #         # Append data to the file
                    #         for stock_info in bought_stocks_info:
                    #             writer.writerow(stock_info)
        # else:
        #         print(f"Not enough data in DataFrame to perform calculations for stock : {stock['tradingsymbol']}")

# Schedule the scalping strategy to run every 5 minutes
def run_scalping_strategy():
    symbols = scalping_s  # List of stocks to trade
    quantity = 1  # Quantity to trade for each stock
    scalping_strategy(symbols, quantity)

schedule.every(5).minutes.do(run_scalping_strategy)

# Function to convert UTC time to Indian Standard Time (IST)
def convert_to_ist(utc_time):
    utc_time = pytz.utc.localize(utc_time)  # Make sure the time is in UTC
    ist_time = utc_time.astimezone(pytz.timezone('Asia/Kolkata'))  # Convert to IST
    return ist_time

trading_start_time = datetime.combine(datetime.now(), time(9, 15))
trading_end_time = datetime.combine(datetime.now(), time(15, 30))

logging.basicConfig(level=logging.INFO)
while True:
    current_ist_time = convert_to_ist(datetime.utcnow())
    if datetime.now(ist).weekday() < 5:
        if current_ist_time.time() >= trading_start_time.time() and current_ist_time.time() <= trading_end_time.time():
            schedule.run_pending()
            # sleep(1)
        else:
            print(f"outside trading ours, current time is {current_ist_time.time()}")
            sleep(300)
            
    else:
        print(f"outside trading days, current day is {datetime.now(ist).weekday()}")
        sleep(300)
        