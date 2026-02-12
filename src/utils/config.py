"""
configuration file for stock scoring system

This centralizes all the weights for each metric, sets metric defintions and thresholds.
Makes it easy to change the scoring model later on wiuthout changing the main code
"""

# the following code sets the weights for the categories, it must add up to 1
CATEGORY_WEIGHTS = {
    'valuation': 0.30, #how muich is the stock actually worth
    'growth': 0.25, #is the company actually growing
    'profitability': 0.25, #is the company actually profitable
    'risk': 0.20 #how risky is it
}

# metric defitions for each category
# 'weight'is how important each metric is within each category
# 'lower_is_better is true for metrics where a value being lower is better (Like a P/E ratio)

METRICS = {
    'valuation': {
        'pe_ratio' :{
            'weight': 0.40,
            'lower_is_better': True,
            'display_name': 'P/E Ratio',
            'description': 'Price to Earnings ratio (lower + cheaper)'
        },
        'peg_ratio':{
            'weight': 0.35,
            'lower_is_better': True,
            'display_name': 'PEG Ratio',
            'description': 'P/E relative to growth'
        },
        'price_to_fcf': {
            'weight': 0.25,
            'lower_is_better': True,
            'display_name': 'Price/FCF',
            'description': 'Price to Free Cash Flow'
        }
    },
    'growth':{
        'revenue_growth': {
            'weight':0.50,
            'lower_is_better':False,
            'display_name':'revenue growth',
            'description': 'Year-over-year revenue growth'
        },
        'eps_growth': {
            'weight':0.50,
            'lower_is_better':False,
            'display_name': 'EPS growth',
            'description':'Earning per share growth'
        }
    },
        'profitability':{
            'roe':{
                'weight':0.40,
                'lower_is_better':False,
                'display_name':'ROE',
                'description': 'Return on Equity'
            }, 
            'operating_margin':{
                'weight':0.30,
                'lower_is_better':False,
                'dsiplay_name': 'Operating Margin',
                'description':'Operating profit / Revenue'
            },
            'net margin':{
                'weight':0.30,
                'lower_is_better': False,
                'display_name':'Net Margin',
                'description':'Net Profit/Revenue'
            }
        },
        'risk': {
            'debt_to_equity':{
                'weight':0.40,
                'lower_is_better':True,
                'display_name':'Debt/Equity',
                'description':'Total debt / Shareholder equity'
            },
            'current_ratio':{
                'weight': '0.30',
                'lower_is_better':False,
                'display_name':'Current Ratio', 
                'description':'Current assets / Current liabilities'
            },
            'beta':{
                'weight':0.30,
                'lower_is_better': True,
                'display_name': 'beta',
                'description':'Volatility vs market (1.0 = Moves with Market)'
            }
        }
}
THRESHOLDS = {
    'high_debt': 2.0,
    'weak_liquidity':1.2,
    'extreme_pe':100,
    'negative_growth':-0.05,
    'min_peer_count':5
}