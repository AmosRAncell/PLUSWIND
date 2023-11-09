import os
import numpy as np
import pandas as pd

# ----- User Input -----
years = [2018, 2019, 2020, 2021]

curtAdderFileForm = 'path/to/hourlyCurtailmentAddersBy{ISO}.csv' # files with hourly ISO-wide curtailment adders
curtAdderIsos = ['CAISO','ERCOT','SPP']

curtMultFileForm = 'path/to/hourlyCurtailmentMultipliersBy{ISO}{YEAR}.csv' # files with hourly ISO-wide curtailment multipliers
curtMultIsos = ['ISONE','MISO','NYISO','PJM']

genFileForm = 'path/to/hourlyGenByIso/hourlyGen_hrBegAvg_preCurtAdj_2018-2021_{ISO}-20230128.csv' # files with pre-curtailment-adjusted generation (i.e. the outputs of getHourlyGenByIso.py)

outN = 'path/to/hourlyGenByIso/hourlyGen_hrBegAvg_curtAdj_clip995_2018-2021_{ISO}-20230129.csv'
# ----------------------

# Load in curtailment adders
curtAdders = {}
for iso in curtAdderIsos:
	isoCurt = pd.read_csv(curtAdderFileForm.format(ISO=iso))
	isoCurt['GMT Datetime (Hour Beginning)'] = pd.to_datetime(isoCurt['GMT Datetime (Hour Beginning)'],infer_datetime_format=True,utc=True)
	isoCurt.set_index('GMT Datetime (Hour Beginning)',inplace=True)
	curtAdders[iso] = isoCurt

curtAdders = pd.concat(curtAdders,names=['ISO','GMT Datetime (Hour Beginning)'])

# Load in curtailment multipliers
curtMults = {}
for iso in curtMultIsos:
	isoCurt = pd.DataFrame()
	for year in years:
		curt = pd.read_csv(curtMultFileForm.format(ISO=iso,YEAR=year))
		curt['GMT Datetime (Hour Beginning)'] = pd.to_datetime(curt['eiaID'],infer_datetime_format=True,utc=True)
		isoCurt = isoCurt.combine_first(curt.set_index('GMT Datetime (Hour Beginning)'))
		assert not isoCurt.index.duplicated().any()
	curtMults[iso] = isoCurt

curtMults = pd.concat(curtMults,names=['ISO','GMT Datetime (Hour Beginning)'])

# Load in hourly ISO-aggregated generation
gens = []
for iso in curtAdderIsos+curtMultIsos:
	gen = pd.read_csv(genFileForm.format(ISO=iso))
	gen['gmt'] = pd.to_datetime(gen['gmt'],infer_datetime_format=True,cache=True)
	gens.append(gen)

gens = pd.concat(gens).set_index(['ISO','gmt'])

# Add curtailment info to the generation dataframe
gens['curtAdder MWh'] = curtAdders['WindCurtailment-MWh']
gens['curtMult'] = curtMults['hourly-curInflator']

assert not (gens['curtAdder MWh'].notna() & gens['curtMult'].notna()).any() # ensure curtailment adders and multipliers are mutually exclusive: only one should be non-na and in use at a time

# Clip hourly curtailment multipliers to be no larger than 2
gens['curtMultClippedAt2'] = gens['curtMult'] > 2
gens['curtMult'] = gens['curtMult'].clip(upper=2)

# Adjust generation for curtailment
gens['curtAdjustedGen MWh'] = gens['Reported Gen MWh']
addRows = gens['curtAdder MWh'].notna()
gens.loc[addRows,'curtAdjustedGen MWh'] += gens.loc[addRows,'curtAdder MWh']
multRows = gens['curtMult'].notna()
gens.loc[multRows,'curtAdjustedGen MWh'] *= gens.loc[multRows,'curtMult']

# Limit curtailment adjusted generation to 99.5th percentile by year and ISO
yrIdx = gens.index.get_level_values('gmt').year.rename('Year')
top995 = lambda g: g.quantile(0.95)
limits = gens['curtAdjustedGen MWh'].groupby(['ISO',yrIdx]).transform(top995)
gens['curtAdjGenClippedAt99.5'] = gens['curtAdjustedGen MWh'] > limits
gens['curtAdjustedGen MWh'] = gens['curtAdjustedGen MWh'].clip(upper=limits)
# NOTE: the above line is equivalent to: gens['curtAdjustedGen MWh'] = gens['curtAdjustedGen MWh'].mask(gens['curtAdjGenClippedAt99.5'],limits)

# Output to CSVs
boolCols = gens.columns[gens.dtypes == 'bool']
gens[boolCols] = gens[boolCols].astype(int)
gens.groupby('ISO').apply(lambda g: g.to_csv(outN.format(ISO=g.name)))
