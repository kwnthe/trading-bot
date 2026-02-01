import pandas as pd

def get_clean_training_data(file_path):
    # 1. Load the raw CSV
    df = pd.read_csv(file_path)
    
    # 2. Keep only the rows where a trade actually finished
    # This removes summary stats, empty rows, and text headers
    valid_states = ['TP_HIT', 'SL_HIT']
    df_clean = df[df['state'].isin(valid_states)].copy()
    
    # 3. Select your "Scale-Agnostic" features
    features = [
        'rsi_at_break', 
        'time_to_fill', 
        'relative_volume', 
        'atr_rel_excursion', 
        'atr_breakout_wick'
    ]
    
    # 4. Final selection and Target encoding
    # We drop any rows that might have a missing feature (NaN)
    df_final = df_clean[features + ['state', 'symbol']].dropna()
    
    # Convert state to binary: 1 = Win (TP), 0 = Loss (SL)
    df_final['target'] = (df_final['state'] == 'TP_HIT').astype(int)
    
    return df_final.drop(columns=['state'])

# Usage
df_silver = get_clean_training_data('data/XAGUSD.csv')
df_gold = get_clean_training_data('data/XAUUSD.csv')

# Merge both into one master AI dataset
df_train = pd.concat([df_silver, df_gold], axis=0).reset_index(drop=True)

# 6. Save the final dataset
df_train.to_csv('data/forex/example.csv', index=False)