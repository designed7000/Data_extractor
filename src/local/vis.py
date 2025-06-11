import pandas as pd

dt = pd.read_csv('../data/products_monitors_20250611_141640.csv')

print(dt['price_text'])