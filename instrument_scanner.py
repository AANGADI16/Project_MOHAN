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


# Function to fetch all instruments for NSE and equity with price less than 3000
def get_instruments():
    instruments = kite.instruments("NSE")
    nse_instruments = [instrument for instrument in instruments if instrument['segment'] == "NSE" and instrument['exchange'] == "NSE" and instrument['last_price'] < 3000 and not instrument['tradingsymbol'][0].isalpha() and not instrument['name'] == '']
    return nse_instruments

# # Function to fetch historical data
# def get_historical_data(symbol, from_date, to_date, interval):
#     historical_data = kite.historical_data(instrument_token=symbol['instrument_token'],
#                                            from_date=from_date,
#                                            to_date=to_date,
#                                            interval=interval)
#     df = pd.DataFrame(historical_data)
#     df.set_index('date', inplace=True)
#     return df

# # Function to calculate 44-day moving average
# def calculate_44_day_moving_average(data):
#     data['44_day_mavg'] = data['close'].rolling(window=44, min_periods=1).mean()

# # Function to find symbols where green candle is close to 44-day MA
# def find_symbols_close_to_ma():
#     result = []
#     instruments = get_instruments()
#     for instrument in instruments:
#         # Fetch historical data for the last 45 days
#         # print(instrument)
#         to_date = dt.datetime.now().strftime('%Y-%m-%d')
#         from_date = (dt.datetime.now() - dt.timedelta(days=180)).strftime('%Y-%m-%d')
#         data = get_historical_data(instrument, from_date, to_date, 'day')
        
#         # Calculate 44-day moving average
#         calculate_44_day_moving_average(data)
        
#         # Check proximity of last closing price to 44-day MA
#         last_close = data['low'].iloc[-1]
#         ma_value = data['44_day_mavg'].iloc[-1]
#         # prev_2_close = data['low'].iloc[-2]
#         # ma_value_2 = data['44_day_mavg'].iloc[-2]
#         # prev_3_close = data['low'].iloc[-3]
#         # ma_value_3 = data['44_day_mavg'].iloc[-3]
#         # prev_4_close = data['low'].iloc[-4]
#         # ma_value_4 = data['44_day_mavg'].iloc[-4]
#         if (last_close >= ma_value * 0.92 and last_close <= ma_value * 1.01): 
#         # or (prev_2_close >= ma_value_2 * 0.99 and prev_2_close <= ma_value_2 * 1.50) or (prev_3_close >= ma_value_3 * 0.99 and prev_3_close <= ma_value_3 * 1.50) or (prev_4_close >= ma_value_4 * 0.99 and prev_4_close <= ma_value_4 * 1.50) :
#             result.append(instrument)
    
#     return result

# # # Find symbols where green candle is close to 44-day MA
# selected_symbols = find_symbols_close_to_ma()
# print("Symbols where green candle is close to 44-day MA and price is less than 3000:", selected_symbols)



# Function to fetch historical data
def get_historical_data(symbol, from_date, to_date, interval):
    historical_data = kite.historical_data(instrument_token=symbol['instrument_token'],
                                           from_date=from_date,
                                           to_date=to_date,
                                           interval=interval)
    if not historical_data:
        print("No historical data available for symbol:", symbol['tradingsymbol'])
        return None
    
    df = pd.DataFrame(historical_data)
    if 'date' not in df.columns:
        print("Error: 'date' column not found in historical data for symbol:", symbol['tradingsymbol'])
        return None
    
    df.set_index('date', inplace=True)
    return df

# Function to calculate 44-day moving average
def calculate_44_day_moving_average(data):
    data['44_day_mavg'] = data['close'].rolling(window=44, min_periods=1).mean()

# Function to check if the gradient of the 44-day moving average is upwards over the past 1 year
def is_gradient_upwards(data):
    # Calculate the 44-day moving average
    calculate_44_day_moving_average(data)
    
    # Calculate the slope of the moving average line
    slope = (data['44_day_mavg'].iloc[-1] - data['44_day_mavg'].iloc[0]) / len(data)
    
    # Check if the slope is positive
    return slope > 0

# Function to find symbols where green candle is close to 44-day MA and gradient of MA is upwards over the past 1 year
def find_symbols_with_conditions():
    result = []
    # instruments = get_instruments()
    instruments = ['1']
    for instrument in instruments:
        # Fetch historical data for the past 1 year
        to_date = dt.datetime.now().strftime('%Y-%m-%d')
        from_date = (dt.datetime.now() - dt.timedelta(days=365)).strftime('%Y-%m-%d')
        data = get_historical_data(3343617, from_date, to_date, 'day')
        
        if data is None or len(data) < 44:
            continue  # Skip if there are not enough data points
        
        # Check if the gradient of the 44-day moving average is upwards
        if not is_gradient_upwards(data):
            continue  # Skip if the gradient is not upwards
        
        # # Check if the Supertrend indicator is green
        # if data['supertrend'].iloc[-1] != 'green':
        #     continue  # Skip if Supertrend is not green
        
        # Check if the green candle intersects the 44-day MA
        last_low = data['low'].iloc[-1]
        ma_value = data['44_day_mavg'].iloc[-1]
        print(last_low)
        print(ma_value)
        # if last_low >= ma_value:
        #     result.append(instrument)
    
    return result

# Find symbols where all conditions are met
selected_symbols = find_symbols_with_conditions()
print("Symbols meeting all conditions:", selected_symbols)