# import pandas as pd
import os
import pyotp
import datetime as dt
import json
import time
import requests

from kiteconnect import KiteConnect

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

# Instrument token of RELIANCE
instrument_token = "738561" 

# Dates between which we need historical data
from_date = "2016-10-01"
to_date = "2016-10-17"

# Interval(minute, day, 3 minute, 5 minute...)
interval = "5minute"

# kite = KiteConnect(api_key=api_key)
# kite.set_access_token(access_token)

# Gets historical data from Kite Connect
def get_historical_data():
 return kite.historical(instrument_token, from_date, to_date, interval)

"""
  Implementation of the moving average strategy.
  We go through the historical records that 
  we received form Kite Connect, calculate moving average,
  and place a BUY or SELL order.
"""
def strategy(records):
    total_closing_price = 0
    record_count = 0
    order_placed = False
    last_order_placed = None
    last_order_price = 0
    profit = 0
    
    for record in records:
        record_count += 1
        total_closing_price += record['close']
        
        #Moving average is calculated for every 5 ticks
        if record_count >= 5:
            moving_average = total_closing_price/5
            
            #If moving average is greater than the last tick, we place a buy order
            if record['close'] > moving_average:
                if last_order_placed == "SELL" or last_order_placed is None:
                    
                    #If last order was Sell, we need to exit the stock first
                    if last_order_placed == "SELL":
                        print("Exit SELL")
                        
                        #Calculate Profit
                        profit += last_order_price - record['Close']
                        last_order_price = record['Close']
                        
                    #New Buy Order
                    print("Place a new BUY Order")
                    last_order_placed == "BUY"
                    
            #If moving average is less than the last tick and there is a position, place a sell order
            elif record['close'] < moving_average:
                if last_order_placed == "BUY":
                
                    #As last trade was a buy, lets exit it first
                    print("Exit BUY")
                
                #Calculate Profit again
                profit += record['close'] - last_order_price
                last_order_price = record['close']
                
                #Fresh SELL Order
                print("Place new SELL Order")
                last_order_placed == "SELL"
                
        total_closing_price == records[record_count - 5]['close']
    print("Gross Profit",profit)
    #Place the last order
    place_order(last_order_placed)
    

#Place an order based on the transaction type(BUY/SELL)
def place_order(transaction_type):
    kite.order_place(tradingsymbol = "KIRIINDUS", exchange = "NSE", quantity = 1, transaction_type=transaction_type,
                    order_type="MARKET",product="CNC")
    
def start():
    records = get_historical_data()
    strategy(records)

start()
