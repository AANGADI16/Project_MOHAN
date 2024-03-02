from kiteconnect import KiteConnect
import pandas as pd
from datetime import datetime, timedelta

# Initialize Kite Connect client
kite = KiteConnect(api_key='your_api_key')
# Set access token
kite.set_access_token('your_access_token')

# Function to fetch instruments (stocks) from NSE
def get_nse_equity_instruments():
    instruments = kite.instruments("NSE")
    nse_equity_instruments = [instrument for instrument in instruments if instrument['segment'] == "NSE" and instrument['exchange'] == "NSE" and instrument['instrument_type'] == "EQ"]
    return nse_equity_instruments

# Function to fetch historical data for a stock
def get_historical_data(symbol, interval):
    # Calculate from_date and to_date
    to_date = datetime.now().strftime('%Y-%m-%d')
    from_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    data = kite.historical_data(symbol, from_date, to_date, interval)
    df = pd.DataFrame(data)
    df.set_index('date', inplace=True)
    return df

# Function to calculate volatility
def calculate_volatility(data, window):
    return data['close'].rolling(window=window).std()

# Function to identify volatility contraction pattern
def identify_volatility_contraction(symbol):
    try:
        # Fetch historical data
        data = get_historical_data(symbol, 'day')
        
        # Calculate volatility (you may choose a different window size)
        data['volatility'] = calculate_volatility(data, window=20)
        
        # Identify periods of volatility contraction
        contraction_window = 5
        for i in range(len(data) - contraction_window):
            contraction_window_data = data.iloc[i:i+contraction_window]
            max_volatility = contraction_window_data['volatility'].max()
            min_volatility = contraction_window_data['volatility'].min()
            if max_volatility - min_volatility < 0.1:  # Example threshold for contraction
                print(f"Potential volatility contraction detected for {symbol} at {data.index[i+contraction_window]}")

        # Detect breakout from the contraction phase
        breakout_window = 10
        for i in range(len(data) - breakout_window):
            breakout_window_data = data.iloc[i:i+breakout_window]
            max_close = breakout_window_data['close'].max()
            min_close = breakout_window_data['close'].min()
            if breakout_window_data.iloc[-1]['close'] > max_close and breakout_window_data.iloc[-1]['close'] > max_close:  
                print(f"Breakout detected for {symbol} at {data.index[i+breakout_window]}")

    except Exception as e:
        print(f"Error processing {symbol}: {str(e)}")

# Function to identify volatility contraction pattern for all NSE equity instruments
def identify_volatility_contraction_for_all():
    nse_equity_instruments = get_nse_equity_instruments()
    print(f"Total NSE equity instruments: {len(nse_equity_instruments)}")
    
    for instrument in nse_equity_instruments:
        identify_volatility_contraction(instrument['tradingsymbol'])

# Example usage
identify_volatility_contraction_for_all()
